from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, text
from sqlmodel import Field, Relationship, SQLModel

# Sólo para el editor: importarlo de verdad sería circular, porque ordenes también nombra a Repuesto.
if TYPE_CHECKING:
    from app.modules.ordenes.models import ItemOrden


def _ahora() -> datetime:
    return datetime.now(UTC)


class Repuesto(SQLModel, table=True):
    __tablename__ = "repuesto"
    __table_args__ = (
        CheckConstraint("precio > 0", name="ck_repuesto_precio"),
        CheckConstraint("stock >= 0", name="ck_repuesto_stock"),
        # El código es único sólo entre los vigentes.
        Index(
            "uq_repuesto_codigo_vigente",
            "codigo",
            unique=True,
            postgresql_where=text("borrado_en IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    codigo: str
    descripcion: str
    precio: Decimal = Field(sa_type=Numeric(10, 2))
    # RN-14: sólo cambia a través de movimientos.
    stock: int = 0
    borrado_en: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

    # passive_deletes="all": al borrar el repuesto, SQLAlchemy no toca a los hijos. Sin esto intentaría
    # poner en NULL su repuesto_id, y ese UPDATE es lo que rechaza el disparador de sólo agregado.
    movimientos: list["MovimientoStock"] = Relationship(
        back_populates="repuesto",
        sa_relationship_kwargs={"lazy": "raise", "passive_deletes": "all"},
    )
    historial_precios: list["HistorialPrecio"] = Relationship(
        back_populates="repuesto",
        sa_relationship_kwargs={"lazy": "raise", "passive_deletes": "all"},
    )
    items: list["ItemOrden"] = Relationship(
        back_populates="repuesto",
        sa_relationship_kwargs={"lazy": "raise"},
    )


class MovimientoStock(SQLModel, table=True):
    __tablename__ = "movimiento_stock"
    # Distinto de cero y no mayor que cero: las salidas se guardan con cantidad negativa.
    __table_args__ = (CheckConstraint("cantidad <> 0", name="ck_movimiento_stock_cantidad"),)

    id: int | None = Field(default=None, primary_key=True)
    repuesto_id: int = Field(foreign_key="repuesto.id", index=True)
    orden_id: int | None = Field(default=None, foreign_key="orden_trabajo.id", index=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    cantidad: int
    motivo: str
    cuando: datetime = Field(default_factory=_ahora, sa_type=DateTime(timezone=True))

    repuesto: Repuesto = Relationship(
        back_populates="movimientos",
        sa_relationship_kwargs={"lazy": "raise"},
    )


class HistorialPrecio(SQLModel, table=True):
    __tablename__ = "historial_precio_repuesto"
    __table_args__ = (
        CheckConstraint("precio_nuevo > 0", name="ck_historial_precio_repuesto_precio_nuevo"),
        CheckConstraint("precio_nuevo <> precio_anterior", name="ck_historial_precio_repuesto_cambio"),
    )

    id: int | None = Field(default=None, primary_key=True)
    repuesto_id: int = Field(foreign_key="repuesto.id", index=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    precio_anterior: Decimal = Field(sa_type=Numeric(10, 2))
    precio_nuevo: Decimal = Field(sa_type=Numeric(10, 2))
    cuando: datetime = Field(default_factory=_ahora, sa_type=DateTime(timezone=True))

    repuesto: Repuesto = Relationship(
        back_populates="historial_precios",
        sa_relationship_kwargs={"lazy": "raise"},
    )
