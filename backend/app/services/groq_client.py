"""Wrapper delgado sobre el SDK `groq`. La lógica de negocio (validar el JSON,
mapear categorías, etc.) vive en los routers/servicios que llaman a este
módulo — aquí solo se habla con la API de Groq."""

import json
import logging
import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import httpx
from groq import Groq

from app.core.config import settings
from app.services import ia_uso
from app.services.ia_seguridad import como_datos, marca_inyeccion, sanear_dato
from app.services.prompts import (
    build_expense_parse_prompt,
    build_receipt_parse_prompt,
    build_weekly_report_prompt,
)

# El plan original fijaba "llama-3.1-8b-instant", pero Groq lo descontinuó
# (404 model_not_found al probarlo en sep/2026). De los modelos de propósito
# general disponibles hoy en la cuenta, "openai/gpt-oss-20b" es el más chico
# y barato, y respondió bien al prompt de extracción en español al probarlo
# a mano. Si se prefiere otro modelo, cambiar solo esta constante.
MODEL = "openai/gpt-oss-20b"
# Modelo del coach (mensajes, consejos, chat). Separado del de extracción para
# poder subirlo a uno más capaz (ej. "openai/gpt-oss-120b") sin encarecer el parseo.
COACH_MODEL = MODEL
# Extraer un gasto es mecánico y va con el razonamiento al mínimo (rápido y barato). Redactar no: con "low"
# el modelo se limita a copiar el dato que recibe en vez de escribir el consejo con sus palabras.
COACH_REASONING = "medium"

GROQ_TIMEOUT_S = 15.0
GROQ_MAX_REINTENTOS = 0

# Topes sobre lo que el modelo extrae: un texto hostil no puede colar un monto o una fecha absurdos.
MONTO_MAXIMO = Decimal("100000000")
# Movimientos que se aceptan de una sola frase ("almuerzo 18 mil y un uber de 12.500").
MAX_MOVIMIENTOS = 5
VENTANA_FECHA = timedelta(days=365)
MAX_DESCRIPCION = 200

logger = logging.getLogger(__name__)

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        # Sin reintentos y con un timeout corto: si Groq no responde, la persona recibe el respaldo en
        # segundos en vez de esperar al timeout y los reintentos por defecto del SDK (más de un minuto).
        _client = Groq(api_key=settings.GROQ_API_KEY, timeout=GROQ_TIMEOUT_S, max_retries=GROQ_MAX_REINTENTOS)
    return _client


class GroqServiceError(Exception):
    """Error genérico llamando a Groq (red, API caída, etc.)."""


class CupoIAAgotado(GroqServiceError):
    """La persona usó todas sus solicitudes de IA del mes. Es un GroqServiceError a propósito: cada
    llamador ya sabe responder con su texto de respaldo cuando la IA no está disponible."""


class ExpenseParseError(GroqServiceError):
    """El modelo no devolvió un JSON válido o no pudo extraer un monto."""


def _chat(
    messages: list[dict], *, model: str = MODEL, temperature: float = 0, reasoning_effort: str = "low"
) -> str:
    # Sin `response_format={"type": "json_object"}` a propósito: con los modelos
    # de razonamiento (gpt-oss) el modo JSON de Groq hace que el modelo se quede
    # dando vueltas y devuelva vacío (400 json_validate_failed) de forma
    # intermitente. El JSON se pide en el prompt y se extrae con `_extraer_json`.
    uso = ia_uso.actual()  # None si quien llama no abrió un `ia_uso.usar(...)`: ni se registra ni hay tope
    if uso is not None and ia_uso.cupo_agotado(uso):
        ia_uso.registrar(uso, model, exito=False, uso_respaldo=True, bloqueado_por="cupo")
        raise CupoIAAgotado("Se agotó el cupo mensual de solicitudes de IA.")
    inicio = time.perf_counter()
    try:
        completion = _get_client().chat.completions.create(
            model=model, messages=messages, temperature=temperature, reasoning_effort=reasoning_effort
        )
        contenido = completion.choices[0].message.content
    except Exception as exc:  # errores de red / API de Groq
        if uso is not None:
            ia_uso.registrar(
                uso, model, exito=False, latencia_ms=_ms_desde(inicio), uso_respaldo=True
            )
        # Mismo modelo en otro proveedor: la respuesta es equivalente, así que los prompts y los filtros no cambian.
        if settings.AI_FALLBACK_URL and settings.AI_FALLBACK_API_KEY:
            return _chat_respaldo(messages, temperature=temperature, reasoning_effort=reasoning_effort, uso=uso)
        raise GroqServiceError(f"Error llamando a Groq: {exc}") from exc

    if uso is not None:
        tokens = getattr(completion, "usage", None)
        ia_uso.registrar(
            uso,
            model,
            exito=True,
            latencia_ms=_ms_desde(inicio),
            tokens_entrada=getattr(tokens, "prompt_tokens", None),
            tokens_salida=getattr(tokens, "completion_tokens", None),
        )
    return contenido


