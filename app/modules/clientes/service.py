from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError

from app.core.database import nombre_restriccion
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.clientes.schemas import ClienteEntrada, VehiculoEntrada
from app.modules.clientes.unit_of_work import ClientesUnitOfWork

MENSAJES_CONFLICTO = {
    "uq_cliente_documento": "Ya existe un cliente con ese documento",
    "uq_vehiculo_patente_vigente": "Ya existe un vehículo vigente con esa patente",
}
MENSAJE_CONFLICTO_GENERICO = "Los datos enviados chocan con lo guardado"


class Conflicto(Exception):
    """Los datos chocan con lo guardado. El router la traduce a un 409."""


class NoEncontrado(Exception):
    """El recurso de la ruta no existe. El router la traduce a un 404."""


def _traducir_conflicto(error: IntegrityError) -> Conflicto:
    return Conflicto(MENSAJES_CONFLICTO.get(nombre_restriccion(error), MENSAJE_CONFLICTO_GENERICO))


async def crear_cliente(uow: ClientesUnitOfWork, datos: ClienteEntrada) -> Cliente:
    try:
        async with uow:
            return await uow.clientes.add(Cliente(**datos.model_dump()))
    except IntegrityError as error:
        raise _traducir_conflicto(error) from None


async def obtener_cliente(uow: ClientesUnitOfWork, cliente_id: int) -> Cliente:
    async with uow:
        cliente = await uow.clientes.get_con_vehiculos_vigentes(cliente_id)
    if cliente is None:
        raise NoEncontrado("El cliente no existe")
    return cliente


async def crear_vehiculo(uow: ClientesUnitOfWork, cliente_id: int, datos: VehiculoEntrada) -> Vehiculo:
    try:
        async with uow:
            if await uow.clientes.get_by_id(cliente_id) is None:
                raise NoEncontrado("El cliente no existe")
            return await uow.vehiculos.add(Vehiculo(cliente_id=cliente_id, **datos.model_dump()))
    except IntegrityError as error:
        raise _traducir_conflicto(error) from None


async def dar_de_baja_vehiculo(uow: ClientesUnitOfWork, vehiculo_id: int) -> None:
    async with uow:
        vehiculo = await uow.vehiculos.get_by_id(vehiculo_id)
        if vehiculo is None:
            raise NoEncontrado("El vehículo no existe")
        if await uow.vehiculos.tiene_ordenes_abiertas(vehiculo_id):
            raise Conflicto("El vehículo tiene órdenes abiertas")
        await uow.vehiculos.soft_delete(vehiculo)


# RN-17: lo propio sólo pide estar autenticado. Sin ficha de cliente, la lista queda vacía.
async def mis_vehiculos(uow: ClientesUnitOfWork, usuario_id: int) -> Sequence[Vehiculo]:
    async with uow:
        return await uow.vehiculos.vigentes_de_usuario(usuario_id)
