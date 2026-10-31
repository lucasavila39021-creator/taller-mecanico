import asyncio
import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings
from app.core.database import nombre_restriccion
from app.core.paginacion import Paginacion, verificar_pagina
from app.core.security import crear_token, hashear_password, verificar_password
from app.modules.clientes.models import Cliente
from app.modules.usuarios.models import AsignacionRol, EventoSeguridad, IntentoAcceso, Rol, Usuario
from app.modules.usuarios.repository import IntentoAccesoRepository
from app.modules.usuarios.schemas import (
    AltaPersonalEntrada,
    AsignarRolEntrada,
    CambioPasswordEntrada,
    LoginEntrada,
    RegistroEntrada,
)
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork

MAXIMO_FALLOS_LOGIN = 5
VENTANA_FALLOS_SEGUNDOS = 60

# Cada restricción de la base con su mensaje propio (RN-18: nunca el texto de la base).
MENSAJES_CONFLICTO = {
    "uq_usuario_email": "Ya existe un usuario con ese correo",
    "uq_cliente_documento": "Ya existe un cliente con ese documento",
    "uq_asignacion_rol_usuario_rol_abierta": "El usuario ya tiene ese rol asignado",
}
MENSAJE_CONFLICTO_GENERICO = "Los datos enviados chocan con lo guardado"


class Conflicto(Exception):
    """Los datos chocan con lo guardado. Sin HTTP: el router la traduce a un 409."""


class NoEncontrado(Exception):
    """El recurso de la ruta no existe. El router la traduce a un 404."""


class CredencialesInvalidas(Exception):
    """Mismo error exista o no el correo (RN-09). El router la traduce a un 401."""


class DemasiadosIntentos(Exception):
    """Se superó el límite de RN-08. El router la traduce a un 429."""

    def __init__(self, reintentar_en: int) -> None:
        super().__init__()
        self.reintentar_en = reintentar_en


def _traducir_conflicto(error: IntegrityError) -> Conflicto:
    return Conflicto(MENSAJES_CONFLICTO.get(nombre_restriccion(error), MENSAJE_CONFLICTO_GENERICO))


async def registrar(
    uow: UsuariosUnitOfWork,
    datos: RegistroEntrada,
    costo: int,
    semaforo: asyncio.Semaphore,
) -> Usuario:
    # Antes de abrir el bloque: adentro, la conexión quedaría tomada 300 ms sin usar la base.
    password_hash = await hashear_password(datos.password, costo, semaforo)

    # RN-02: las cuatro escrituras van en un solo bloque. La unicidad la garantiza la base, sin
    # consulta previa: entre preguntar y guardar podría entrar otro pedido con el mismo dato.
    # Por eso un documento que ya es de un cliente da 409 y la ficha existente no se toca.
    try:
        async with uow:
            usuario = await uow.usuarios.add(
                Usuario(email=datos.email, nombre=datos.nombre, password_hash=password_hash)
            )
            await uow.roles.add(AsignacionRol(usuario_id=usuario.id, rol=Rol.CLIENTE))
            await uow.clientes.add(
                Cliente(
                    usuario_id=usuario.id,
                    nombre=datos.nombre,
                    documento=datos.documento,
                    telefono=datos.telefono,
                )
            )
            await uow.eventos.add(EventoSeguridad(actor=datos.email, accion="Alta de usuario por auto-registro"))
    except IntegrityError as error:
        raise _traducir_conflicto(error) from None
    return usuario


# Sesión y transacción propias: es la única escritura del sistema que no comparte la transacción
# de su petición, porque el fallo que se quiere contar es el mismo que la revierte.
# Costo: deja filas aunque la petición falle, y cada intento usa una conexión más.
async def _anotar_intento(
    fabrica: async_sessionmaker[AsyncSession], email: str, ip: str, exito: bool
) -> None:
    async with fabrica() as session, session.begin():
        await IntentoAccesoRepository(session).add(IntentoAcceso(email=email, ip=ip, exito=exito))


async def login(
    uow: UsuariosUnitOfWork,
    fabrica: async_sessionmaker[AsyncSession],
    datos: LoginEntrada,
    ip: str,
    settings: Settings,
    semaforo: asyncio.Semaphore,
    hash_ficticio: str,
) -> tuple[str, Usuario]:
    ahora = datetime.now(UTC)
    # Primero el límite (RN-08): cuesta una consulta y no calcula ningún hash.
    # El bloque se cierra antes de verificar, para no tener la conexión tomada durante bcrypt.
    async with uow:
        desde = ahora - timedelta(seconds=VENTANA_FALLOS_SEGUNDOS)
        fallos, primero = await uow.intentos.fallos_recientes(datos.email, ip, desde)
        if fallos >= MAXIMO_FALLOS_LOGIN:
            faltan = (primero + timedelta(seconds=VENTANA_FALLOS_SEGUNDOS) - ahora).total_seconds()
            raise DemasiadosIntentos(max(1, math.ceil(faltan)))
        usuario = await uow.usuarios.get_by_email(datos.email)

    # RN-09: si el correo no existe se verifica igual, contra el hash ficticio, para tardar lo mismo.
    password_hash = usuario.password_hash if usuario is not None else hash_ficticio
    correcta = await verificar_password(datos.password, password_hash, semaforo)

    if usuario is None or not correcta or not usuario.activo:
        await _anotar_intento(fabrica, datos.email, ip, False)
        raise CredencialesInvalidas

    async with uow:
        roles = await uow.roles.roles_vigentes(usuario.id, datetime.now(UTC))
    await _anotar_intento(fabrica, datos.email, ip, True)
    return crear_token(usuario.id, roles, settings), usuario


