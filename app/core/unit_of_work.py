from types import TracebackType
from typing import Self

from sqlmodel.ext.asyncio.session import AsyncSession


class UnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> Self:
        return self

    # Devuelve None para que la excepción siga su camino después del rollback.
    # No cierra la sesión porque no la creó: la cierra get_session.
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.session.rollback()
            return
        try:
            await self.session.commit()
        except Exception:
            # Si falla el propio commit, sin este rollback la sesión queda inservible.
            await self.session.rollback()
            raise
