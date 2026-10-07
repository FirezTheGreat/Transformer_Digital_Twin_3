"""API Routers Aggregator (Phase 7.3)."""

from fastapi import APIRouter

from app.api.routers.analytics import router as analytics_router
from app.api.routers.assets import router as assets_router
from app.api.routers.feedback import router as feedback_router
from app.api.routers.replay import router as replay_router
from app.api.routers.reports import router as reports_router
from app.api.routers.telemetry import router as telemetry_router

api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(telemetry_router)
api_v1_router.include_router(replay_router)
api_v1_router.include_router(assets_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(feedback_router)
api_v1_router.include_router(reports_router)

