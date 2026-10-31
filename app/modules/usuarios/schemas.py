from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

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


# No incluye password_hash.
class UsuarioSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nombre: str
