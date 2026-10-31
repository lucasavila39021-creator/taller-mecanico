from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import crear_fabrica_sesiones, crear_motor
from app.modules.health.router import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Al arrancar: el bucle de eventos ya existe.
    motor = crear_motor(get_settings())
    app.state.motor = motor
    app.state.fabrica_sesiones = crear_fabrica_sesiones(motor)
    yield
    # Al apagar.
    await motor.dispose()


app = FastAPI(title="Taller Mecánico", lifespan=lifespan)
app.include_router(health_router)
