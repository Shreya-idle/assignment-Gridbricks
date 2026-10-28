from fastapi import APIRouter

from app.api.routes import analytics, data_sources, generation, health, saved_analyses

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(data_sources.router)
api_router.include_router(generation.router)
api_router.include_router(analytics.router)
api_router.include_router(saved_analyses.router)
