from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.schemas.common import Nombre

# Contraseñas que un ataque de diccionario prueba primero. La lista es corta a propósito: atrapa lo obvio sin
# volver molesto el registro.
_CONTRASENAS_COMUNES = {
    "12345678", "123456789", "1234567890", "87654321", "11111111", "00000000", "12341234", "11223344",
    "password", "password1", "contraseña", "contrasena", "qwerty123", "qwertyui", "asdfghjk", "abcd1234",
    "iloveyou", "teamo123", "colombia", "payandcheck", "paycheck", "123123123", "abc12345",
}


def _contrasena_segura(valor: str) -> str:
    if len(valor) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if valor.lower() in _CONTRASENAS_COMUNES or len(set(valor)) <= 2:
        raise ValueError("Esa contraseña es muy fácil de adivinar. Prueba con otra.")
    return valor


NuevaContrasena = Annotated[str, Field(max_length=128), AfterValidator(_contrasena_segura)]

# El correo identifica la cuenta sin importar mayúsculas: el teclado del teléfono
# suele poner la primera letra en mayúscula y eso no debe crear otra cuenta.
Email = Annotated[EmailStr, AfterValidator(str.lower)]


class RegisterRequest(BaseModel):
    email: Email
    password: NuevaContrasena
    nombre: Nombre
    idioma: Literal["es", "en"] | None = None
    # Sin aceptar la política vigente no hay cuenta: la app no deja enviar el formulario sin la casilla.
    acepta_politica: bool
    politica_version: str


class ConsentimientoRequest(BaseModel):
    politica_version: str


class ConsentimientoSmsRequest(BaseModel):
    acepta: bool


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(max_length=128)


class GoogleAuthRequest(BaseModel):
    id_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
