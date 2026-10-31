from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.unit_of_work import UnitOfWork
from app.modules.clientes.repository import ClienteRepository
from app.modules.usuarios.repository import (
    AsignacionRolRepository,
    EventoSeguridadRepository,
    UsuarioRepository,
)


class UsuariosUnitOfWork(UnitOfWork):
    # Todos los repositorios comparten la sesión: lo que hacen se confirma o se revierte junto.
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.usuarios = UsuarioRepository(session)
        self.roles = AsignacionRolRepository(session)
        self.clientes = ClienteRepository(session)
        self.eventos = EventoSeguridadRepository(session)
