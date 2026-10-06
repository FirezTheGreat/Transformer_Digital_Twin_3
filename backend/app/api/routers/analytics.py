"""Health, Episodes, Recommendations, Model-Card & Scenario Router (Phase 7.3).

Provides analytical query and simulation endpoints:
- GET /v1/assets/{asset_id}/health: Multi-domain health breakdown, evidence grades, gated OTHI.
- GET /v1/assets/{asset_id}/episodes: Open and tracked anomaly episodes.
- GET /v1/assets/{asset_id}/recommendations: Active deterministic maintenance actions.
- GET /v1/assets/{asset_id}/model-card: Physical parameters, calibration metrics, bounds.
- POST /v1/assets/{asset_id}/scenario: 2-hour what-if thermal projection under load/ambient steps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    AppState,
    get_app_state,
    get_capability_evaluator,
    get_model_artifact,
    get_scenario_simulator,
)
from app.engine.capability import CapabilityEvaluator
from app.engine.fact_bundle import build_default_health_bundle
from app.engine.scenario_simulator import ScenarioSimulator
from app.engine.thermal_fallback import ThermalTrustState
from app.models.anomaly import AnomalyCategory, AnomalyEpisode
from app.models.health import OTHIBundle
from app.models.maintenance import MaintenancePriority, MaintenanceRecommendation
from app.models.scenario import ScenarioProjectionResult, ScenarioRequest
from app.models.thermal_artifact import CalibratedThermalModelArtifact

router = APIRouter(prefix="/assets", tags=["Analytics & Scenarios"])


@router.get(
    "/{asset_id}/health",
    response_model=OTHIBundle,
    status_code=status.HTTP_200_OK,
    summary="Get multi-domain health breakdown, evidence grades, and gated OTHI",
)
async def get_asset_health(
    asset_id: str,
    app_state: AppState = Depends(get_app_state),
) -> OTHIBundle:
    """Return the gated OTHI composite score, independent evidence quality grade, and 5-domain scores."""
    if (
        app_state.latest_fact_bundle is not None
        and app_state.latest_fact_bundle.asset_id == asset_id
    ):
        return app_state.latest_fact_bundle.health

    if (
        app_state.current_state is not None
        and app_state.current_state.asset_id == asset_id
        and app_state.current_state.health_bundle is not None
    ):
        return app_state.current_state.health_bundle

    now = datetime.now(timezone.utc)
    return build_default_health_bundle(asset_id, now)


@router.get(
    "/{asset_id}/episodes",
    response_model=List[AnomalyEpisode],
    status_code=status.HTTP_200_OK,
    summary="Query open and tracked anomaly episodes",
)
async def get_asset_episodes(
    asset_id: str,
    state_filter: Optional[str] = Query(default=None, alias="state", description="Filter by episode state (e.g. ACTIVE, WARNING, CRITICAL)"),
    category: Optional[AnomalyCategory] = Query(default=None, description="Filter by anomaly category"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max episodes to return"),
    app_state: AppState = Depends(get_app_state),
) -> List[AnomalyEpisode]:
    """Fetch active and recovering anomaly episodes for the target asset."""
    episodes: List[AnomalyEpisode] = []
    if (
        app_state.current_state is not None
        and app_state.current_state.asset_id == asset_id
    ):
        episodes = list(app_state.current_state.open_episodes)

    # Apply category filter
    if category is not None:
        episodes = [ep for ep in episodes if ep.category == category]

    # Apply state filter
    if state_filter is not None:
        clean_state = state_filter.upper().strip()
        episodes = [
            ep for ep in episodes
            if (ep.state.value if hasattr(ep.state, "value") else str(ep.state)).upper() == clean_state
        ]

    return episodes[:limit]


@router.get(
    "/{asset_id}/recommendations",
    response_model=List[MaintenanceRecommendation],
    status_code=status.HTTP_200_OK,
    summary="Query active prioritized maintenance recommendations",
)
async def get_asset_recommendations(
    asset_id: str,
    priority: Optional[MaintenancePriority] = Query(default=None, description="Filter by priority tier (P0–P4)"),
    rule_id: Optional[str] = Query(default=None, description="Filter by triggering rule ID"),
    app_state: AppState = Depends(get_app_state),
) -> List[MaintenanceRecommendation]:
    """Fetch explainable maintenance recommendations with action-window provenance and priority."""
    recs: List[MaintenanceRecommendation] = []
    if (
        app_state.current_state is not None
        and app_state.current_state.asset_id == asset_id
    ):
        recs = list(app_state.current_state.active_recommendations)
    elif (
        app_state.latest_fact_bundle is not None
        and app_state.latest_fact_bundle.asset_id == asset_id
    ):
        recs = list(app_state.latest_fact_bundle.active_recommendations)

    if priority is not None:
        recs = [r for r in recs if r.priority == priority]

    if rule_id is not None:
        clean_rule = rule_id.strip()
        recs = [r for r in recs if r.rule_id == clean_rule]

    return recs


@router.get(
    "/{asset_id}/model-card",
    response_model=CalibratedThermalModelArtifact,
    status_code=status.HTTP_200_OK,
    summary="Inspect physical parameters, calibration metrics, and qualification bounds",
)
async def get_asset_model_card(
    asset_id: str,
    model_artifact: CalibratedThermalModelArtifact = Depends(get_model_artifact),
) -> CalibratedThermalModelArtifact:
    """Return comprehensive calibrated model card including parameters, bounds, and qualification matrix."""
    return model_artifact


@router.post(
    "/{asset_id}/scenario",
    response_model=ScenarioProjectionResult,
    status_code=status.HTTP_200_OK,
    summary="Execute 2-hour what-if thermal projection under load/ambient steps",
)
async def execute_what_if_scenario(
    asset_id: str,
    request: ScenarioRequest,
    app_state: AppState = Depends(get_app_state),
    simulator: ScenarioSimulator = Depends(get_scenario_simulator),
) -> ScenarioProjectionResult:
    """Simulate 2-hour forward top-oil temperature trajectory with conformal uncertainty bounds."""
    state = app_state.current_state

    # Extract origin values from active state if available
    now = datetime.now(timezone.utc)
    origin_time = state.state_time_utc if state else now
    origin_top_oil: Optional[float] = None
    origin_ambient: Optional[float] = None
    origin_load_u: Optional[float] = None

    if state:
        # Check top oil observation
        for k, m in state.current_observations.items():
            k_clean = k.lower()
            if "top_oil" in k_clean or k_clean == "oti":
                origin_top_oil = float(m.value) if m.value is not None else None
            elif "ambient" in k_clean or k_clean == "ati":
                origin_ambient = float(m.value) if m.value is not None else None

        if state.derived_electrical is not None:
            origin_load_u = state.derived_electrical.relative_load_index

    # Default fallback values for testing if uninitialized
    if origin_top_oil is None:
        origin_top_oil = 65.0
    if origin_ambient is None:
        origin_ambient = 30.0
    if origin_load_u is None:
        origin_load_u = 0.80

    # Determine trust state
    trust_state = ThermalTrustState.MODEL_HEALTHY
    if state and state.thermal_latent:
        status_str = state.thermal_latent.model_status.upper()
        if "FALLBACK" in status_str:
            trust_state = ThermalTrustState.FALLBACK_PERSISTENCE
        elif "WARMUP" in status_str:
            trust_state = ThermalTrustState.WARMUP
        elif "SHADOW" in status_str or "DESCRIPTIVE" in status_str:
            trust_state = ThermalTrustState.SHADOW_DESCRIPTIVE

    return simulator.run_projection(
        origin_time_utc=origin_time,
        origin_top_oil_degc=origin_top_oil,
        origin_ambient_degc=origin_ambient,
        origin_load_value=origin_load_u,
        trust_state=trust_state,
        scenario_request=request,
        is_load_value_already_index_u=True,
    )
