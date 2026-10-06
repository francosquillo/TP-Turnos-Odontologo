"""Task 2.3 GREEN: FastAPI + GET /health (200 / 503 sin secretos).

`async def` solo donde todo adentro es async no bloqueante (pings con timeout 2s).
"""

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin, auth, clinica, cobros, notificaciones
from app.api import obras_sociales as os_api
from app.api import pacientes, profesionales, sillones, turnos
from app.core.config import get_settings


async def check_postgres() -> str:
    """Ping Postgres real; nunca levanta excepcion (retorna 'down')."""
    import asyncpg

    settings = get_settings()
    try:
        conn = await asyncpg.connect(settings.database_url, timeout=2)
        try:
            await conn.fetchval("SELECT 1")
        finally:
            await conn.close()
        return "up"
    except Exception:
        return "down"


async def check_redis() -> str:
    """Ping Redis real; nunca levanta excepcion (retorna 'down')."""
    import redis.asyncio as aioredis

    settings = get_settings()
    try:
        client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        try:
            await client.ping()
        finally:
            await client.aclose()
        return "up"
    except Exception:
        return "down"


PostgresDep = Annotated[str, Depends(check_postgres)]
RedisDep = Annotated[str, Depends(check_redis)]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="TP Turnos Odontologo (C-01 skeleton)")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health(pg: PostgresDep, rd: RedisDep) -> JSONResponse:
        ok = pg == "up" and rd == "up"
        return JSONResponse(
            status_code=200 if ok else 503,
            content={"status": "ok" if ok else "degraded", "postgres": pg, "redis": rd},
        )

    for router in (
        auth.router,
        pacientes.router,
        profesionales.router,
        sillones.router,
        turnos.router,
        clinica.router,
        cobros.router,
        os_api.router,
        notificaciones.router,
        admin.router,
    ):
        app.include_router(router)

    return app


app = create_app()
