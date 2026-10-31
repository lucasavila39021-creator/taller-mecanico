import asyncio
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Los modelos se nombran entre sí como texto: tienen que estar todos importados antes de la primera consulta.
import app.modules.clientes.models  # noqa: F401
import app.modules.ordenes.models  # noqa: F401
import app.modules.repuestos.models  # noqa: F401
import app.modules.usuarios.models  # noqa: F401
from app.core.config import get_settings
from app.core.database import crear_fabrica_sesiones, crear_motor
from app.core.dependencies import exigir_password_al_dia
from app.core.security import hashear_password
from app.modules.clientes.router import router as clientes_router
from app.modules.health.router import router as health_router
from app.modules.ordenes.router import router as ordenes_router
from app.modules.repuestos.router import router as repuestos_router
from app.modules.usuarios.router import router as usuarios_router
from app.modules.usuarios.router import router_admin as administracion_router


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


# Los mensajes propios de cada tipo de error de validación. Entre llaves, datos que trae el error.
MENSAJES_VALIDACION = {
    "missing": "Este campo es obligatorio",
    "extra_forbidden": "Este campo no está permitido",
    "string_type": "Tiene que ser un texto",
    "string_too_short": "No puede estar vacío",
    "string_unicode": "Contiene caracteres inválidos",
    "int_type": "Tiene que ser un número entero",
    "int_parsing": "Tiene que ser un número entero",
    "int_from_float": "Tiene que ser un número entero",
    "bool_type": "Tiene que ser verdadero o falso",
    "bool_parsing": "Tiene que ser verdadero o falso",
    "greater_than": "Tiene que ser mayor que {gt}",
    "greater_than_equal": "Tiene que ser mayor o igual que {ge}",
    "less_than": "Tiene que ser menor que {lt}",
    "less_than_equal": "Tiene que ser menor o igual que {le}",
    "decimal_type": "Tiene que ser un número",
    "decimal_parsing": "Tiene que ser un número",
    "finite_number": "Tiene que ser un número",
    "decimal_max_digits": "Tiene demasiados dígitos",
    "decimal_whole_digits": "Tiene demasiados dígitos",
    "decimal_max_places": "Admite como máximo {decimal_places} decimales",
    "enum": "No es un valor permitido",
    "timezone_aware": "La fecha tiene que indicar la zona horaria",
    "datetime_type": "Tiene que ser una fecha",
    "datetime_parsing": "No es una fecha válida",
    "datetime_from_date_parsing": "No es una fecha válida",
    "json_invalid": "El cuerpo no es un JSON válido",
    "model_attributes_type": "El cuerpo tiene que ser un objeto",
    "list_type": "Tiene que ser una lista",
    "too_short": "Tiene que tener al menos {min_length} elemento",
}


def _mensaje_validacion(error: dict) -> str:
    if error["type"] == "value_error":
        # Un ValueError propio ya está en español; el del validador de correo, no.
        mensaje = error["msg"].removeprefix("Value error, ")
        return "El correo no es válido" if mensaje.startswith("value is not a valid email") else mensaje
    plantilla = MENSAJES_VALIDACION.get(error["type"], "El valor no es válido")
    return plantilla.format(**error.get("ctx", {}))


# El 422 de FastAPI repite lo recibido en "input": devolvería la contraseña, y un carácter
# que no se puede codificar lo haría terminar en un 500. Por eso no se repite la entrada.
@app.exception_handler(RequestValidationError)
async def error_de_validacion(request: Request, error: RequestValidationError) -> JSONResponse:
    detalle = [
        {
            # El nombre de un campo que no se pidió también viene del cliente.
            "loc": [p.encode("utf-8", "replace").decode() if isinstance(p, str) else p for p in e["loc"]],
            "msg": _mensaje_validacion(e),
            "type": e["type"],
        }
        for e in error.errors()
    ]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detalle})


# Dos grupos porque FastAPI suma dependencias y no las resta: el control del cambio obligatorio
# de contraseña se monta una sola vez, en el grupo protegido (RN-06).
grupo_abierto = APIRouter()
grupo_abierto.include_router(health_router)
grupo_abierto.include_router(usuarios_router)

grupo_protegido = APIRouter(dependencies=[Depends(exigir_password_al_dia)])
grupo_protegido.include_router(administracion_router)
grupo_protegido.include_router(clientes_router)
grupo_protegido.include_router(repuestos_router)
grupo_protegido.include_router(ordenes_router)

app.include_router(grupo_abierto)
app.include_router(grupo_protegido)
