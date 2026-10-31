from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.dependencies import IdRuta, UsuarioActual, get_usuario_actual, requiere_rol
from app.core.paginacion import Pagina, Paginacion, PaginaInexistente, armar_pagina
from app.modules.ordenes import service
from app.modules.ordenes.models import Estado
from app.modules.ordenes.schemas import EstadoSalida, OrdenDetalle, OrdenEntrada, OrdenResumen
from app.modules.ordenes.unit_of_work import OrdenesUnitOfWork
from app.modules.usuarios.models import Rol


# El router construye el Unit of Work y se lo pasa al servicio sin abrirlo.
async def get_uow(session: Annotated[AsyncSession, Depends(get_session)]) -> OrdenesUnitOfWork:
    return OrdenesUnitOfWork(session)


router = APIRouter(tags=["órdenes"])

Uow = Annotated[OrdenesUnitOfWork, Depends(get_uow)]
Autenticado = Annotated[UsuarioActual, Depends(get_usuario_actual)]
Personal = Annotated[UsuarioActual, Depends(requiere_rol(Rol.ADMIN, Rol.RECEPCION, Rol.MECANICO))]
Mostrador = Annotated[UsuarioActual, Depends(requiere_rol(Rol.RECEPCION, Rol.ADMIN))]
Mecanico = Annotated[UsuarioActual, Depends(requiere_rol(Rol.MECANICO))]


def _traducir(error: Exception) -> HTTPException:
    codigos = {
        service.NoEncontrado: status.HTTP_404_NOT_FOUND,
        service.Conflicto: status.HTTP_409_CONFLICT,
        service.SinPermiso: status.HTTP_403_FORBIDDEN,
        service.TotalExcedido: status.HTTP_422_UNPROCESSABLE_CONTENT,
        PaginaInexistente: status.HTTP_422_UNPROCESSABLE_CONTENT,
    }
    return HTTPException(status_code=codigos[type(error)], detail=str(error))


ERRORES = (service.NoEncontrado, service.Conflicto, service.SinPermiso, service.TotalExcedido, PaginaInexistente)


@router.get("/estados-orden")
async def estados(actual: Autenticado, uow: Uow) -> list[EstadoSalida]:
    return [EstadoSalida.model_validate(e) for e in await service.listar_estados(uow)]


@router.post("/ordenes", status_code=status.HTTP_201_CREATED)
async def crear(datos: OrdenEntrada, actual: Mostrador, uow: Uow) -> OrdenDetalle:
    try:
        return OrdenDetalle.desde_orden(await service.crear(uow, datos, actual.usuario.id))
    except ERRORES as error:
        raise _traducir(error) from None


@router.get("/ordenes")
async def listar(
    actual: Personal,
    uow: Uow,
    paginacion: Annotated[Paginacion, Depends()],
    # El enum es el contrato: un estado que no declara da 422.
    estado: Estado | None = None,
) -> Pagina[OrdenResumen]:
    try:
        ordenes, total = await service.listar(uow, estado, paginacion)
    except ERRORES as error:
        raise _traducir(error) from None
    return armar_pagina([OrdenResumen.desde_orden(o) for o in ordenes], total, paginacion)


@router.get("/mis-ordenes")
async def mis_ordenes(
    actual: Autenticado, uow: Uow, paginacion: Annotated[Paginacion, Depends()]
) -> Pagina[OrdenResumen]:
    try:
        ordenes, total = await service.listar_propias(uow, actual.usuario.id, paginacion)
    except ERRORES as error:
        raise _traducir(error) from None
    return armar_pagina([OrdenResumen.desde_orden(o) for o in ordenes], total, paginacion)


@router.get("/ordenes/{id}")
async def obtener(id: IdRuta, actual: Autenticado, uow: Uow) -> OrdenDetalle:
    try:
        return OrdenDetalle.desde_orden(await service.obtener(uow, id, actual.usuario.id, actual.roles_vigentes))
    except ERRORES as error:
        raise _traducir(error) from None


@router.post("/ordenes/{id}/iniciar")
async def iniciar(id: IdRuta, actual: Mecanico, uow: Uow) -> OrdenDetalle:
    try:
        return OrdenDetalle.desde_orden(await service.iniciar(uow, id, actual.usuario.id))
    except ERRORES as error:
        raise _traducir(error) from None


@router.post("/ordenes/{id}/terminar")
async def terminar(id: IdRuta, actual: Autenticado, uow: Uow, tareas: BackgroundTasks) -> OrdenDetalle:
    try:
        orden = await service.terminar(uow, id, actual.usuario.id, actual.roles_vigentes)
    except ERRORES as error:
        raise _traducir(error) from None
    # Se agenda recién acá: si la operación falló, la excepción ya salió y no hay aviso.
    tareas.add_task(service.avisar_cliente, orden.vehiculo.cliente.nombre, orden.id, orden.vehiculo.patente)
    return OrdenDetalle.desde_orden(orden)


# Sin requiere_rol: la decisión la toma el servicio, porque el dueño no tiene un rol de personal.
@router.post("/ordenes/{id}/cancelar")
async def cancelar(id: IdRuta, actual: Autenticado, uow: Uow) -> OrdenDetalle:
    try:
        return OrdenDetalle.desde_orden(await service.cancelar(uow, id, actual.usuario.id, actual.roles_vigentes))
    except ERRORES as error:
        raise _traducir(error) from None
