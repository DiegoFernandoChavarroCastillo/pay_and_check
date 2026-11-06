from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr

# El correo identifica la cuenta sin importar mayúsculas: el teclado del teléfono
# suele poner la primera letra en mayúscula y eso no debe crear otra cuenta.
Email = Annotated[EmailStr, AfterValidator(str.lower)]


class RegisterRequest(BaseModel):
    email: Email
    password: str
    nombre: str
    idioma: Literal["es", "en"] | None = None


class LoginRequest(BaseModel):
    email: Email
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