async def cambiar_password(
    uow: UsuariosUnitOfWork,
    usuario: Usuario,
    datos: CambioPasswordEntrada,
    settings: Settings,
    semaforo: asyncio.Semaphore,
) -> str:
    if not await verificar_password(datos.password_actual, usuario.password_hash, semaforo):
        raise CredencialesInvalidas
    password_hash = await hashear_password(datos.password_nueva, settings.BCRYPT_COST, semaforo)

    async with uow:
        await uow.usuarios.update(
            usuario,
            {
                "password_hash": password_hash,
                "debe_cambiar_password": False,
                "password_cambiada_en": datetime.now(UTC),
            },
        )
        await uow.eventos.add(EventoSeguridad(actor=usuario.email, accion="Cambio de contraseña"))
        roles = await uow.roles.roles_vigentes(usuario.id, datetime.now(UTC))
    # RN-07: se emite después de anotar el cambio. Las sesiones anteriores dejan de valer y esta no.
    return crear_token(usuario.id, roles, settings)


async def crear_personal(
    uow: UsuariosUnitOfWork,
    datos: AltaPersonalEntrada,
    actor: Usuario,
    costo: int,
    semaforo: asyncio.Semaphore,
) -> Usuario:
    password_hash = await hashear_password(datos.password, costo, semaforo)
    try:
        async with uow:
            # La contraseña es provisoria: la persona tiene que cambiarla al entrar.
            usuario = await uow.usuarios.add(
                Usuario(
                    email=datos.email,
                    nombre=datos.nombre,
                    password_hash=password_hash,
                    debe_cambiar_password=True,
                )
            )
            await uow.eventos.add(EventoSeguridad(actor=actor.email, accion=f"Alta de personal: {usuario.email}"))
    except IntegrityError as error:
        raise _traducir_conflicto(error) from None
    return usuario


async def _obtener_usuario(uow: UsuariosUnitOfWork, usuario_id: int) -> Usuario:
    usuario = await uow.usuarios.get_by_id(usuario_id)
    if usuario is None:
        raise NoEncontrado("El usuario no existe")
    return usuario


async def listar_roles(uow: UsuariosUnitOfWork, usuario_id: int) -> Sequence[AsignacionRol]:
    async with uow:
        await _obtener_usuario(uow, usuario_id)
        return await uow.roles.de_usuario(usuario_id)


async def asignar_rol(
    uow: UsuariosUnitOfWork, usuario_id: int, datos: AsignarRolEntrada, actor: Usuario
) -> AsignacionRol:
    ahora = datetime.now(UTC)
    try:
        async with uow:
            usuario = await _obtener_usuario(uow, usuario_id)
            # Reasignar un rol vencido cierra la fila anterior y abre una nueva.
            # Una abierta y vigente no se toca: la rechaza el índice único parcial (RN-03).
            abierta = await uow.roles.abierta(usuario_id, datos.rol)
            if abierta is not None and abierta.vence_en is not None and abierta.vence_en <= ahora:
                await uow.roles.update(abierta, {"revocada_en": ahora})
            asignacion = await uow.roles.add(
                AsignacionRol(usuario_id=usuario_id, rol=datos.rol, vence_en=datos.vence_en, otorgada_por=actor.id)
            )
            await uow.eventos.add(
                EventoSeguridad(actor=actor.email, accion=f"Asignación del rol {datos.rol} a {usuario.email}")
            )
    except IntegrityError as error:
        raise _traducir_conflicto(error) from None
    return asignacion


# RN-05: el sistema nunca queda sin administradores vigentes.
async def _exigir_otro_administrador(uow: UsuariosUnitOfWork, usuario_id: int) -> None:
    await uow.roles.bloquear_administradores()
    administradores = await uow.roles.ids_administradores_vigentes(datetime.now(UTC))
    if not administradores - {usuario_id}:
        raise Conflicto("El sistema no puede quedar sin administradores")


async def revocar_rol(uow: UsuariosUnitOfWork, usuario_id: int, rol: Rol, actor: Usuario) -> AsignacionRol:
    async with uow:
        usuario = await _obtener_usuario(uow, usuario_id)
        if rol == Rol.ADMIN:
            if usuario_id == actor.id:
                raise Conflicto("No podés revocarte tu propio rol ADMIN")
            await _exigir_otro_administrador(uow, usuario_id)
        abierta = await uow.roles.abierta(usuario_id, rol)
        if abierta is None:
            raise NoEncontrado("El usuario no tiene ese rol asignado")
        # La fila no se borra: queda el historial de quién tuvo qué rol y hasta cuándo.
        await uow.roles.update(abierta, {"revocada_en": datetime.now(UTC)})
        await uow.eventos.add(EventoSeguridad(actor=actor.email, accion=f"Revocación del rol {rol} a {usuario.email}"))
    return abierta


async def listar_eventos(
    uow: UsuariosUnitOfWork, paginacion: Paginacion
) -> tuple[Sequence[EventoSeguridad], int]:
    async with uow:
        total = await uow.eventos.count()
        verificar_pagina(paginacion, total)
        eventos = await uow.eventos.get_all(offset=paginacion.offset, limit=paginacion.size)
    return eventos, total
