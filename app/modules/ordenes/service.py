import asyncio
import logging
from collections.abc import Sequence
from decimal import Decimal

from app.core.paginacion import Paginacion, verificar_pagina
from app.modules.ordenes.models import Estado, EstadoOrden, HistorialEstadoOrden, ItemOrden, OrdenTrabajo
from app.modules.ordenes.repository import OrdenRepository
from app.modules.ordenes.schemas import OrdenEntrada
from app.modules.ordenes.unit_of_work import OrdenesUnitOfWork
from app.modules.repuestos.models import Repuesto
from app.modules.repuestos.repository import StockInsuficiente
from app.modules.usuarios.models import Rol

# El logger de uvicorn es el que ya sale en la consola del servidor.
logger = logging.getLogger("uvicorn.error")

ROLES_PERSONAL = {Rol.ADMIN, Rol.RECEPCION, Rol.MECANICO}
ROLES_CANCELAN = {Rol.RECEPCION, Rol.ADMIN}
# Lo que entra en orden_trabajo.total, NUMERIC(12,2).
TOTAL_MAXIMO = Decimal("9999999999.99")


class Conflicto(Exception):
    """Choca con lo guardado o con el estado. El router la traduce a un 409."""


class NoEncontrado(Exception):
    """La orden de la ruta no existe. El router la traduce a un 404."""


class SinPermiso(Exception):
    """La decisión depende de la orden, no sólo del rol. El router la traduce a un 403."""


class TotalExcedido(Exception):
    """El total no entra en la columna. El router la traduce a un 422."""


async def listar_estados(uow: OrdenesUnitOfWork) -> Sequence[EstadoOrden]:
    async with uow:
        return await uow.estados.get_all()


async def crear(uow: OrdenesUnitOfWork, datos: OrdenEntrada, usuario_id: int) -> OrdenTrabajo:
    async with uow:
        # RN-19: sin catálogo no se puede crear ninguna orden.
        if await uow.estados.get_by_codigo(Estado.PENDIENTE) is None:
            raise Conflicto("El catálogo de estados está vacío")
        # RN-16: los dados de baja no se pueden usar en órdenes nuevas.
        if await uow.vehiculos.get_by_id(datos.vehiculo_id) is None:
            raise Conflicto("El vehículo no existe o fue dado de baja")

        # Todos en una consulta, para que el alta no haga una por cada ítem.
        ids = [item.repuesto_id for item in datos.items]
        repuestos = {r.id: r for r in await uow.repuestos.get_all(Repuesto.id.in_(ids))}

        items = []
        total = Decimal("0")
        for item in datos.items:
            repuesto = repuestos.get(item.repuesto_id)
            if repuesto is None:
                raise Conflicto(f"El repuesto {item.repuesto_id} no existe o fue dado de baja")
            # RN-10: el precio se copia del repuesto y el total lo calcula el servidor.
            items.append(ItemOrden(repuesto_id=repuesto.id, cantidad=item.cantidad, precio_unitario=repuesto.precio))
            total += repuesto.precio * item.cantidad
        if total > TOTAL_MAXIMO:
            raise TotalExcedido("El total de la orden es demasiado grande")

        # Composición: los ítems y la primera línea del historial se guardan junto con la orden.
        orden = await uow.ordenes.add(
            OrdenTrabajo(
                vehiculo_id=datos.vehiculo_id,
                estado=Estado.PENDIENTE,
                falla=datos.falla,
                total=total,
                items=items,
                historial=[HistorialEstadoOrden(hasta_estado=Estado.PENDIENTE, usuario_id=usuario_id)],
            )
        )
    return await _detalle(uow, orden.id)


async def _detalle(uow: OrdenesUnitOfWork, orden_id: int) -> OrdenTrabajo:
    async with uow:
        orden = await uow.ordenes.get_detalle(orden_id)
    if orden is None:
        raise NoEncontrado("La orden no existe")
    return orden


async def listar(
    uow: OrdenesUnitOfWork, estado: Estado | None, paginacion: Paginacion
) -> tuple[Sequence[OrdenTrabajo], int]:
    filtros = [OrdenTrabajo.estado == estado] if estado is not None else []
    return await _pagina(uow, filtros, paginacion)


async def listar_propias(
    uow: OrdenesUnitOfWork, usuario_id: int, paginacion: Paginacion
) -> tuple[Sequence[OrdenTrabajo], int]:
    return await _pagina(uow, [OrdenRepository.filtro_de_usuario(usuario_id)], paginacion)


async def _pagina(
    uow: OrdenesUnitOfWork, filtros: list, paginacion: Paginacion
) -> tuple[Sequence[OrdenTrabajo], int]:
    async with uow:
        total = await uow.ordenes.count(*filtros)
        verificar_pagina(paginacion, total)
        ordenes = await uow.ordenes.get_pagina_con_vehiculo(*filtros, offset=paginacion.offset, limit=paginacion.size)
    return ordenes, total


