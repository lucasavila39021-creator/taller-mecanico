import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import get_fabrica_sesiones, get_hash_ficticio, get_semaforo_bcrypt, get_usuarios_uow
from app.modules.usuarios import service
from app.modules.usuarios.schemas import LoginEntrada, LoginSalida, MensajeSalida, RegistroEntrada, UsuarioSalida
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork

NOMBRE_COOKIE = "access_token"

router = APIRouter(prefix="/auth", tags=["auth"])


# El token viaja sólo acá: nunca en el cuerpo ni en la cabecera Authorization.
def _poner_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        NOMBRE_COOKIE,
        token,
        max_age=settings.TOKEN_DURACION_SEGUNDOS,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )


@router.post("/registro", status_code=status.HTTP_201_CREATED)
async def registro(
    datos: RegistroEntrada,
    uow: Annotated[UsuariosUnitOfWork, Depends(get_usuarios_uow)],
    settings: Annotated[Settings, Depends(get_settings)],
    semaforo: Annotated[asyncio.Semaphore, Depends(get_semaforo_bcrypt)],
) -> UsuarioSalida:
    try:
        usuario = await service.registrar(uow, datos, settings.BCRYPT_COST, semaforo)
    except service.Conflicto as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return UsuarioSalida.model_validate(usuario)


@router.post("/login")
async def login(
    datos: LoginEntrada,
    request: Request,
    response: Response,
    uow: Annotated[UsuariosUnitOfWork, Depends(get_usuarios_uow)],
    fabrica: Annotated[async_sessionmaker[AsyncSession], Depends(get_fabrica_sesiones)],
    settings: Annotated[Settings, Depends(get_settings)],
    semaforo: Annotated[asyncio.Semaphore, Depends(get_semaforo_bcrypt)],
    hash_ficticio: Annotated[str, Depends(get_hash_ficticio)],
) -> LoginSalida:
    ip = request.client.host if request.client else "desconocida"
    try:
        token, usuario = await service.login(uow, fabrica, datos, ip, settings, semaforo, hash_ficticio)
    except service.DemasiadosIntentos as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos: probá de nuevo más tarde",
            headers={"Retry-After": str(error.reintentar_en)},
        ) from None
    except service.CredencialesInvalidas:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Correo o contraseña incorrectos"
        ) from None
    _poner_cookie(response, token, settings)
    return LoginSalida(
        mensaje="Sesión iniciada",
        debe_cambiar_password=usuario.debe_cambiar_password,
        expira_en_segundos=settings.TOKEN_DURACION_SEGUNDOS,
    )


@router.post("/logout")
async def logout(response: Response, settings: Annotated[Settings, Depends(get_settings)]) -> MensajeSalida:
    response.delete_cookie(NOMBRE_COOKIE, httponly=True, samesite="lax", secure=settings.COOKIE_SECURE)
    return MensajeSalida(mensaje="Sesión cerrada")
