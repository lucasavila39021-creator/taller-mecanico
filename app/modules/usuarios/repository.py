from datetime import datetime

from sqlmodel import func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.repository import BaseRepository
from app.modules.usuarios.models import AsignacionRol, EventoSeguridad, IntentoAcceso, Usuario


class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Usuario)

    async def get_by_email(self, email: str) -> Usuario | None:
        consulta = select(Usuario).where(Usuario.email == email)
        return (await self.session.exec(consulta)).first()


class AsignacionRolRepository(BaseRepository[AsignacionRol]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AsignacionRol)

    # Vigente: no revocada y sin vencer.
    async def roles_vigentes(self, usuario_id: int, ahora: datetime) -> list[str]:
        consulta = (
            select(AsignacionRol.rol)
            .where(
                AsignacionRol.usuario_id == usuario_id,
                AsignacionRol.revocada_en.is_(None),
                or_(AsignacionRol.vence_en.is_(None), AsignacionRol.vence_en > ahora),
            )
            .order_by(AsignacionRol.rol)
        )
        return list((await self.session.exec(consulta)).all())


class IntentoAccesoRepository(BaseRepository[IntentoAcceso]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, IntentoAcceso)

    # RN-08: cuántos fallos cuentan y cuándo fue el más viejo de ellos.
    # Un login correcto reinicia la cuenta: sólo cuentan los fallos posteriores al último acierto.
    async def fallos_recientes(self, email: str, ip: str, desde: datetime) -> tuple[int, datetime | None]:
        ultimo_acierto = (
            select(func.max(IntentoAcceso.id))
            .where(IntentoAcceso.email == email, IntentoAcceso.ip == ip, IntentoAcceso.exito.is_(True))
            .scalar_subquery()
        )
        consulta = select(func.count(), func.min(IntentoAcceso.cuando)).where(
            IntentoAcceso.email == email,
            IntentoAcceso.ip == ip,
            IntentoAcceso.exito.is_(False),
            IntentoAcceso.cuando >= desde,
            IntentoAcceso.id > func.coalesce(ultimo_acierto, 0),
        )
        cantidad, primero = (await self.session.exec(consulta)).one()
        return cantidad, primero


class EventoSeguridadRepository(BaseRepository[EventoSeguridad]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EventoSeguridad)
