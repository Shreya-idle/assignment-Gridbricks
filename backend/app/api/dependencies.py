from fastapi import Request

from app.services.analytics import AnalyticsService
from app.services.generation import GenerationService
from app.services.source_status import SourceStatusRegistry


def get_generation_service(request: Request) -> GenerationService:
    return request.app.state.generation_service


def get_analytics_service(request: Request) -> AnalyticsService:
    return request.app.state.analytics_service


def get_source_statuses(request: Request) -> SourceStatusRegistry:
    return request.app.state.source_statuses
