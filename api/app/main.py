"""API del Portal Oleofinos.

Se publica solo en 127.0.0.1: la única cliente es el servidor de Next.js del mismo equipo.
Arranque en el servidor:  uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app import db
from app.config import Settings, get_settings
from app.routers import auth, commodities, usuarios

log = logging.getLogger("oleoweb.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    db.iniciar(settings.DATABASE_URL.get_secret_value())  # type: ignore[union-attr]

    app = FastAPI(
        title="Portal Oleofinos API",
        version="0.1.0",
        # La documentación interactiva solo existe en desarrollo.
        docs_url="/docs" if settings.es_dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.es_dev else None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.exception_handler(Exception)
    async def _error_no_controlado(_: Request, exc: Exception) -> JSONResponse:
        # El detalle va al log del servidor, nunca a la respuesta.
        log.exception("Error no controlado", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Error interno."})

    @app.get("/salud", include_in_schema=False)
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    app.include_router(auth.router)
    app.include_router(commodities.router)
    app.include_router(usuarios.router)
    return app


def __getattr__(nombre: str):  # pragma: no cover
    # `uvicorn app.main:app` crea la app al pedirla, no al importar el módulo (facilita pruebas).
    if nombre == "app":
        return create_app()
    raise AttributeError(nombre)
