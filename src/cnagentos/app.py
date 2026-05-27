from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from cnagentos.api import register_api_support, success_response
from cnagentos.config import Settings, get_settings
from cnagentos.controllers.admin import router as admin_router
from cnagentos.controllers.auth import router as auth_router
from cnagentos.db import build_engine, build_sessionmaker


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    engine = build_engine(active_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await engine.dispose()

    app = FastAPI(title=active_settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = active_settings
    app.state.engine = engine
    app.state.sessionmaker = build_sessionmaker(engine)
    register_api_support(app)
    app.include_router(auth_router)
    app.include_router(admin_router)

    @app.get("/health")
    async def health(request: Request):
        return success_response(request, {"status": "ok"})

    return app
