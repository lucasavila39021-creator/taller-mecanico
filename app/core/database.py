from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings


# Este módulo no crea nada al importarse: las dos funciones las llama el lifespan.
def crear_motor(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        echo=settings.SQL_ECHO,
        # Descarta las conexiones que murieron, por ejemplo si se reinició PostgreSQL.
        pool_pre_ping=True,
    )


def crear_fabrica_sesiones(motor: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)


# Una sesión por petición: el bloque async with la cierra al terminar.
async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.fabrica_sesiones() as session:
        yield session


# El nombre de la restricción que falló, para traducir el error sin mostrar el texto de la base.
def nombre_restriccion(error: IntegrityError) -> str | None:
    return getattr(error.orig.__cause__, "constraint_name", None)
