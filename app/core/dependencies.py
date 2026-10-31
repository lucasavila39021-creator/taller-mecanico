import asyncio

from fastapi import Request


async def get_semaforo_bcrypt(request: Request) -> asyncio.Semaphore:
    return request.app.state.semaforo_bcrypt
