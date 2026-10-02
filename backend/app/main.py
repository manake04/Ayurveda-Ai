"""FastAPI application entry point: `uvicorn app.main:app`."""

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ask, graph, meta, tools
from app.core.config import Settings, get_settings
from app.core.container import Container


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = container or await Container.create(settings)
        yield
        await app.state.container.close()

    app = FastAPI(
        title="IP-SAKTI Sahayak API",
        description="Source-cited IP and regulatory guidance for Ayurveda.",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    api = APIRouter(prefix="/api")
    for module in (meta, ask, graph, tools):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
