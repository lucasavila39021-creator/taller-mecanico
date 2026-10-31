from collections.abc import Sequence

from sqlalchemy.orm import selectinload
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.repository import BaseRepository, SoftDeleteRepository
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import EstadoOrden, OrdenTrabajo


class ClienteRepository(BaseRepository[Cliente]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Cliente)

    # RN-16: un vehículo dado de baja deja de aparecer, así que la precarga también lo filtra.
    async def get_con_vehiculos_vigentes(self, id: int) -> Cliente | None:
        consulta = (
            select(Cliente)
            .where(Cliente.id == id)
            .options(selectinload(Cliente.vehiculos.and_(Vehiculo.borrado_en.is_(None))))
        )
        return (await self.session.exec(consulta)).first()


class VehiculoRepository(SoftDeleteRepository[Vehiculo]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Vehiculo)

    async def vigentes_de_usuario(self, usuario_id: int) -> Sequence[Vehiculo]:
        consulta = (
            select(Vehiculo)
            .join(Cliente, Vehiculo.cliente_id == Cliente.id)
            .where(Cliente.usuario_id == usuario_id, Vehiculo.borrado_en.is_(None))
            .order_by(Vehiculo.id)
        )
        return (await self.session.exec(consulta)).all()

    # RN-16: abierta es la que está en un estado que el catálogo no marca como final.
    async def tiene_ordenes_abiertas(self, vehiculo_id: int) -> bool:
        consulta = (
            select(func.count())
            .select_from(OrdenTrabajo)
            .join(EstadoOrden, OrdenTrabajo.estado == EstadoOrden.codigo)
            .where(OrdenTrabajo.vehiculo_id == vehiculo_id, EstadoOrden.es_final.is_(False))
        )
        return (await self.session.exec(consulta)).one() > 0
