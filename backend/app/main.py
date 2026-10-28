import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.clients.elexon import ElexonClient
from app.core.config import Settings, get_settings
from app.core.errors import install_exception_handlers
from app.database import create_database_resources
from app.services.analytics import AnalyticsService
from app.services.auth import SupabaseJwtVerifier
from app.services.generation import GenerationService
from app.services.persistence import PersistenceService
from app.services.source_status import SourceStatusRegistry


def create_app(settings: Settings | None = None, client: ElexonClient | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(
            level=getattr(logging, settings.log_level),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        owned_client = client is None
        elexon = client or ElexonClient(
            str(settings.elexon_base_url),
            settings.elexon_timeout_seconds,
            settings.elexon_max_retries,
        )
        statuses = SourceStatusRegistry(configured=bool(settings.elexon_base_url))
        db_engine, db_session_factory = create_database_resources(settings)
        app.state.settings = settings
        app.state.elexon_client = elexon
        app.state.source_statuses = statuses
        app.state.db_engine = db_engine
        app.state.db_session_factory = db_session_factory
        app.state.persistence_service = PersistenceService(db_session_factory)
        app.state.auth_verifier = SupabaseJwtVerifier(settings)
        app.state.generation_service = GenerationService(
            elexon,
            statuses,
            settings.elexon_max_range_days,
            app.state.persistence_service,
        )
        app.state.analytics_service = AnalyticsService(
            app.state.generation_service,
            settings.elexon_max_range_days,
            settings.analytics_forecast_history_days,
        )
        logging.getLogger(__name__).info("WindSight application started")
        yield
        if owned_client:
            await elexon.aclose()
        if db_engine is not None:
            await db_engine.dispose()
        await app.state.auth_verifier.aclose()
        logging.getLogger(__name__).info("WindSight application stopped")

    app = FastAPI(
        title=settings.app_name,
        description="Validated access to Elexon FUELHH actuals and WINDFOR forecasts.",
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    install_exception_handlers(app)
    return app


app = create_app()