def _chat_respaldo(messages: list[dict], *, temperature: float, reasoning_effort: str, uso) -> str:
    """Llamada al proveedor de respaldo (API compatible con OpenAI). Queda en el registro de uso con su propio
    nombre de modelo, así se mide cuánto tráfico atiende y cuánto cuesta."""
    modelo = f"respaldo:{settings.AI_FALLBACK_MODEL}"
    inicio = time.perf_counter()
    try:
        respuesta = httpx.post(
            f"{settings.AI_FALLBACK_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.AI_FALLBACK_API_KEY}"},
            json={
                "model": settings.AI_FALLBACK_MODEL,
                "messages": messages,
                "temperature": temperature,
                "reasoning_effort": reasoning_effort,
            },
            timeout=GROQ_TIMEOUT_S,
        )
        respuesta.raise_for_status()
        data = respuesta.json()
        contenido = data["choices"][0]["message"]["content"]
    except Exception as exc:
        if uso is not None:
            ia_uso.registrar(uso, modelo, exito=False, latencia_ms=_ms_desde(inicio), uso_respaldo=True)
        raise GroqServiceError(f"Error llamando al proveedor de respaldo: {exc}") from exc
    if uso is not None:
        tokens = data.get("usage") or {}
        ia_uso.registrar(
            uso,
            modelo,
            exito=True,
            latencia_ms=_ms_desde(inicio),
            tokens_entrada=tokens.get("prompt_tokens"),
            tokens_salida=tokens.get("completion_tokens"),
        )
    return contenido


def _ms_desde(inicio: float) -> int:
    return round((time.perf_counter() - inicio) * 1000)


def _extraer_json(raw: str | None):
    """Decodifica el JSON de la respuesta del modelo, tolerando backticks o
    texto alrededor del objeto. Lanza ValueError si no hay un JSON válido."""
    texto = raw or ""
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio != -1 and fin > inicio:
        texto = texto[inicio : fin + 1]
    return json.loads(texto)


def _validar_gasto(raw: str, categorias: list[str], hoy: date | None = None) -> dict:
    """Valida el JSON de un gasto devuelto por el modelo. Nunca inventa datos:
    si falta algo o no es interpretable, lanza ExpenseParseError. Con `hoy`, la fecha debe quedar a
    menos de un año de ese día."""
    try:
        data = _extraer_json(raw)
    except ValueError as exc:
        raise ExpenseParseError("El modelo no devolvió un JSON válido.") from exc

    if not isinstance(data, dict):
        raise ExpenseParseError("El modelo no devolvió un objeto JSON.")

    if "error" in data:
        raise ExpenseParseError("No se pudo identificar un monto en el texto.")

    faltantes = {"monto", "descripcion", "fecha"} - data.keys()
    if data.get("tipo") != "ingreso":
        faltantes |= {"categoria"} - data.keys()
    if faltantes:
        raise ExpenseParseError(f"La respuesta del modelo no incluye: {', '.join(sorted(faltantes))}.")

    try:
        monto = Decimal(str(data["monto"]))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ExpenseParseError("No se pudo interpretar el monto como número.") from exc
    if monto <= 0:
        raise ExpenseParseError("El monto debe ser mayor que cero.")
    if monto > MONTO_MAXIMO:
        raise ExpenseParseError("El monto supera el máximo razonable.")

    # Un ingreso no lleva categoría: las categorías son de gasto.
    tipo = data.get("tipo", "gasto")
    if tipo not in ("gasto", "ingreso"):
        raise ExpenseParseError(f"El modelo devolvió un tipo de movimiento inválido: {tipo!r}.")
    if tipo == "gasto" and data["categoria"] not in categorias:
        raise ExpenseParseError(f"El modelo devolvió una categoría inválida: {data['categoria']!r}.")

    try:
        fecha = date.fromisoformat(str(data["fecha"]))
    except ValueError as exc:
        raise ExpenseParseError("La fecha devuelta por el modelo no es válida.") from exc
    if hoy is not None and abs(fecha - hoy) > VENTANA_FECHA:
        raise ExpenseParseError("La fecha devuelta por el modelo está fuera de un año alrededor de hoy.")

    comercio = data.get("comercio")
    return {
        "tipo": tipo,
        "monto": monto,
        "categoria": data["categoria"] if tipo == "gasto" else None,
        "descripcion": str(data["descripcion"]).strip()[:MAX_DESCRIPCION],
        "fecha": fecha,
        "comercio": str(comercio).strip() if comercio else None,
    }


