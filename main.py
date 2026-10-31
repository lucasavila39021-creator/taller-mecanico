import asyncio
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Los modelos se nombran entre sí como texto: tienen que estar todos importados antes de la primera consulta.
import app.modules.clientes.models  # noqa: F401
import app.modules.ordenes.models  # noqa: F401
import app.modules.repuestos.models  # noqa: F401
import app.modules.usuarios.models  # noqa: F401
from app.core.config import get_settings
from app.core.database import crear_fabrica_sesiones, crear_motor
from app.core.security import hashear_password
from app.modules.health.router import router as health_router
from app.modules.usuarios.router import router as usuarios_router


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


# El 422 de FastAPI repite lo recibido en "input": devolvería la contraseña, y un carácter
# que no se puede codificar lo haría terminar en un 500. Por eso no se repite la entrada.
@app.exception_handler(RequestValidationError)
async def error_de_validacion(request: Request, error: RequestValidationError) -> JSONResponse:
    detalle = [
        {
            # El nombre de un campo que no se pidió también viene del cliente.
            "loc": [p.encode("utf-8", "replace").decode() if isinstance(p, str) else p for p in e["loc"]],
            "msg": e["msg"],
            "type": e["type"],
        }
        for e in error.errors()
    ]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detalle})


app.include_router(health_router)
app.include_router(usuarios_router)
