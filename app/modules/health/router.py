import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session

logger = logging.getLogger(__name__)

# Sin este límite, una base que no contesta dejaría la petición colgada.
TIMEOUT_READY_SEGUNDOS = 5

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"estado": "ok"}


@router.get("/ready")
async def ready(session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
    try:
        async with asyncio.timeout(TIMEOUT_READY_SEGUNDOS):
            await session.exec(text("SELECT 1"))
    # Se captura todo a propósito: al conectar, el driver lanza errores de varios tipos,
    # y cualquier falla significa lo mismo: la aplicación no está lista.
    except Exception as error:
        # El detalle queda en la consola del servidor; al cliente sólo le llega un mensaje propio.
        logger.warning("La base de datos no responde: %s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La base de datos no está disponible",
        ) from None
    return {"estado": "ok"}
