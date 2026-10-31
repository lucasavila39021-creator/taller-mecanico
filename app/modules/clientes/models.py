from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, Index, UniqueConstraint, text
from sqlmodel import Field, Relationship, SQLModel

# Sólo para el editor: importarlo de verdad sería circular, porque usuarios también nombra a Cliente.
if TYPE_CHECKING:
    from app.modules.ordenes.models import OrdenTrabajo
    from app.modules.usuarios.models import Usuario


class Cliente(SQLModel, table=True):
    __tablename__ = "cliente"
    # El UNIQUE de usuario_id ya crea un índice, así que la clave foránea no necesita otro.
    __table_args__ = (
        UniqueConstraint("usuario_id", name="uq_cliente_usuario_id"),
        UniqueConstraint("documento", name="uq_cliente_documento"),
    )

    id: int | None = Field(default=None, primary_key=True)
    usuario_id: int | None = Field(default=None, foreign_key="usuario.id")
    nombre: str
    documento: str
    telefono: str

    usuario: Optional["Usuario"] = Relationship(
        back_populates="cliente",
        sa_relationship_kwargs={"lazy": "raise"},
    )
    vehiculos: list["Vehiculo"] = Relationship(
        back_populates="cliente",
        sa_relationship_kwargs={"lazy": "raise"},
    )


class Vehiculo(SQLModel, table=True):
    __tablename__ = "vehiculo"
    __table_args__ = (
        CheckConstraint("anio BETWEEN 1950 AND 2100", name="ck_vehiculo_anio"),
        # La patente es única sólo entre los vigentes: el comprador de un auto vendido puede registrarlo.
        Index(
            "uq_vehiculo_patente_vigente",
            "patente",
            unique=True,
            postgresql_where=text("borrado_en IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    cliente_id: int = Field(foreign_key="cliente.id", index=True)
    patente: str
    marca: str
    modelo: str
    anio: int
    borrado_en: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

    cliente: Cliente = Relationship(
        back_populates="vehiculos",
        sa_relationship_kwargs={"lazy": "raise"},
    )
    ordenes: list["OrdenTrabajo"] = Relationship(
        back_populates="vehiculo",
        sa_relationship_kwargs={"lazy": "raise"},
    )
