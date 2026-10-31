import asyncio
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import crear_fabrica_sesiones, crear_motor
from app.core.security import hashear_password
from app.modules.health.router import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Al arrancar: el bucle de eventos ya existe.
    settings = get_settings()
    motor = crear_motor(settings)
    app.state.motor = motor
    app.state.fabrica_sesiones = crear_fabrica_sesiones(motor)
    app.state.semaforo_bcrypt = asyncio.Semaphore(settings.BCRYPT_CONCURRENCIA)
    # RN-09: si el correo no existe, el login verifica contra este hash para tardar lo mismo.
    # Sale de una contraseña al azar que nadie conoce, y se calcula una sola vez.
    app.state.hash_ficticio = await hashear_password(
        secrets.token_urlsafe(32), settings.BCRYPT_COST, app.state.semaforo_bcrypt
    )
    yield
    # Al apagar.
    await motor.dispose()


app = FastAPI(title="Taller Mecánico", lifespan=lifespan)
app.include_router(health_router)
