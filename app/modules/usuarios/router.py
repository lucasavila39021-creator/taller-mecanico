import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.dependencies import get_semaforo_bcrypt
from app.modules.usuarios import service
from app.modules.usuarios.schemas import RegistroEntrada, UsuarioSalida
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork

router = APIRouter(prefix="/auth", tags=["auth"])


# El router construye el Unit of Work y se lo pasa al servicio sin abrirlo.
async def get_uow(session: Annotated[AsyncSession, Depends(get_session)]) -> UsuariosUnitOfWork:
    return UsuariosUnitOfWork(session)


@router.post("/registro", status_code=status.HTTP_201_CREATED)
async def registro(
    datos: RegistroEntrada,
    uow: Annotated[UsuariosUnitOfWork, Depends(get_uow)],
    settings: Annotated[Settings, Depends(get_settings)],
    semaforo: Annotated[asyncio.Semaphore, Depends(get_semaforo_bcrypt)],
) -> UsuarioSalida:
    try:
        usuario = await service.registrar(uow, datos, settings.BCRYPT_COST, semaforo)
    except service.Conflicto as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return UsuarioSalida.model_validate(usuario)
