from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Numeric, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

# Sólo para el editor: importarlos de verdad sería circular, porque esos módulos también nombran a estos modelos.
if TYPE_CHECKING:
    from app.modules.clientes.models import Vehiculo
    from app.modules.repuestos.models import Repuesto


# Tiene que coincidir con las filas de estado_orden: agregar un estado obliga a tocar los dos y el servicio.
class Estado(StrEnum):
    PENDIENTE = "PENDIENTE"
    EN_REPARACION = "EN_REPARACION"
    TERMINADA = "TERMINADA"
    CANCELADA = "CANCELADA"


def _ahora() -> datetime:
    return datetime.now(UTC)


class EstadoOrden(SQLModel, table=True):
    __tablename__ = "estado_orden"
    __table_args__ = (UniqueConstraint("posicion", name="uq_estado_orden_posicion"),)

    codigo: str = Field(primary_key=True)
    descripcion: str
    posicion: int
    es_final: bool


class OrdenTrabajo(SQLModel, table=True):
    __tablename__ = "orden_trabajo"
    __table_args__ = (CheckConstraint("total >= 0", name="ck_orden_trabajo_total"),)

    id: int | None = Field(default=None, primary_key=True)
    vehiculo_id: int = Field(foreign_key="vehiculo.id", index=True)
    mecanico_id: int | None = Field(default=None, foreign_key="usuario.id", index=True)
    estado: str = Field(foreign_key="estado_orden.codigo", index=True)
    falla: str
    creada_en: datetime = Field(default_factory=_ahora, sa_type=DateTime(timezone=True))
    total: Decimal = Field(sa_type=Numeric(12, 2))

    vehiculo: "Vehiculo" = Relationship(
        back_populates="ordenes",
        sa_relationship_kwargs={"lazy": "raise"},
    )
    # Los ítems y el historial se guardan junto con la orden, por la cascada de guardado.
    # passive_deletes="all": al borrar la orden, SQLAlchemy no toca a los hijos. Sin esto intentaría
    # poner en NULL su orden_id, y ese UPDATE es lo que rechaza el disparador de sólo agregado.
    items: list["ItemOrden"] = Relationship(
        back_populates="orden",
        sa_relationship_kwargs={"lazy": "raise", "passive_deletes": "all", "order_by": "ItemOrden.id"},
    )
    historial: list["HistorialEstadoOrden"] = Relationship(
        back_populates="orden",
        sa_relationship_kwargs={"lazy": "raise", "passive_deletes": "all", "order_by": "HistorialEstadoOrden.id"},
    )


class ItemOrden(SQLModel, table=True):
    __tablename__ = "item_orden"
    # El UNIQUE empieza por orden_id y le sirve de índice; repuesto_id necesita el suyo.
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_item_orden_cantidad"),
        CheckConstraint("precio_unitario > 0", name="ck_item_orden_precio_unitario"),
        UniqueConstraint("orden_id", "repuesto_id", name="uq_item_orden_orden_repuesto"),
    )

    id: int | None = Field(default=None, primary_key=True)
    orden_id: int = Field(foreign_key="orden_trabajo.id")
    repuesto_id: int = Field(foreign_key="repuesto.id", index=True)
    cantidad: int
    precio_unitario: Decimal = Field(sa_type=Numeric(10, 2))

    orden: OrdenTrabajo = Relationship(
        back_populates="items",
        sa_relationship_kwargs={"lazy": "raise"},
    )
    repuesto: "Repuesto" = Relationship(
        back_populates="items",
        sa_relationship_kwargs={"lazy": "raise"},
    )


class HistorialEstadoOrden(SQLModel, table=True):
    __tablename__ = "historial_estado_orden"

    id: int | None = Field(default=None, primary_key=True)
    orden_id: int = Field(foreign_key="orden_trabajo.id", index=True)
    desde_estado: str | None = Field(default=None, foreign_key="estado_orden.codigo", index=True)
    hasta_estado: str = Field(foreign_key="estado_orden.codigo", index=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    cuando: datetime = Field(default_factory=_ahora, sa_type=DateTime(timezone=True))

    orden: OrdenTrabajo = Relationship(
        back_populates="historial",
        sa_relationship_kwargs={"lazy": "raise"},
    )
