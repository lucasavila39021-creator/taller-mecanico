from collections.abc import Sequence

from sqlalchemy import ColumnElement
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.repository import BaseRepository
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import EstadoOrden, HistorialEstadoOrden, ItemOrden, OrdenTrabajo


# Sólo lectura y sin heredar de BaseRepository: su clave primaria no es id, y heredar
# le daría add, update y delete, que no debe ofrecer (RN-19).
class EstadoOrdenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self) -> Sequence[EstadoOrden]:
        consulta = select(EstadoOrden).order_by(EstadoOrden.posicion)
        return (await self.session.exec(consulta)).all()

    async def get_by_codigo(self, codigo: str) -> EstadoOrden | None:
        return await self.session.get(EstadoOrden, codigo)


class OrdenRepository(BaseRepository[OrdenTrabajo]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OrdenTrabajo)

    # Una cantidad fija de consultas, sin importar cuántos ítems tenga: una para la orden con su
    # vehículo y cliente, una para los ítems con su repuesto y una para el historial (Ejercicio 8).
    async def get_detalle(self, id: int) -> OrdenTrabajo | None:
        consulta = (
            select(OrdenTrabajo)
            .where(OrdenTrabajo.id == id)
            .options(
                joinedload(OrdenTrabajo.vehiculo).joinedload(Vehiculo.cliente),
                selectinload(OrdenTrabajo.items).joinedload(ItemOrden.repuesto),
                selectinload(OrdenTrabajo.historial),
            )
            .execution_options(populate_existing=True)
        )
        return (await self.session.exec(consulta)).first()

    # Las órdenes de un listado con su vehículo y cliente, en la misma consulta.
    async def get_pagina_con_vehiculo(
        self, *filtros: ColumnElement[bool], offset: int, limit: int
    ) -> Sequence[OrdenTrabajo]:
        consulta = (
            select(OrdenTrabajo)
            .where(*filtros)
            .options(joinedload(OrdenTrabajo.vehiculo).joinedload(Vehiculo.cliente))
            .order_by(OrdenTrabajo.id)
            .offset(offset)
            .limit(limit)
        )
        return (await self.session.exec(consulta)).all()

    # FOR UPDATE: dos transiciones sobre la misma orden se atienden de a una.
    async def get_bloqueada(self, id: int) -> OrdenTrabajo | None:
        consulta = (
            select(OrdenTrabajo)
            .where(OrdenTrabajo.id == id)
            .options(selectinload(OrdenTrabajo.items))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await self.session.exec(consulta)).first()

    async def usuario_del_dueno(self, vehiculo_id: int) -> int | None:
        consulta = (
            select(Cliente.usuario_id)
            .join(Vehiculo, Vehiculo.cliente_id == Cliente.id)
            .where(Vehiculo.id == vehiculo_id)
        )
        return (await self.session.exec(consulta)).first()

    # El filtro de lo propio (RN-17). Se usa igual en la cuenta y en la página.
    @staticmethod
    def filtro_de_usuario(usuario_id: int) -> ColumnElement[bool]:
        vehiculos = (
            select(Vehiculo.id)
            .join(Cliente, Vehiculo.cliente_id == Cliente.id)
            .where(Cliente.usuario_id == usuario_id)
        )
        return OrdenTrabajo.vehiculo_id.in_(vehiculos)


class HistorialEstadoOrdenRepository(BaseRepository[HistorialEstadoOrden]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, HistorialEstadoOrden)
