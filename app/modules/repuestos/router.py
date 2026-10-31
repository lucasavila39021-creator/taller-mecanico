from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AfterValidator
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.dependencies import IdRuta, UsuarioActual, requiere_rol
from app.core.paginacion import Pagina, Paginacion, PaginaInexistente, armar_pagina
from app.modules.repuestos import service
from app.modules.repuestos.schemas import (
    MovimientoSalida,
    PrecioSalida,
    ReponerEntrada,
    RepuestoCambio,
    RepuestoEntrada,
    RepuestoSalida,
)
from app.modules.repuestos.unit_of_work import RepuestosUnitOfWork
from app.modules.usuarios.models import Rol
from app.modules.usuarios.schemas import sin_caracter_nulo


# El router construye el Unit of Work y se lo pasa al servicio sin abrirlo.
async def get_uow(session: Annotated[AsyncSession, Depends(get_session)]) -> RepuestosUnitOfWork:
    return RepuestosUnitOfWork(session)


router = APIRouter(prefix="/repuestos", tags=["repuestos"])

Uow = Annotated[RepuestosUnitOfWork, Depends(get_uow)]
Administrador = Annotated[UsuarioActual, Depends(requiere_rol(Rol.ADMIN))]
Personal = Annotated[UsuarioActual, Depends(requiere_rol(Rol.ADMIN, Rol.RECEPCION, Rol.MECANICO))]


def _no_encontrado(error: service.NoEncontrado) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.get("")
async def listar(
    actual: Personal,
    uow: Uow,
    paginacion: Annotated[Paginacion, Depends()],
    q: Annotated[str | None, Query(), AfterValidator(lambda v: v and sin_caracter_nulo(v))] = None,
) -> Pagina[RepuestoSalida]:
    try:
        repuestos, total = await service.listar(uow, q, paginacion)
    except PaginaInexistente as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    return armar_pagina([RepuestoSalida.model_validate(r) for r in repuestos], total, paginacion)


@router.get("/{id}")
async def obtener(id: IdRuta, actual: Personal, uow: Uow) -> RepuestoSalida:
    try:
        return RepuestoSalida.model_validate(await service.obtener(uow, id))
    except service.NoEncontrado as error:
        raise _no_encontrado(error) from None


@router.post("", status_code=status.HTTP_201_CREATED)
async def crear(datos: RepuestoEntrada, actual: Administrador, uow: Uow) -> RepuestoSalida:
    try:
        repuesto = await service.crear(uow, datos, actual.usuario.id)
    except service.Conflicto as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return RepuestoSalida.model_validate(repuesto)


@router.patch("/{id}")
async def modificar(id: IdRuta, datos: RepuestoCambio, actual: Administrador, uow: Uow) -> RepuestoSalida:
    try:
        return RepuestoSalida.model_validate(await service.modificar(uow, id, datos, actual.usuario.id))
    except service.NoEncontrado as error:
        raise _no_encontrado(error) from None


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def dar_de_baja(id: IdRuta, actual: Administrador, uow: Uow) -> None:
    try:
        await service.dar_de_baja(uow, id)
    except service.NoEncontrado as error:
        raise _no_encontrado(error) from None


@router.post("/{id}/reponer")
async def reponer(id: IdRuta, datos: ReponerEntrada, actual: Administrador, uow: Uow) -> RepuestoSalida:
    try:
        return RepuestoSalida.model_validate(await service.reponer(uow, id, datos, actual.usuario.id))
    except service.NoEncontrado as error:
        raise _no_encontrado(error) from None
    except service.CantidadInvalida as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None


@router.get("/{id}/movimientos")
async def movimientos(id: IdRuta, actual: Administrador, uow: Uow) -> list[MovimientoSalida]:
    try:
        return [MovimientoSalida.model_validate(m) for m in await service.movimientos(uow, id)]
    except service.NoEncontrado as error:
        raise _no_encontrado(error) from None


@router.get("/{id}/precios")
async def precios(id: IdRuta, actual: Administrador, uow: Uow) -> list[PrecioSalida]:
    try:
        return [PrecioSalida.model_validate(p) for p in await service.precios(uow, id)]
    except service.NoEncontrado as error:
        raise _no_encontrado(error) from None
