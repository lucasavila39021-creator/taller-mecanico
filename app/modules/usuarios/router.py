import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import (
    IdRuta,
    UsuarioActual,
    get_fabrica_sesiones,
    get_hash_ficticio,
    get_semaforo_bcrypt,
    get_usuario_actual,
    get_usuarios_uow,
    requiere_rol,
)
from app.core.paginacion import Pagina, Paginacion, PaginaInexistente, armar_pagina
from app.core.security import NOMBRE_COOKIE
from app.modules.usuarios import service
from app.modules.usuarios.models import Rol
from app.modules.usuarios.schemas import (
    AltaPersonalEntrada,
    AsignacionSalida,
    AsignarRolEntrada,
    CambioPasswordEntrada,
    EventoSalida,
    LoginEntrada,
    LoginSalida,
    MensajeSalida,
    RegistroEntrada,
    UsuarioSalida,
    YoSalida,
)
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork

# Va en el grupo abierto de main.py.
router = APIRouter(prefix="/auth", tags=["auth"])
# Va en el grupo protegido de main.py.
router_admin = APIRouter(tags=["administración"])

Administrador = Annotated[UsuarioActual, Depends(requiere_rol(Rol.ADMIN))]
UowUsuarios = Annotated[UsuariosUnitOfWork, Depends(get_usuarios_uow)]


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


@router.get("/yo")
async def yo(actual: Annotated[UsuarioActual, Depends(get_usuario_actual)]) -> YoSalida:
    return YoSalida(
        id=actual.usuario.id,
        email=actual.usuario.email,
        nombre=actual.usuario.nombre,
        debe_cambiar_password=actual.usuario.debe_cambiar_password,
        roles_vigentes=actual.roles_vigentes,
        roles_token=actual.roles_token,
    )


@router.post("/cambiar-password")
async def cambiar_password(
    datos: CambioPasswordEntrada,
    response: Response,
    actual: Annotated[UsuarioActual, Depends(get_usuario_actual)],
    uow: Annotated[UsuariosUnitOfWork, Depends(get_usuarios_uow)],
    settings: Annotated[Settings, Depends(get_settings)],
    semaforo: Annotated[asyncio.Semaphore, Depends(get_semaforo_bcrypt)],
) -> MensajeSalida:
    try:
        token = await service.cambiar_password(uow, actual.usuario, datos, settings, semaforo)
    except service.CredencialesInvalidas:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="La contraseña actual es incorrecta"
        ) from None
    _poner_cookie(response, token, settings)
    return MensajeSalida(mensaje="Contraseña cambiada")


@router_admin.post("/usuarios", status_code=status.HTTP_201_CREATED)
async def alta_personal(
    datos: AltaPersonalEntrada,
    actual: Administrador,
    uow: UowUsuarios,
    settings: Annotated[Settings, Depends(get_settings)],
    semaforo: Annotated[asyncio.Semaphore, Depends(get_semaforo_bcrypt)],
) -> UsuarioSalida:
    try:
        usuario = await service.crear_personal(uow, datos, actual.usuario, settings.BCRYPT_COST, semaforo)
    except service.Conflicto as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return UsuarioSalida.model_validate(usuario)


@router_admin.get("/usuarios/{id}/roles")
async def roles_de_usuario(id: IdRuta, actual: Administrador, uow: UowUsuarios) -> list[AsignacionSalida]:
    try:
        asignaciones = await service.listar_roles(uow, id)
    except service.NoEncontrado as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    return [AsignacionSalida.model_validate(a) for a in asignaciones]


@router_admin.post("/usuarios/{id}/roles", status_code=status.HTTP_201_CREATED)
async def asignar_rol(
    id: IdRuta, datos: AsignarRolEntrada, actual: Administrador, uow: UowUsuarios
) -> AsignacionSalida:
    try:
        asignacion = await service.asignar_rol(uow, id, datos, actual.usuario)
    except service.NoEncontrado as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    except service.Conflicto as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return AsignacionSalida.model_validate(asignacion)


@router_admin.delete("/usuarios/{id}/roles/{rol}")
async def revocar_rol(id: IdRuta, rol: Rol, actual: Administrador, uow: UowUsuarios) -> AsignacionSalida:
    try:
        asignacion = await service.revocar_rol(uow, id, rol, actual.usuario)
    except service.NoEncontrado as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    except service.Conflicto as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return AsignacionSalida.model_validate(asignacion)


@router_admin.post("/usuarios/{id}/desactivar")
async def desactivar_usuario(id: IdRuta, actual: Administrador, uow: UowUsuarios) -> UsuarioSalida:
    try:
        usuario = await service.desactivar_usuario(uow, id, actual.usuario)
    except service.NoEncontrado as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    except service.Conflicto as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return UsuarioSalida.model_validate(usuario)


@router_admin.get("/eventos")
async def eventos(
    paginacion: Annotated[Paginacion, Depends()], actual: Administrador, uow: UowUsuarios
) -> Pagina[EventoSalida]:
    try:
        filas, total = await service.listar_eventos(uow, paginacion)
    except PaginaInexistente as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    return armar_pagina([EventoSalida.model_validate(f) for f in filas], total, paginacion)
