import asyncio

from sqlalchemy.exc import IntegrityError

from app.core.database import nombre_restriccion
from app.core.security import hashear_password
from app.modules.clientes.models import Cliente
from app.modules.usuarios.models import AsignacionRol, EventoSeguridad, Rol, Usuario
from app.modules.usuarios.schemas import RegistroEntrada
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork

# Cada restricción de la base con su mensaje propio (RN-18: nunca el texto de la base).
MENSAJES_CONFLICTO = {
    "uq_usuario_email": "Ya existe un usuario con ese correo",
    "uq_cliente_documento": "Ya existe un cliente con ese documento",
}
MENSAJE_CONFLICTO_GENERICO = "Los datos enviados chocan con lo guardado"


class Conflicto(Exception):
    """Los datos chocan con lo guardado. Sin HTTP: el router la traduce a un 409."""


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
