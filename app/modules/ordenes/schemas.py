from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.ordenes.models import OrdenTrabajo
from app.modules.repuestos.schemas import CANTIDAD_MAXIMA, Dinero
from app.modules.usuarios.schemas import Texto


class ItemEntrada(BaseModel):
    # extra="forbid": el precio nunca viaja en el cuerpo (RN-10).
    model_config = ConfigDict(extra="forbid")

    repuesto_id: int = Field(ge=1, le=2_147_483_647)
    cantidad: int = Field(gt=0, le=CANTIDAD_MAXIMA)


class OrdenEntrada(BaseModel):
    # extra="forbid": el total, el estado y la fecha tampoco viajan.
    model_config = ConfigDict(extra="forbid")

    vehiculo_id: int = Field(ge=1, le=2_147_483_647)
    falla: Texto
    items: list[ItemEntrada] = Field(min_length=1)

    @model_validator(mode="after")
    def _sin_repuestos_repetidos(self) -> Self:
        ids = [item.repuesto_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Un repuesto no puede repetirse en la orden")
        return self


class EstadoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: str
    descripcion: str
    posicion: int
    es_final: bool


class ItemSalida(BaseModel):
    repuesto_id: int
    codigo: str
    descripcion: str
    cantidad: int
    precio_unitario: Dinero
    subtotal: Dinero


class HistorialSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    desde_estado: str | None
    hasta_estado: str
    usuario_id: int
    cuando: datetime


class OrdenResumen(BaseModel):
    id: int
    estado: str
    patente: str
    total: Dinero
    creada_en: datetime
    mecanico_id: int | None
    falla: str
    cliente: str

    @classmethod
    def _campos(cls, orden: OrdenTrabajo) -> dict:
        return {
            "id": orden.id,
            "estado": orden.estado,
            "patente": orden.vehiculo.patente,
            "total": orden.total,
            "creada_en": orden.creada_en,
            "mecanico_id": orden.mecanico_id,
            "falla": orden.falla,
            "cliente": orden.vehiculo.cliente.nombre,
        }

    @classmethod
    def desde_orden(cls, orden: OrdenTrabajo) -> Self:
        return cls(**cls._campos(orden))


class OrdenDetalle(OrdenResumen):
    items: list[ItemSalida]
    historial: list[HistorialSalida]

    @classmethod
    def desde_orden(cls, orden: OrdenTrabajo) -> Self:
        return cls(
            **cls._campos(orden),
            items=[
                ItemSalida(
                    repuesto_id=item.repuesto_id,
                    codigo=item.repuesto.codigo,
                    descripcion=item.repuesto.descripcion,
                    cantidad=item.cantidad,
                    precio_unitario=item.precio_unitario,
                    subtotal=item.precio_unitario * item.cantidad,
                )
                for item in orden.items
            ],
            historial=[HistorialSalida.model_validate(linea) for linea in orden.historial],
        )
