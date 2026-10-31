from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.usuarios.schemas import Texto


class ClienteEntrada(BaseModel):
    # Sin usuario_id: la recepción carga la ficha, y la cuenta llega sólo por el auto-registro.
    model_config = ConfigDict(extra="forbid")

    nombre: Texto
    documento: Texto
    telefono: Texto


class VehiculoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patente: Texto
    marca: Texto
    modelo: Texto
    anio: int = Field(ge=1950, le=2100)

    # ac456ef y AC456EF son la misma patente.
    @field_validator("patente")
    @classmethod
    def _normalizar_patente(cls, valor: str) -> str:
        return valor.upper()


class VehiculoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    patente: str
    marca: str
    modelo: str
    anio: int


class ClienteSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int | None
    nombre: str
    documento: str
    telefono: str


class ClienteDetalle(ClienteSalida):
    vehiculos: list[VehiculoSalida]
