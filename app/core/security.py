import asyncio
from datetime import UTC, datetime
from typing import Any

import bcrypt
import jwt

from app.core.config import Settings

ALGORITMO_TOKEN = "HS256"
NOMBRE_COOKIE = "access_token"


class TokenInvalido(Exception):
    """El token no se puede usar: firma incorrecta, vencido o mal formado."""


# bcrypt corre fuera del bucle de eventos y el semáforo limita cuántos corren a la vez.
# El semáforo llega por parámetro: se crea en el lifespan, porque al importar este módulo
# todavía no hay configuración ni bucle de eventos.
async def hashear_password(password: str, costo: int, semaforo: asyncio.Semaphore) -> str:
    async with semaforo:
        hash_bytes = await asyncio.to_thread(bcrypt.hashpw, password.encode(), bcrypt.gensalt(rounds=costo))
    return hash_bytes.decode()


async def verificar_password(password: str, password_hash: str, semaforo: asyncio.Semaphore) -> bool:
    async with semaforo:
        return await asyncio.to_thread(bcrypt.checkpw, password.encode(), password_hash.encode())


def crear_token(usuario_id: int, roles: list[str], settings: Settings) -> str:
    # iat con fracciones de segundo y no un datetime, que PyJWT truncaría a segundos.
    # RN-07 distingue una sesión de otra aunque sean del mismo segundo que el cambio de contraseña.
    ahora = datetime.now(UTC).timestamp()
    payload = {
        "sub": str(usuario_id),
        "iat": ahora,
        "exp": ahora + settings.TOKEN_DURACION_SEGUNDOS,
        "roles": roles,
    }
    return jwt.encode(payload, settings.SECRET_KEY.get_secret_value(), algorithm=ALGORITMO_TOKEN)


def verificar_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[ALGORITMO_TOKEN],
            options={"require": ["sub", "iat", "exp", "roles"]},
        )
    except jwt.InvalidTokenError as error:
        raise TokenInvalido from error
