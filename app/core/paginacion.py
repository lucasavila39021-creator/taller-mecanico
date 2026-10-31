from collections.abc import Sequence
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel


# Sin HTTP: el router es el que la traduce a un 422.
class PaginaInexistente(Exception):
    def __init__(self, page: int, pages: int) -> None:
        super().__init__(f"La página {page} no existe: hay {pages}")


class Pagina[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


# Se usa como dependencia: FastAPI valida page y size, y responde 422 si no cumplen.
class Paginacion:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1)] = 1,
        size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> None:
        self.page = page
        self.size = size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


# Con cero resultados hay una página, vacía.
def calcular_paginas(total: int, size: int) -> int:
    return max(1, (total + size - 1) // size)


# Se llama después de contar y antes de traer las filas.
def verificar_pagina(paginacion: Paginacion, total: int) -> None:
    pages = calcular_paginas(total, paginacion.size)
    if paginacion.page > pages:
        raise PaginaInexistente(paginacion.page, pages)


def armar_pagina[T](items: Sequence[T], total: int, paginacion: Paginacion) -> Pagina[T]:
    return Pagina[T](
        items=list(items),
        total=total,
        page=paginacion.page,
        size=paginacion.size,
        pages=calcular_paginas(total, paginacion.size),
    )
