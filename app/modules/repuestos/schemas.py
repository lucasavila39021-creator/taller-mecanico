from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from app.modules.usuarios.schemas import Texto

# Dentro de lo que entra en NUMERIC(10,2): sin este límite, un precio enorme sería un 500.
PrecioEntrada = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
# El dinero sale como texto y con dos decimales: "32000.00".
Dinero = Annotated[Decimal, PlainSerializer(lambda valor: f"{valor:.2f}", return_type=str)]
# Un INTEGER de PostgreSQL llega a 2147483647; este límite deja margen para sumar.
CANTIDAD_MAXIMA = 1_000_000


class RepuestoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: Texto
    descripcion: Texto
    precio: PrecioEntrada
    stock_inicial: int = Field(ge=0, le=CANTIDAD_MAXIMA)

    # fil-001 y FIL-001 son el mismo código.
    @field_validator("codigo")
    @classmethod
    def _normalizar_codigo(cls, valor: str) -> str:
        return valor.upper()


class RepuestoCambio(BaseModel):
    # extra="forbid": el stock no se edita por PATCH (RN-14).
    model_config = ConfigDict(extra="forbid")

    # El valor por defecto no se valida, pero un null enviado sí: da 422.
    descripcion: Texto = None
    precio: PrecioEntrada = None


class ReponerEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cantidad: int = Field(gt=0, le=CANTIDAD_MAXIMA)


class RepuestoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    descripcion: str
    precio: Dinero
    stock: int


class MovimientoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repuesto_id: int
    orden_id: int | None
    usuario_id: int
    cantidad: int
    motivo: str
    cuando: datetime


class PrecioSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repuesto_id: int
    usuario_id: int
    precio_anterior: Dinero
    precio_nuevo: Dinero
    cuando: datetime
