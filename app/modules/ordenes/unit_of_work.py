from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.unit_of_work import UnitOfWork
from app.modules.clientes.repository import VehiculoRepository
from app.modules.ordenes.repository import EstadoOrdenRepository, HistorialEstadoOrdenRepository, OrdenRepository
from app.modules.repuestos.repository import RepuestoRepository


class OrdenesUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.ordenes = OrdenRepository(session)
        self.historial = HistorialEstadoOrdenRepository(session)
        self.estados = EstadoOrdenRepository(session)
        self.vehiculos = VehiculoRepository(session)
        self.repuestos = RepuestoRepository(session)
