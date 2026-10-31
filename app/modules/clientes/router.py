from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.dependencies import IdRuta, UsuarioActual, get_usuario_actual, requiere_rol
from app.modules.clientes import service
from app.modules.clientes.schemas import ClienteDetalle, ClienteEntrada, ClienteSalida, VehiculoEntrada, VehiculoSalida
from app.modules.clientes.unit_of_work import ClientesUnitOfWork
from app.modules.usuarios.models import Rol


# El router construye el Unit of Work y se lo pasa al servicio sin abrirlo.
async def get_uow(session: Annotated[AsyncSession, Depends(get_session)]) -> ClientesUnitOfWork:
    return ClientesUnitOfWork(session)


router = APIRouter(tags=["clientes"])

Uow = Annotated[ClientesUnitOfWork, Depends(get_uow)]
Mostrador = Annotated[UsuarioActual, Depends(requiere_rol(Rol.RECEPCION, Rol.ADMIN))]


@router.post("/clientes", status_code=status.HTTP_201_CREATED)
async def crear_cliente(datos: ClienteEntrada, actual: Mostrador, uow: Uow) -> ClienteSalida:
    try:
        cliente = await service.crear_cliente(uow, datos)
    except service.Conflicto as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return ClienteSalida.model_validate(cliente)


@router.get("/clientes/{id}")
async def obtener_cliente(id: IdRuta, actual: Mostrador, uow: Uow) -> ClienteDetalle:
    try:
        cliente = await service.obtener_cliente(uow, id)
    except service.NoEncontrado as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    return ClienteDetalle.model_validate(cliente)


@router.post("/clientes/{id}/vehiculos", status_code=status.HTTP_201_CREATED)
async def crear_vehiculo(id: IdRuta, datos: VehiculoEntrada, actual: Mostrador, uow: Uow) -> VehiculoSalida:
    try:
        vehiculo = await service.crear_vehiculo(uow, id, datos)
    except service.NoEncontrado as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    except service.Conflicto as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return VehiculoSalida.model_validate(vehiculo)


@router.delete("/vehiculos/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def dar_de_baja_vehiculo(id: IdRuta, actual: Mostrador, uow: Uow) -> None:
    try:
        await service.dar_de_baja_vehiculo(uow, id)
    except service.NoEncontrado as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    except service.Conflicto as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None


@router.get("/mis-vehiculos")
async def mis_vehiculos(
    actual: Annotated[UsuarioActual, Depends(get_usuario_actual)], uow: Uow
) -> list[VehiculoSalida]:
    vehiculos = await service.mis_vehiculos(uow, actual.usuario.id)
    return [VehiculoSalida.model_validate(v) for v in vehiculos]
