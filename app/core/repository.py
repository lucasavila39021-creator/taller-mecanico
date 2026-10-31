from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ColumnElement
from sqlmodel import SQLModel, func, select
from sqlmodel.ext.asyncio.session import AsyncSession


class BaseRepository[T: SQLModel]:
    # Recibe la clase del modelo porque los genéricos se borran en tiempo de ejecución: T no existe al correr.
    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, id: int) -> T | None:
        return await self.session.get(self.model, id)

    # get_all y count reciben los mismos filtros, para que el total cuente lo mismo que la página.
    async def get_all(
        self,
        *filtros: ColumnElement[bool],
        offset: int = 0,
        limit: int | None = None,
    ) -> Sequence[T]:
        # Sin un orden fijo, una fila podría repetirse o perderse entre dos páginas.
        consulta = select(self.model).where(*filtros).order_by(self.model.id).offset(offset).limit(limit)
        return (await self.session.exec(consulta)).all()

    async def count(self, *filtros: ColumnElement[bool]) -> int:
        consulta = select(func.count()).select_from(self.model).where(*filtros)
        return (await self.session.exec(consulta)).one()

    # Ningún método confirma: flush() envía el cambio dentro de la transacción, y confirma el Unit of Work.
    async def add(self, entidad: T) -> T:
        self.session.add(entidad)
        await self.session.flush()
        return entidad

    # datos trae sólo los campos enviados: es lo que entrega un PATCH con exclude_unset.
    async def update(self, entidad: T, datos: dict[str, Any]) -> T:
        entidad.sqlmodel_update(datos)
        self.session.add(entidad)
        await self.session.flush()
        return entidad

    async def delete(self, entidad: T) -> None:
        await self.session.delete(entidad)
        await self.session.flush()


class SoftDeleteRepository[T: SQLModel](BaseRepository[T]):
    async def get_by_id(self, id: int) -> T | None:
        entidad = await super().get_by_id(id)
        if entidad is None or entidad.borrado_en is not None:
            return None
        return entidad

    async def get_all(
        self,
        *filtros: ColumnElement[bool],
        offset: int = 0,
        limit: int | None = None,
    ) -> Sequence[T]:
        return await super().get_all(self.model.borrado_en.is_(None), *filtros, offset=offset, limit=limit)

    async def count(self, *filtros: ColumnElement[bool]) -> int:
        return await super().count(self.model.borrado_en.is_(None), *filtros)

    async def get_by_id_including_deleted(self, id: int) -> T | None:
        return await super().get_by_id(id)

    async def soft_delete(self, entidad: T) -> None:
        entidad.borrado_en = datetime.now(UTC)
        self.session.add(entidad)
        await self.session.flush()
