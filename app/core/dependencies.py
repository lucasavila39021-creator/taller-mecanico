import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Path, Request, status
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.security import NOMBRE_COOKIE, TokenInvalido, verificar_token
from app.modules.usuarios.models import Rol, Usuario
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork

# Un id más grande que un INTEGER de PostgreSQL sería un 500 en lugar de un 422.
IdRuta = Annotated[int, Path(ge=1, le=2_147_483_647)]


async def get_semaforo_bcrypt(request: Request) -> asyncio.Semaphore:
    return request.app.state.semaforo_bcrypt


async def get_hash_ficticio(request: Request) -> str:
    return request.app.state.hash_ficticio


async def get_fabrica_sesiones(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.fabrica_sesiones


# El router construye el Unit of Work y se lo pasa al servicio sin abrirlo.
async def get_usuarios_uow(session: Annotated[AsyncSession, Depends(get_session)]) -> UsuariosUnitOfWork:
    return UsuariosUnitOfWork(session)


@dataclass
class UsuarioActual:
    usuario: Usuario
    # Los que deciden los permisos (RN-04).
    roles_vigentes: list[str]
    # Los que decía el token al emitirse: sólo informativos.
    roles_token: list[str]


def _no_autenticado() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")


# El token se lee sólo de la cookie: la cabecera Authorization no se mira.
async def get_usuario_actual(
    request: Request,
    uow: Annotated[UsuariosUnitOfWork, Depends(get_usuarios_uow)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UsuarioActual:
    token = request.cookies.get(NOMBRE_COOKIE)
    if token is None:
        raise _no_autenticado()
    try:
        contenido = verificar_token(token, settings)
        usuario_id = int(contenido["sub"])
    except (TokenInvalido, ValueError):
        raise _no_autenticado() from None

    # El bloque se cierra acá para no dejar la conexión tomada mientras corre el handler.
    async with uow:
        usuario = await uow.usuarios.get_by_id(usuario_id)
        roles = await uow.roles.roles_vigentes(usuario_id, datetime.now(UTC))

    if usuario is None or not usuario.activo:
        raise _no_autenticado()
    # RN-07: la comparación es sin truncar. El token del propio cambio se emite después de anotarlo.
    cambiada_en = usuario.password_cambiada_en
    if cambiada_en is not None and contenido["iat"] < cambiada_en.timestamp():
        raise _no_autenticado()
    return UsuarioActual(usuario=usuario, roles_vigentes=roles, roles_token=contenido["roles"])


# RN-06: se monta una sola vez, en el grupo protegido de main.py.
async def exigir_password_al_dia(actual: Annotated[UsuarioActual, Depends(get_usuario_actual)]) -> None:
    if actual.usuario.debe_cambiar_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Tenés que cambiar la contraseña antes de continuar"
        )


# RN-04: decide con los roles vigentes en la base, no con los del token.
def requiere_rol(*roles: Rol) -> Callable[..., Awaitable[UsuarioActual]]:
    async def verificar(actual: Annotated[UsuarioActual, Depends(get_usuario_actual)]) -> UsuarioActual:
        if not set(actual.roles_vigentes) & set(roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenés permiso para esta operación")
        return actual

    return verificar
