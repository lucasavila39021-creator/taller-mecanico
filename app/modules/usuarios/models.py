from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, Index, UniqueConstraint, text
from sqlmodel import Field, Relationship, SQLModel

# Sólo para el editor: importarlo de verdad sería circular, porque clientes también nombra a Usuario.
if TYPE_CHECKING:
    from app.modules.clientes.models import Cliente


class Rol(StrEnum):
    ADMIN = "ADMIN"
    RECEPCION = "RECEPCION"
    MECANICO = "MECANICO"
    CLIENTE = "CLIENTE"


def _ahora() -> datetime:
    return datetime.now(UTC)


class Usuario(SQLModel, table=True):
    __tablename__ = "usuario"
    # Las restricciones llevan nombre para poder reconocerlas al traducir un IntegrityError a un 409.
    __table_args__ = (UniqueConstraint("email", name="uq_usuario_email"),)

    id: int | None = Field(default=None, primary_key=True)
    email: str
    nombre: str
    password_hash: str
    activo: bool = True
    debe_cambiar_password: bool = False
    password_cambiada_en: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

    # foreign_keys es necesario porque asignacion_rol tiene dos claves foráneas a usuario.
    # lazy="raise": leer la relación sin precargarla falla, en lugar de disparar una consulta oculta.
    roles: list["AsignacionRol"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={"foreign_keys": "[AsignacionRol.usuario_id]", "lazy": "raise"},
    )
    # uselist=False: devuelve un objeto y no una lista.
    cliente: Optional["Cliente"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={"uselist": False, "lazy": "raise"},
    )


class AsignacionRol(SQLModel, table=True):
    __tablename__ = "asignacion_rol"
    __table_args__ = (
        CheckConstraint("rol IN ('ADMIN', 'RECEPCION', 'MECANICO', 'CLIENTE')", name="ck_asignacion_rol_rol"),
        # RN-03: una sola asignación abierta por rol. Las revocadas quedan como historial.
        Index(
            "uq_asignacion_rol_usuario_rol_abierta",
            "usuario_id",
            "rol",
            unique=True,
            postgresql_where=text("revocada_en IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    rol: str
    desde: datetime = Field(default_factory=_ahora, sa_type=DateTime(timezone=True))
    vence_en: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    revocada_en: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    # Quién otorgó el rol. Nula cuando no lo otorgó un usuario, como en el auto-registro.
    otorgada_por: int | None = Field(default=None, foreign_key="usuario.id", index=True)

    usuario: Usuario = Relationship(
        back_populates="roles",
        sa_relationship_kwargs={"foreign_keys": "[AsignacionRol.usuario_id]", "lazy": "raise"},
    )


class IntentoAcceso(SQLModel, table=True):
    __tablename__ = "intento_acceso"
    # RN-08: el conteo de fallos busca por correo y dirección dentro de una ventana de tiempo.
    __table_args__ = (Index("ix_intento_acceso_email_ip_cuando", "email", "ip", "cuando"),)

    id: int | None = Field(default=None, primary_key=True)
    cuando: datetime = Field(default_factory=_ahora, sa_type=DateTime(timezone=True))
    email: str
    ip: str
    exito: bool


class EventoSeguridad(SQLModel, table=True):
    __tablename__ = "evento_seguridad"

    id: int | None = Field(default=None, primary_key=True)
    cuando: datetime = Field(default_factory=_ahora, sa_type=DateTime(timezone=True))
    # Texto y no clave foránea: el actor puede ser SISTEMA, que no es un usuario.
    actor: str
    accion: str
