"""Deja la base en el estado inicial conocido que usan los casos de prueba."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.database import crear_fabrica_sesiones, crear_motor
from app.core.security import hashear_password
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import Estado, EstadoOrden, HistorialEstadoOrden, ItemOrden, OrdenTrabajo
from app.modules.repuestos.models import HistorialPrecio, MovimientoStock, Repuesto
from app.modules.usuarios.models import AsignacionRol, EventoSeguridad, Rol, Usuario

# Contraseña de mentira: sólo vive en este archivo.
PASSWORD = "Taller2026!"

# Fecha fija para que dos corridas dejen exactamente el mismo resultado.
FECHA_CARGA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


async def vaciar_tablas(session: AsyncSession) -> None:
    # TRUNCATE y no DELETE: el disparador de sólo agregado rechaza los DELETE.
    # RESTART IDENTITY: un ROLLBACK no devuelve los números, y los casos de prueba usan ids fijos.
    # La metadata no incluye alembic_version, así que la versión del esquema no se toca.
    tablas = ", ".join(tabla.name for tabla in SQLModel.metadata.sorted_tables)
    await session.exec(text(f"TRUNCATE {tablas} RESTART IDENTITY"))


async def cargar_estados(session: AsyncSession) -> None:
    session.add_all(
        [
            EstadoOrden(codigo=Estado.PENDIENTE, descripcion="Esperando que un mecánico la inicie", posicion=1, es_final=False),
            EstadoOrden(codigo=Estado.EN_REPARACION, descripcion="Un mecánico la está reparando", posicion=2, es_final=False),
            EstadoOrden(codigo=Estado.TERMINADA, descripcion="Reparación terminada", posicion=3, es_final=True),
            EstadoOrden(codigo=Estado.CANCELADA, descripcion="Cancelada antes de iniciarse", posicion=4, es_final=True),
        ]
    )
    await session.flush()


async def cargar_usuarios(session: AsyncSession, costo: int) -> dict[str, Usuario]:
    personas = [
        ("admin@example.com", "Ana Admin", Rol.ADMIN, False),
        ("admin2@example.com", "Andrés Admin", Rol.ADMIN, False),
        ("recepcion@example.com", "Rita Recepción", Rol.RECEPCION, False),
        ("mecanico@example.com", "Mario Mecánico", Rol.MECANICO, False),
        ("mecanico2@example.com", "Marta Mecánica", Rol.MECANICO, False),
        ("cliente@example.com", "Laura Cliente", Rol.CLIENTE, False),
        ("nuevo@example.com", "Nico Nuevo", Rol.MECANICO, True),
    ]
    usuarios = {}
    for email, nombre, rol, debe_cambiar in personas:
        usuario = Usuario(
            email=email,
            nombre=nombre,
            password_hash=hashear_password(PASSWORD, costo),
            debe_cambiar_password=debe_cambiar,
        )
        session.add(usuario)
        await session.flush()
        session.add(AsignacionRol(usuario_id=usuario.id, rol=rol, desde=FECHA_CARGA))
        usuarios[email] = usuario
    await session.flush()
    return usuarios


async def cargar_clientes(session: AsyncSession, usuarios: dict[str, Usuario]) -> dict[str, Vehiculo]:
    laura = Cliente(
        usuario_id=usuarios["cliente@example.com"].id,
        nombre="Laura Cliente",
        documento="30111222",
        telefono="2615550101",
    )
    jorge = Cliente(nombre="Jorge Gómez", documento="28333444", telefono="2615550102")
    session.add_all([laura, jorge])
    await session.flush()

    vehiculos = {
        "laura_1": Vehiculo(cliente_id=laura.id, patente="AB123CD", marca="Toyota", modelo="Corolla", anio=2018),
        "laura_2": Vehiculo(cliente_id=laura.id, patente="AC456EF", marca="Ford", modelo="Focus", anio=2019),
        "jorge": Vehiculo(cliente_id=jorge.id, patente="AD789GH", marca="Renault", modelo="Kangoo", anio=2015),
    }
    session.add_all(vehiculos.values())
    await session.flush()
    return vehiculos


async def cargar_repuestos(session: AsyncSession, admin: Usuario) -> dict[str, Repuesto]:
    repuestos = {
        "filtro": Repuesto(codigo="FIL-001", descripcion="Filtro de aceite", precio=Decimal("8500.00"), stock=10),
        "pastillas": Repuesto(codigo="FRE-010", descripcion="Pastillas de freno delanteras", precio=Decimal("32000.00"), stock=4),
        "bujia": Repuesto(codigo="BUJ-020", descripcion="Bujía", precio=Decimal("6000.00"), stock=2),
        "aceite": Repuesto(codigo="ACE-530", descripcion="Aceite 5W30 por litro", precio=Decimal("12000.00"), stock=20),
    }
    session.add_all(repuestos.values())
    await session.flush()

    # RN-14: cada stock queda respaldado por un movimiento.
    session.add_all(
        MovimientoStock(
            repuesto_id=repuesto.id,
            usuario_id=admin.id,
            cantidad=repuesto.stock,
            motivo="Stock inicial",
            cuando=FECHA_CARGA,
        )
        for repuesto in repuestos.values()
    )
    session.add(
        HistorialPrecio(
            repuesto_id=repuestos["filtro"].id,
            usuario_id=admin.id,
            precio_anterior=Decimal("8000.00"),
            precio_nuevo=repuestos["filtro"].precio,
            cuando=FECHA_CARGA,
        )
    )
    await session.flush()
    return repuestos


async def crear_orden(
    session: AsyncSession,
    vehiculo: Vehiculo,
    repuesto: Repuesto,
    cantidad: int,
    falla: str,
    recepcion: Usuario,
    creada_en: datetime,
) -> OrdenTrabajo:
    # El precio se copia del repuesto y el total lo calcula el servidor (RN-10).
    orden = OrdenTrabajo(
        vehiculo_id=vehiculo.id,
        estado=Estado.PENDIENTE,
        falla=falla,
        creada_en=creada_en,
        total=repuesto.precio * cantidad,
        items=[ItemOrden(repuesto_id=repuesto.id, cantidad=cantidad, precio_unitario=repuesto.precio)],
        historial=[HistorialEstadoOrden(hasta_estado=Estado.PENDIENTE, usuario_id=recepcion.id, cuando=creada_en)],
    )
    session.add(orden)
    await session.flush()
    return orden


async def cargar_ordenes(
    session: AsyncSession,
    usuarios: dict[str, Usuario],
    vehiculos: dict[str, Vehiculo],
    repuestos: dict[str, Repuesto],
) -> None:
    recepcion = usuarios["recepcion@example.com"]
    mecanico = usuarios["mecanico@example.com"]

    await crear_orden(
        session, vehiculos["laura_1"], repuestos["filtro"], 1, "Cambio de filtro de aceite", recepcion, FECHA_CARGA
    )

    # La orden 2 pide 4 bujías cuando hay 2: el stock recién se descuenta al terminarla (casos C-11 y C-12).
    creada_en = FECHA_CARGA + timedelta(minutes=10)
    orden = await crear_orden(
        session, vehiculos["jorge"], repuestos["bujia"], 4, "El motor falla en frío", recepcion, creada_en
    )
    orden.estado = Estado.EN_REPARACION
    orden.mecanico_id = mecanico.id
    session.add(
        HistorialEstadoOrden(
            orden_id=orden.id,
            desde_estado=Estado.PENDIENTE,
            hasta_estado=Estado.EN_REPARACION,
            usuario_id=mecanico.id,
            cuando=creada_en + timedelta(minutes=10),
        )
    )
    await session.flush()


async def cargar_datos(session: AsyncSession, costo: int) -> None:
    await vaciar_tablas(session)
    # El catálogo primero: todo lo que tiene un estado apunta a él.
    await cargar_estados(session)
    usuarios = await cargar_usuarios(session, costo)
    vehiculos = await cargar_clientes(session, usuarios)
    repuestos = await cargar_repuestos(session, usuarios["admin@example.com"])
    await cargar_ordenes(session, usuarios, vehiculos, repuestos)
    session.add(EventoSeguridad(cuando=FECHA_CARGA, actor="SISTEMA", accion="Carga de los datos iniciales"))


async def main() -> None:
    settings = get_settings()
    motor = crear_motor(settings)
    try:
        # Una sola transacción: o queda todo cargado, o la base queda como estaba.
        async with crear_fabrica_sesiones(motor)() as session, session.begin():
            await cargar_datos(session, settings.BCRYPT_COST)
    finally:
        await motor.dispose()
    print("Datos iniciales cargados.")


if __name__ == "__main__":
    asyncio.run(main())
