from datetime import UTC, datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

from app.modules.usuarios.models import Rol

MAXIMO_BYTES_PASSWORD = 72


def _sin_caracter_nulo(valor: str) -> str:
    # PostgreSQL no guarda el carácter nulo: sin este control, sería un 500 en lugar de un 422.
    if "\x00" in valor:
        raise ValueError("No puede contener el carácter nulo")
    return valor


def _maximo_72_bytes(valor: str) -> str:
    # Bytes y no caracteres: una ñ ocupa dos. bcrypt rechaza con una excepción lo que pasa de 72.
    if len(valor.encode()) > MAXIMO_BYTES_PASSWORD:
        raise ValueError(f"La contraseña no puede ocupar más de {MAXIMO_BYTES_PASSWORD} bytes")
    return valor


Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1), AfterValidator(_sin_caracter_nulo)]
Password = Annotated[str, Field(min_length=1), AfterValidator(_sin_caracter_nulo), AfterValidator(_maximo_72_bytes)]


class RegistroEntrada(BaseModel):
    # extra="forbid": nadie se registra con un rol.
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    nombre: Texto
    password: Password
    documento: Texto
    telefono: Texto

    # El correo es único sin importar mayúsculas: Ana@x.com y ana@x.com son la misma persona.
    @field_validator("email")
    @classmethod
    def _normalizar_email(cls, valor: str) -> str:
        return valor.lower()


class LoginEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: Password

    @field_validator("email")
    @classmethod
    def _normalizar_email(cls, valor: str) -> str:
        return valor.lower()


class CambioPasswordEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password_actual: Password
    password_nueva: Password


class AltaPersonalEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    nombre: Texto
    password: Password

    @field_validator("email")
    @classmethod
    def _normalizar_email(cls, valor: str) -> str:
        return valor.lower()


class AsignarRolEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rol: Rol
    # AwareDatetime rechaza una fecha sin zona: es ambigua, ¿la hora de quién?
    vence_en: AwareDatetime | None = None

    @field_validator("vence_en")
    @classmethod
    def _vence_en_el_futuro(cls, valor: AwareDatetime | None) -> AwareDatetime | None:
        if valor is None:
            return None
        try:
            # Una fecha en el límite del calendario no entra al pasarla a UTC: sería un 500.
            en_utc = valor.astimezone(UTC)
        except OverflowError:
            raise ValueError("El vencimiento no es una fecha válida") from None
        if en_utc <= datetime.now(UTC):
            raise ValueError("El vencimiento tiene que estar en el futuro")
        return valor


class AsignacionSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    rol: str
    desde: datetime
    vence_en: datetime | None
    revocada_en: datetime | None
    otorgada_por: int | None


class EventoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cuando: datetime
    actor: str
    accion: str


class YoSalida(BaseModel):
    id: int
    email: str
    nombre: str
    debe_cambiar_password: bool
    roles_vigentes: list[str]
    roles_token: list[str]


# No trae el token: viaja sólo en la cookie.
class LoginSalida(BaseModel):
    mensaje: str
    debe_cambiar_password: bool
    expira_en_segundos: int


class MensajeSalida(BaseModel):
    mensaje: str


# No incluye password_hash.
class UsuarioSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nombre: str
