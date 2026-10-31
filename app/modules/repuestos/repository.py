from collections.abc import Sequence

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.repository import BaseRepository, SoftDeleteRepository
from app.modules.repuestos.models import HistorialPrecio, MovimientoStock, Repuesto

STOCK_MAXIMO = 2_147_483_647


class StockInsuficiente(Exception):
    """El movimiento dejaría el stock en negativo."""


class StockExcedido(Exception):
    """El movimiento dejaría un stock que no entra en la columna."""


class RepuestoRepository(SoftDeleteRepository[Repuesto]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Repuesto)

    # FOR UPDATE: dos operaciones sobre el mismo repuesto se atienden de a una.
    async def get_vigente_bloqueado(self, id: int) -> Repuesto | None:
        consulta = (
            select(Repuesto)
            .where(Repuesto.id == id, Repuesto.borrado_en.is_(None))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await self.session.exec(consulta)).first()

    async def get_bloqueado_incluyendo_bajas(self, id: int) -> Repuesto | None:
        consulta = (
            select(Repuesto)
            .where(Repuesto.id == id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await self.session.exec(consulta)).first()

    # RN-14: el ÚNICO punto del sistema que escribe el stock. Crea el movimiento y ajusta el número.
    # La cantidad es positiva si entra y negativa si sale. Recibe el repuesto ya bloqueado.
    async def registrar_movimiento(
        self,
        repuesto: Repuesto,
        cantidad: int,
        motivo: str,
        usuario_id: int,
        orden_id: int | None = None,
    ) -> MovimientoStock:
        nuevo_stock = repuesto.stock + cantidad
        if nuevo_stock < 0:
            raise StockInsuficiente
        if nuevo_stock > STOCK_MAXIMO:
            raise StockExcedido
        repuesto.stock = nuevo_stock
        movimiento = MovimientoStock(
            repuesto_id=repuesto.id,
            orden_id=orden_id,
            usuario_id=usuario_id,
            cantidad=cantidad,
            motivo=motivo,
        )
        self.session.add(movimiento)
        await self.session.flush()
        return movimiento


class MovimientoStockRepository(BaseRepository[MovimientoStock]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MovimientoStock)

    async def de_repuesto(self, repuesto_id: int) -> Sequence[MovimientoStock]:
        return await self.get_all(MovimientoStock.repuesto_id == repuesto_id)


class HistorialPrecioRepository(BaseRepository[HistorialPrecio]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, HistorialPrecio)

    async def de_repuesto(self, repuesto_id: int) -> Sequence[HistorialPrecio]:
        return await self.get_all(HistorialPrecio.repuesto_id == repuesto_id)