async def obtener(uow: OrdenesUnitOfWork, orden_id: int, usuario_id: int, roles: list[str]) -> OrdenTrabajo:
    orden = await _detalle(uow, orden_id)
    # RN-17: el personal ve todas; un cliente, sólo las de sus vehículos.
    if not ROLES_PERSONAL & set(roles) and orden.vehiculo.cliente.usuario_id != usuario_id:
        raise SinPermiso("No podés ver esta orden")
    return orden


async def _obtener_bloqueada(uow: OrdenesUnitOfWork, orden_id: int) -> OrdenTrabajo:
    orden = await uow.ordenes.get_bloqueada(orden_id)
    if orden is None:
        raise NoEncontrado("La orden no existe")
    return orden


async def _cambiar_estado(
    uow: OrdenesUnitOfWork, orden: OrdenTrabajo, hasta: Estado, usuario_id: int, **cambios: object
) -> None:
    desde = orden.estado
    await uow.ordenes.update(orden, {"estado": hasta, **cambios})
    await uow.historial.add(
        HistorialEstadoOrden(orden_id=orden.id, desde_estado=desde, hasta_estado=hasta, usuario_id=usuario_id)
    )


async def iniciar(uow: OrdenesUnitOfWork, orden_id: int, usuario_id: int) -> OrdenTrabajo:
    async with uow:
        orden = await _obtener_bloqueada(uow, orden_id)
        if orden.estado != Estado.PENDIENTE:
            raise Conflicto("Sólo se puede iniciar una orden pendiente")
        await _cambiar_estado(uow, orden, Estado.EN_REPARACION, usuario_id, mecanico_id=usuario_id)
    return await _detalle(uow, orden_id)


# RN-13: todo en un solo bloque. Si un repuesto no alcanza, no queda ninguna de las escrituras.
async def terminar(uow: OrdenesUnitOfWork, orden_id: int, usuario_id: int, roles: list[str]) -> OrdenTrabajo:
    async with uow:
        orden = await _obtener_bloqueada(uow, orden_id)
        # El mecánico asignado necesita además seguir teniendo el rol (RN-04).
        es_asignado = orden.mecanico_id == usuario_id and Rol.MECANICO in roles
        if not es_asignado and Rol.ADMIN not in roles:
            raise SinPermiso("Sólo la termina el mecánico asignado o un administrador")
        if orden.estado != Estado.EN_REPARACION:
            raise Conflicto("Sólo se puede terminar una orden en reparación")
        # En orden de id: dos terminaciones con los mismos repuestos no se traban entre sí.
        for item in sorted(orden.items, key=lambda i: i.repuesto_id):
            # Un repuesto dado de baja después del alta igual se descuenta: la orden ya lo usaba.
            repuesto = await uow.repuestos.get_bloqueado_incluyendo_bajas(item.repuesto_id)
            try:
                await uow.repuestos.registrar_movimiento(
                    repuesto, -item.cantidad, f"Salida por la orden {orden_id}", usuario_id, orden_id
                )
            except StockInsuficiente:
                raise Conflicto(f"No hay stock suficiente de {repuesto.descripcion}") from None
        await _cambiar_estado(uow, orden, Estado.TERMINADA, usuario_id)
    return await _detalle(uow, orden_id)


# RN-12: el permiso se evalúa antes que el estado. La ruta no lleva requiere_rol porque
# el dueño no tiene un rol de personal: la decisión depende de la orden.
async def cancelar(uow: OrdenesUnitOfWork, orden_id: int, usuario_id: int, roles: list[str]) -> OrdenTrabajo:
    async with uow:
        orden = await _obtener_bloqueada(uow, orden_id)
        if not ROLES_CANCELAN & set(roles) and await uow.ordenes.usuario_del_dueno(orden.vehiculo_id) != usuario_id:
            raise SinPermiso("No podés cancelar esta orden")
        if orden.estado != Estado.PENDIENTE:
            raise Conflicto("Sólo se puede cancelar una orden pendiente")
        await _cambiar_estado(uow, orden, Estado.CANCELADA, usuario_id)
    return await _detalle(uow, orden_id)


# Corre con BackgroundTasks: después de enviar la respuesta y sólo si la operación se confirmó.
# Recibe textos y no la orden, porque para entonces la sesión de la petición ya no se usa.
async def avisar_cliente(cliente: str, orden_id: int, patente: str) -> None:
    await asyncio.sleep(0.5)
    logger.info("Aviso a %s: la orden %s del vehículo %s está terminada", cliente, orden_id, patente)
