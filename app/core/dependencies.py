import asyncio
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork


async def get_semaforo_bcrypt(request: Request) -> asyncio.Semaphore:
    return request.app.state.semaforo_bcrypt


async def get_hash_ficticio(request: Request) -> str:
    return request.app.state.hash_ficticio


async def get_fabrica_sesiones(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.fabrica_sesiones


# El router construye el Unit of Work y se lo pasa al servicio sin abrirlo.
async def get_usuarios_uow(session: Annotated[AsyncSession, Depends(get_session)]) -> UsuariosUnitOfWork:
    return UsuariosUnitOfWork(session)