def _validar_gasto_saneado(raw: str, categorias: list[str], hoy: date) -> dict:
    """El prompt lleva los nombres de categoría saneados: el modelo devuelve ese nombre y aquí se
    traduce al original."""
    saneadas = {sanear_dato(c): c for c in categorias}
    data = _validar_gasto(raw, list(saneadas), hoy)
    if data["categoria"] is not None:
        data["categoria"] = saneadas[data["categoria"]]
    return data


def _chat_marcando_inyeccion(texto: str, messages: list[dict]) -> str:
    """Llama a Groq y, si la heurística de entrada marcó el texto, lo anota en el registro de uso (sin el texto)."""
    inyectado = marca_inyeccion(texto)
    if inyectado:
        logger.warning("expenses: el texto parece un intento de inyección")
    try:
        return _chat(messages)
    finally:
        if inyectado:
            ia_uso.marcar_bloqueo("inyeccion")


def parse_expense_text(texto: str, categorias: list[str], hoy: date) -> dict:
    """Extrae {tipo, monto, categoria, descripcion, fecha} de un texto libre.
    `tipo` es "gasto" o "ingreso"; un ingreso viene sin categoría.

    Lanza ExpenseParseError con un mensaje claro si el modelo no devuelve un
    JSON usable o no logra identificar un monto — nunca inventa un monto.
    """
    raw = _chat_marcando_inyeccion(
        texto,
        [
            {"role": "system", "content": build_expense_parse_prompt(categorias, hoy.isoformat())},
            {"role": "user", "content": como_datos(texto)},
        ],
    )
    try:
        crudo = _extraer_json(raw)
    except ValueError as exc:
        raise ExpenseParseError("El modelo no devolvió un JSON válido.") from exc
    # Varios movimientos en una frase llegan como {"movimientos": [...]}; un objeto suelto sigue valiendo.
    if isinstance(crudo, dict) and isinstance(crudo.get("movimientos"), list) and crudo["movimientos"]:
        elementos = crudo["movimientos"][:MAX_MOVIMIENTOS]
    else:
        elementos = [crudo]

    # El primero tiene que ser válido (si no, el error es el de siempre); de los demás se descartan los que no
    # lo sean, para no perder el movimiento bueno por uno dudoso.
    data = _validar_gasto_saneado(json.dumps(elementos[0]), categorias, hoy)
    data.pop("comercio")
    adicionales = []
    for elemento in elementos[1:]:
        try:
            extra = _validar_gasto_saneado(json.dumps(elemento), categorias, hoy)
        except ExpenseParseError:
            continue
        extra.pop("comercio")
        adicionales.append(extra)
    if adicionales:
        data["adicionales"] = adicionales
    return data


def parse_receipt_text(texto_ocr: str, categorias: list[str], hoy: date) -> dict:
    """Extrae {monto, categoria, descripcion, fecha, comercio} del texto que el
    OCR del teléfono reconoció en un recibo. Mismas garantías que
    `parse_expense_text`."""
    raw = _chat_marcando_inyeccion(
        texto_ocr,
        [
            {"role": "system", "content": build_receipt_parse_prompt(categorias, hoy.isoformat())},
            {"role": "user", "content": como_datos(texto_ocr)},
        ],
    )
    data = _validar_gasto_saneado(raw, categorias, hoy)
    if data.pop("tipo") != "gasto":
        raise ExpenseParseError("El recibo no corresponde a un gasto.")
    return data


def generate_weekly_recommendations(resumen: str) -> str:
    """Devuelve 2-3 recomendaciones en texto natural a partir de un resumen agregado."""
    # `or ""`: Groq puede devolver content=None (el modelo solo "razonó") y un `.strip()` sobre None sería un 500.
    return (_chat([{"role": "system", "content": build_weekly_report_prompt(resumen)}], temperature=0.4) or "").strip()


def generate_coach_text(system_prompt: str, messages: list[dict] | None = None) -> str:
    """Respuesta en texto del coach. `messages` son los turnos previos del chat."""
    contenido = _chat(
        [{"role": "system", "content": system_prompt}, *(messages or [])],
        model=COACH_MODEL,
        temperature=0.6,
        reasoning_effort=COACH_REASONING,
    )
    return (contenido or "").strip()  # content=None no debe ser un 500: los llamadores ya tratan "" como respaldo


def generate_coach_json(system_prompt: str, contenido: str) -> dict:
    """Respuesta del coach como objeto JSON. Lanza GroqServiceError si no lo es."""
    raw = _chat(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": contenido}],
        model=COACH_MODEL,
        temperature=0.5,
        reasoning_effort=COACH_REASONING,
    )
    try:
        data = _extraer_json(raw)
    except ValueError as exc:
        raise GroqServiceError("El coach no devolvió un JSON válido.") from exc
    if not isinstance(data, dict):
        raise GroqServiceError("El coach no devolvió un objeto JSON.")
    return data
