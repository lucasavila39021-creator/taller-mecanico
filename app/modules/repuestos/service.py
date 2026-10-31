from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError

from app.core.database import nombre_restriccion
from app.core.paginacion import Paginacion, verificar_pagina
from app.modules.repuestos.models import HistorialPrecio, MovimientoStock, Repuesto
from app.modules.repuestos.repository import StockExcedido
from app.modules.repuestos.schemas import ReponerEntrada, RepuestoCambio, RepuestoEntrada
from app.modules.repuestos.unit_of_work import RepuestosUnitOfWork

MENSAJES_CONFLICTO = {"uq_repuesto_codigo_vigente": "Ya existe un repuesto vigente con ese código"}
MENSAJE_CONFLICTO_GENERICO = "Los datos enviados chocan con lo guardado"


class Conflicto(Exception):
    """Los datos chocan con lo guardado. El router la traduce a un 409."""


class NoEncontrado(Exception):
    """El recurso de la ruta no existe. El router la traduce a un 404."""


class CantidadInvalida(Exception):
    """La reposición no entra en el stock. El router la traduce a un 422."""


def _no_encontrado() -> NoEncontrado:
    return NoEncontrado("El repuesto no existe")


async def listar(
    uow: RepuestosUnitOfWork, q: str | None, paginacion: Paginacion
) -> tuple[Sequence[Repuesto], int]:
    # icontains usa parámetros ligados y autoescape trata % y _ como texto común.
    filtros = [Repuesto.descripcion.icontains(q, autoescape=True)] if q else []
    async with uow:
        total = await uow.repuestos.count(*filtros)
        verificar_pagina(paginacion, total)
        repuestos = await uow.repuestos.get_all(*filtros, offset=paginacion.offset, limit=paginacion.size)
    return repuestos, total


async def obtener(uow: RepuestosUnitOfWork, repuesto_id: int) -> Repuesto:
    async with uow:
        repuesto = await uow.repuestos.get_by_id(repuesto_id)
    if repuesto is None:
        raise _no_encontrado()
    return repuesto


async def crear(uow: RepuestosUnitOfWork, datos: RepuestoEntrada, usuario_id: int) -> Repuesto:
    try:
        async with uow:
            repuesto = await uow.repuestos.add(
                Repuesto(codigo=datos.codigo, descripcion=datos.descripcion, precio=datos.precio, stock=0)
            )
            # RN-14: el stock inicial entra como movimiento. Sin stock no hay movimiento: el CHECK pide distinto de cero.
            if datos.stock_inicial > 0:
                await uow.repuestos.registrar_movimiento(repuesto, datos.stock_inicial, "Stock inicial", usuario_id)
    except IntegrityError as error:
        raise Conflicto(
            MENSAJES_CONFLICTO.get(nombre_restriccion(error), MENSAJE_CONFLICTO_GENERICO)
        ) from None
    return repuesto


# RN-20: el cambio y su línea de historial van en un solo bloque.
async def modificar(
    uow: RepuestosUnitOfWork, repuesto_id: int, datos: RepuestoCambio, usuario_id: int
) -> Repuesto:
    cambios = datos.model_dump(exclude_unset=True)
    async with uow:
        repuesto = await uow.repuestos.get_vigente_bloqueado(repuesto_id)
        if repuesto is None:
            raise _no_encontrado()
        precio_anterior = repuesto.precio
        await uow.repuestos.update(repuesto, cambios)
        # Un PATCH que no cambia el precio no deja línea: el CHECK la rechazaría.
        if "precio" in cambios and cambios["precio"] != precio_anterior:
            await uow.precios.add(
                HistorialPrecio(
                    repuesto_id=repuesto_id,
                    usuario_id=usuario_id,
                    precio_anterior=precio_anterior,
                    precio_nuevo=cambios["precio"],
                )
            )
    return repuesto


async def dar_de_baja(uow: RepuestosUnitOfWork, repuesto_id: int) -> None:
    async with uow:
        repuesto = await uow.repuestos.get_by_id(repuesto_id)
        if repuesto is None:
            raise _no_encontrado()
        await uow.repuestos.soft_delete(repuesto)


async def reponer(
    uow: RepuestosUnitOfWork, repuesto_id: int, datos: ReponerEntrada, usuario_id: int
) -> Repuesto:
    try:
        async with uow:
            repuesto = await uow.repuestos.get_vigente_bloqueado(repuesto_id)
            if repuesto is None:
                raise _no_encontrado()
            await uow.repuestos.registrar_movimiento(repuesto, datos.cantidad, "Reposición", usuario_id)
    except StockExcedido:
        raise CantidadInvalida("La cantidad excede el stock máximo") from None
    return repuesto


async def movimientos(uow: RepuestosUnitOfWork, repuesto_id: int) -> Sequence[MovimientoStock]:
    async with uow:
        if await uow.repuestos.get_by_id(repuesto_id) is None:
            raise _no_encontrado()
        return await uow.movimientos.de_repuesto(repuesto_id)


async def precios(uow: RepuestosUnitOfWork, repuesto_id: int) -> Sequence[HistorialPrecio]:
    async with uow:
        if await uow.repuestos.get_by_id(repuesto_id) is None:
            raise _no_encontrado()
        return await uow.precios.de_repuesto(repuesto_id)
