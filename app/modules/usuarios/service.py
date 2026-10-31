import asyncio
import math
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings
from app.core.database import nombre_restriccion
from app.core.security import crear_token, hashear_password, verificar_password
from app.modules.clientes.models import Cliente
from app.modules.usuarios.models import AsignacionRol, EventoSeguridad, IntentoAcceso, Rol, Usuario
from app.modules.usuarios.repository import IntentoAccesoRepository
from app.modules.usuarios.schemas import CambioPasswordEntrada, LoginEntrada, RegistroEntrada
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork

MAXIMO_FALLOS_LOGIN = 5
VENTANA_FALLOS_SEGUNDOS = 60

# Cada restricción de la base con su mensaje propio (RN-18: nunca el texto de la base).
MENSAJES_CONFLICTO = {
    "uq_usuario_email": "Ya existe un usuario con ese correo",
    "uq_cliente_documento": "Ya existe un cliente con ese documento",
}
MENSAJE_CONFLICTO_GENERICO = "Los datos enviados chocan con lo guardado"


class Conflicto(Exception):
    """Los datos chocan con lo guardado. Sin HTTP: el router la traduce a un 409."""


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
