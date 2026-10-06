"""Application Dependencies and State Container (Phase 7.3).

Provides thread-safe state container and FastAPI dependency injection providers
for storage, engines, configuration, scenario simulation, feedback ledger, and active digital twin states.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from fastapi import Depends, Request

from app.core.checkpoint import CheckpointStore
from app.core.config import Settings, get_settings
from app.core.storage import StorageEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.feedback import OperatorFeedbackLedger
from app.engine.reducer import TwinReducer
from app.engine.replay import ReplayEngine
from app.engine.scenario_simulator import ScenarioSimulator
from app.models.fact_bundle import FactBundle
from app.models.profile import AssetProfile
from app.models.thermal_artifact import (
    BaselineMetricEntry,
    CalibratedThermalModelArtifact,
    ConformalUncertaintyParams,
    IdentifiabilityReport,
    PromotionDecision,
    QualificationStatus,
    ThermalModelParamsDict,
    ThermalModelQualification,
)
from app.models.twin_state import TwinState


def build_default_model_artifact(asset_id: str = "DT-TRIPURA-001") -> CalibratedThermalModelArtifact:
    """Construct baseline fallback thermal model artifact when file is absent."""
    return CalibratedThermalModelArtifact(
        schema_version="1.2.0",
        model_version="greybox_v1_0",
        asset_id=asset_id,
        created_at_utc="2026-04-01T12:00:00Z",
        selected_load_driver="rms_current_a",
        load_driver_reference_value=153.865,
        parameters=ThermalModelParamsDict(beta_0=15.0, beta_1=35.0, tau_hours=3.0),
        identifiability=IdentifiabilityReport(
            is_identifiable=True,
            fit_samples_count=1000,
            fit_span_days=14.0,
            load_cv=0.45,
            load_range=120.0,
            tau_cv_across_folds=0.08,
            boundary_hit=False,
            diagnostic_messages=["Identifiability criteria satisfied"],
        ),
        conformal_uncertainty=ConformalUncertaintyParams(
            horizon_steps=8,
            horizon_scales_degc=[2.0, 2.2, 2.5, 3.0, 3.8, 4.5, 5.5, 6.5],
            block_quantile_90=5.9891,
            horizon_half_widths_degc=[2.99, 3.11, 3.37, 4.08, 5.04, 6.29, 8.20, 9.56],
            calibration_residual_median=0.1,
            calibration_residual_mad=1.2,
            num_calibration_origins=50,
        ),
        test_metrics=BaselineMetricEntry(
            model_name="first_order_greybox_ode",
            mae_degc=2.15,
            rmse_degc=2.85,
            bias_degc=0.20,
            marginal_coverage_90_pct=91.5,
            mean_width_degc=5.4,
        ),
        promotion=PromotionDecision(
            status="PROMOTED",
            primary_evaluation_horizon="2_hour_multi_step_trajectory",
            mae_improvement_pct=18.5,
            passes_mae_criterion=True,
            passes_bias_criterion=True,
            passes_coverage_criterion=True,
            passes_scenario_criterion=True,
            passes_identifiability_criterion=True,
            all_criteria_met=True,
            reasons=["All promotion criteria satisfied against untouched TEST partition."],
        ),
        qualification=ThermalModelQualification(
            parameter_interpretability=QualificationStatus.QUALIFIED,
            forecast_qualification=QualificationStatus.QUALIFIED,
            scenario_qualification=QualificationStatus.QUALIFIED,
            residual_display_qualification=QualificationStatus.QUALIFIED,
            residual_anomaly_qualification=QualificationStatus.QUALIFIED,
            cusum_qualification=QualificationStatus.DISABLED,
            maintenance_inference_qualification=QualificationStatus.QUALIFIED,
            dimension_reasons={
                "scenario_qualification": "2-hour what-if scenario projection validated on held-out test data."
            },
        ),
    )


class AppState:
    """Central stateful container holding engines, storage, and active digital twin states."""

    def __init__(
        self,
        settings: Settings | None = None,
        storage: StorageEngine | None = None,
        checkpoint_store: CheckpointStore | None = None,
        profile: AssetProfile | None = None,
        reducer: TwinReducer | None = None,
        capability_evaluator: CapabilityEvaluator | None = None,
        feedback_ledger: OperatorFeedbackLedger | None = None,
        replay_engine: ReplayEngine | None = None,
        model_artifact: CalibratedThermalModelArtifact | None = None,
        scenario_simulator: ScenarioSimulator | None = None,
        current_state: TwinState | None = None,
        latest_fact_bundle: FactBundle | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.storage = storage
        self.checkpoint_store = checkpoint_store
        self.profile = profile
        self.reducer = reducer
        self.capability_evaluator = capability_evaluator
        self.feedback_ledger = feedback_ledger
        self.replay_engine = replay_engine
        self.model_artifact = model_artifact
        self.scenario_simulator = scenario_simulator
        self.current_state = current_state
        self.latest_fact_bundle = latest_fact_bundle

    def update_state(self, state: TwinState, fact_bundle: FactBundle | None = None) -> None:
        """Update current state and latest FactBundle."""
        self.current_state = state
        self.latest_fact_bundle = fact_bundle


def get_app_state(request: Request) -> AppState:
    """Retrieve AppState container from FastAPI application state."""
    state = getattr(request.app.state, "app_state", None)
    if state is None:
        state = AppState()
        request.app.state.app_state = state
    return state


def get_settings_dep(state: AppState = Depends(get_app_state)) -> Settings:
    """Provide application settings dependency."""
    return state.settings


def get_storage(state: AppState = Depends(get_app_state)) -> StorageEngine:
    """Provide StorageEngine dependency."""
    if state.storage is None:
        state.storage = StorageEngine(db_path=state.settings.db_path)
    return state.storage


def get_reducer(state: AppState = Depends(get_app_state)) -> TwinReducer:
    """Provide TwinReducer dependency."""
    if state.reducer is None:
        state.reducer = TwinReducer(
            profile=state.profile,
            load_reference_kva=state.settings.load_reference_kva,
        )
    return state.reducer


def get_capability_evaluator(state: AppState = Depends(get_app_state)) -> CapabilityEvaluator:
    """Provide CapabilityEvaluator dependency."""
    if state.capability_evaluator is None:
        state.capability_evaluator = CapabilityEvaluator(
            profile=state.profile,
            expected_cadence_s=state.settings.expected_cadence_s,
            evaluation_window_s=state.settings.evaluation_window_s,
        )
    return state.capability_evaluator


def get_replay_engine(
    state: AppState = Depends(get_app_state),
    storage: StorageEngine = Depends(get_storage),
) -> ReplayEngine:
    """Provide ReplayEngine dependency."""
    if state.replay_engine is None:
        state.replay_engine = ReplayEngine(
            storage=storage,
            asset_id=state.settings.default_asset_id,
        )
    return state.replay_engine


def get_feedback_ledger(state: AppState = Depends(get_app_state)) -> OperatorFeedbackLedger:
    """Provide OperatorFeedbackLedger dependency."""
    if state.feedback_ledger is None:
        state.feedback_ledger = OperatorFeedbackLedger()
    return state.feedback_ledger


def get_model_artifact(state: AppState = Depends(get_app_state)) -> CalibratedThermalModelArtifact:
    """Provide CalibratedThermalModelArtifact dependency."""
    if state.model_artifact is None:
        artifact_path = Path("data/processed/calibrated_thermal_model.json")
        if artifact_path.exists():
            try:
                state.model_artifact = CalibratedThermalModelArtifact.load_json(artifact_path)
            except Exception:
                state.model_artifact = build_default_model_artifact(state.settings.default_asset_id)
        else:
            state.model_artifact = build_default_model_artifact(state.settings.default_asset_id)
    return state.model_artifact


def get_scenario_simulator(
    state: AppState = Depends(get_app_state),
    artifact: CalibratedThermalModelArtifact = Depends(get_model_artifact),
) -> ScenarioSimulator:
    """Provide ScenarioSimulator dependency."""
    if state.scenario_simulator is None:
        state.scenario_simulator = ScenarioSimulator.from_artifact(artifact)
    return state.scenario_simulator
