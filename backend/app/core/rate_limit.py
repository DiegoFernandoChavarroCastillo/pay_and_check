"""Límites de tasa (docs/seguridad.md, A2 y A6). Acotan el abuso económico de la IA ("denial of wallet") y el
adivinar contraseñas.

Viven en la memoria del proceso: se reinician con cada despliegue y, con más de una instancia, cada una
llevaría su propia cuenta (el límite efectivo se multiplica). Para el piloto, con una sola instancia, alcanza;
para escalar haría falta un almacén compartido (Redis)."""

import math
import threading
import time
from collections import deque

from fastapi import Depends, HTTPException, Request, status

from app.deps import get_current_user
from app.models.user import User

# Solicitudes de IA por persona y por minuto, sumando todos los endpoints que llaman a Groq.
MAX_SOLICITUDES_IA = 20
VENTANA_IA_S = 60
# Intentos de login FALLIDOS por IP y por email en cinco minutos. Solo cuentan los fallos: detrás de una misma
# IP (una universidad) muchas personas entran bien a la vez.
MAX_FALLOS_LOGIN = 10
VENTANA_LOGIN_S = 300

_reloj = time.monotonic  # las pruebas lo reemplazan


class LimiteDeTasa:
    """Ventana deslizante: como máximo `maximo` eventos por clave en los últimos `ventana_s` segundos."""

    def __init__(self, maximo: int, ventana_s: float):
        self.maximo = maximo
        self.ventana_s = ventana_s
        self._eventos: dict[str, deque[float]] = {}
        self._candado = threading.Lock()

    def _vigentes(self, clave: str, ahora: float) -> deque[float]:
        eventos = self._eventos.get(clave)
        if eventos is None:
            return deque()
        while eventos and eventos[0] <= ahora - self.ventana_s:
            eventos.popleft()
        if not eventos:
            del self._eventos[clave]  # no acumular claves muertas
        return eventos

    def _espera(self, claves: tuple[str, ...], ahora: float) -> int:
        espera = 0.0
        for clave in claves:
            eventos = self._vigentes(clave, ahora)
            if len(eventos) >= self.maximo:
                espera = max(espera, eventos[0] + self.ventana_s - ahora)
        return math.ceil(espera)

    def espera(self, *claves: str) -> int:
        """Segundos hasta poder volver a intentar; 0 si todavía hay lugar en todas las claves."""
        with self._candado:
            return self._espera(claves, _reloj())

    def registrar(self, *claves: str) -> None:
        with self._candado:
            ahora = _reloj()
            for clave in claves:
                self._vigentes(clave, ahora)
                self._eventos.setdefault(clave, deque()).append(ahora)

    def consumir(self, clave: str) -> int:
        """Revisa y registra en un solo paso. Devuelve 0 si pasó, o los segundos de espera si no (lo rechazado
        no se registra: esperar el `Retry-After` alcanza)."""
        with self._candado:
            ahora = _reloj()
            espera = self._espera((clave,), ahora)
            if espera == 0:
                self._eventos.setdefault(clave, deque()).append(ahora)
            return espera

    def olvidar(self, *claves: str) -> None:
        with self._candado:
            for clave in claves:
                self._eventos.pop(clave, None)

    def vaciar(self) -> None:
        with self._candado:
            self._eventos.clear()


LIMITE_IA = LimiteDeTasa(MAX_SOLICITUDES_IA, VENTANA_IA_S)
LIMITE_LOGIN = LimiteDeTasa(MAX_FALLOS_LOGIN, VENTANA_LOGIN_S)
# Canjes fallidos de códigos de convenio o de familia por persona: sin límite se podían probar códigos
# ("ECI-2001", "ECI-2002"…) hasta dar con uno válido y activar un plan pago gratis.
MAX_FALLOS_CANJE = 5
VENTANA_CANJE_S = 15 * 60
LIMITE_CANJE = LimiteDeTasa(MAX_FALLOS_CANJE, VENTANA_CANJE_S)


def reiniciar() -> None:
    """Borra todos los contadores (las pruebas, entre un caso y otro)."""
    LIMITE_IA.vaciar()
    LIMITE_LOGIN.vaciar()
    LIMITE_CANJE.vaciar()


def _demasiadas(espera: int, mensaje: str) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        mensaje.format(espera=espera),
        headers={"Retry-After": str(espera)},
    )


def limite_ia(current_user: User = Depends(get_current_user)) -> None:
    """Dependencia de los endpoints que llaman a Groq: un mismo contador por persona."""
    espera = LIMITE_IA.consumir(str(current_user.id))
    if espera:
        raise _demasiadas(espera, "Demasiadas solicitudes de IA seguidas. Intenta de nuevo en {espera} segundos.")


def ip_del_cliente(request: Request) -> str:
    """La IP del cliente. Detrás del proxy de Render sale de X-Forwarded-For: uvicorn arranca con
    --proxy-headers (ver start.sh), si no, todas las personas compartirían la IP del proxy."""
    return request.client.host if request.client else "desconocida"


def _claves_de_login(ip: str, email: str) -> tuple[str, str]:
    return f"ip:{ip}", f"email:{email}"


def revisar_login(ip: str, email: str) -> None:
    """Lanza 429 si esa IP o ese email ya acumularon demasiados intentos fallidos."""
    espera = LIMITE_LOGIN.espera(*_claves_de_login(ip, email))
    if espera:
        raise _demasiadas(espera, "Demasiados intentos fallidos. Intenta de nuevo en {espera} segundos.")


def registrar_fallo_de_login(ip: str, email: str) -> None:
    LIMITE_LOGIN.registrar(*_claves_de_login(ip, email))


def limpiar_fallos_de_login(email: str) -> None:
    """Entrar bien perdona los fallos de esa cuenta; los de la IP siguen contando."""
    LIMITE_LOGIN.olvidar(f"email:{email}")


def revisar_canje(user_id: int) -> None:
    """Lanza 429 si la persona ya acumuló demasiados códigos inválidos seguidos."""
    espera = LIMITE_CANJE.espera(f"canje:{user_id}")
    if espera:
        raise _demasiadas(espera, "Demasiados códigos inválidos. Intenta de nuevo en {espera} segundos.")


def registrar_fallo_de_canje(user_id: int) -> None:
    LIMITE_CANJE.registrar(f"canje:{user_id}")
