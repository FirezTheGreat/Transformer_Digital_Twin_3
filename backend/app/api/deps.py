"""Application Dependencies and State Container (Phase 7.3).

Provides thread-safe state container and FastAPI dependency injection providers
for storage, engines, configuration, scenario simulation, feedback ledger, and active digital twin states.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
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


def build_default_model_artifact(
    asset_id: str = "tripura_dt_01",
    dataset_id: str = "tripura_dev",
) -> CalibratedThermalModelArtifact:
    """Construct baseline fallback thermal model artifact when file is absent."""
    return CalibratedThermalModelArtifact(
        schema_version="1.2.0",
        model_version="greybox_v1_0",
        dataset_id=dataset_id,
        asset_id=asset_id,
        created_at_utc="2026-10-07T07:55:17+00:00",
        selected_load_driver="rms_current_a",
        load_driver_reference_value=153.8652,
        parameters=ThermalModelParamsDict(beta_0=1.0880, beta_1=2.8979, tau_hours=0.50),
        identifiability=IdentifiabilityReport(
            is_identifiable=False,
            fit_samples_count=10941,
            fit_span_days=150.39,
            load_cv=0.5331,
            load_range=226.34,
            tau_cv_across_folds=0.0,
            boundary_hit=True,
            diagnostic_messages=["Parameters sit on bounds: beta0=1.088, beta1=2.8979, tau=0.5 (domain: [0.5, 24.0] h)"],
        ),
        conformal_uncertainty=ConformalUncertaintyParams(
            horizon_steps=8,
            horizon_scales_degc=[0.5, 0.5186, 0.5622, 0.681, 0.842, 1.0498, 1.3694, 1.596],
            block_quantile_90=5.9891,
            horizon_half_widths_degc=[2.9945, 3.1057, 3.3670, 4.0787, 5.0427, 6.2871, 8.2012, 9.5585],
            calibration_residual_median=0.2062,
            calibration_residual_mad=0.9613,
            num_calibration_origins=3551,
        ),
        test_metrics=BaselineMetricEntry(
            model_name="greybox_ode_2h_trajectory",
            mae_degc=1.6527,
            rmse_degc=2.2929,
            bias_degc=0.2473,
            marginal_coverage_90_pct=97.33,
            mean_width_degc=10.6589,
        ),
        promotion=PromotionDecision(
            status="NOT_PROMOTED",
            primary_evaluation_horizon="2_hour_multi_step_trajectory",
            mae_improvement_pct=18.59,
            passes_mae_criterion=True,
            passes_bias_criterion=False,
            passes_coverage_criterion=True,
            passes_scenario_criterion=True,
            passes_identifiability_criterion=False,
            all_criteria_met=False,
            reasons=[
                "2-Hour trajectory MAE improvement (18.59%) exceeds 5% threshold vs persistence.",
                "2-Hour trajectory signed bias (+0.25 degC) exceeds persistence bias (+0.05 degC).",
                "Identifiability failure: parameter solution sits on boundary (tau=0.50 h in [0.5, 24.0] h).",
            ],
        ),
        qualification=ThermalModelQualification(
            parameter_interpretability=QualificationStatus.UNVERIFIED,
            forecast_qualification=QualificationStatus.PENDING_VALIDATION,
            scenario_qualification=QualificationStatus.QUALIFIED,
            residual_display_qualification=QualificationStatus.DESCRIPTIVE_ONLY,
            residual_anomaly_qualification=QualificationStatus.NOT_QUALIFIED,
            cusum_qualification=QualificationStatus.DISABLED,
            maintenance_inference_qualification=QualificationStatus.DISABLED,
            dimension_reasons={
                "residual_display_qualification": "Descriptive shadow residuals only; not qualified as statistical anomaly evidence."
            },
        ),
    )


def build_runtime_reducer(
    settings: Settings,
    feedback_ledger: OperatorFeedbackLedger | None = None,
    asset_id: str | None = None,
    storage: StorageEngine | None = None,
) -> TwinReducer:
    """Build a fully wired reducer for the configured asset (episodes, evidence, OTHI, exposure, maintenance).

    Thermal qualification comes from the asset's resolved artifact, so unpromoted models stay gated.
    """
    from app.core.checkpoint import CheckpointStore
    from app.core.registry import resolve_asset_profile, resolve_model_artifact
    from app.engine.anomaly_detectors import MultiDomainAnomalyEngine
    from app.engine.electrical_episodes import ElectricalEpisodeEngine
    from app.engine.exposure import ThermalExposureEngine
    from app.engine.maintenance import MaintenanceEngine
    from app.engine.othi import OTHIEngine
    from app.engine.review import ReviewFlagEngine
    from app.engine.thermal_fallback import ThermalFallbackGate

    target_asset = asset_id or settings.default_asset_id
    profile = resolve_asset_profile(asset_id=target_asset)
    artifact = resolve_model_artifact(asset_id=target_asset)
    thermal_gate = ThermalFallbackGate.from_artifact(artifact, nominal_cadence_s=profile.expected_cadence_s)
    qual = artifact.qualification if thermal_gate.is_model_promoted else None
    ref_kva = profile.rated_kva if profile.rated_kva is not None else settings.load_reference_kva
    chk_store = CheckpointStore(storage=storage) if storage is not None else None

    return TwinReducer(
        profile=profile,
        load_reference_kva=ref_kva,
        checkpoint_cadence_events=10 if chk_store is not None else 0,
        checkpoint_store=chk_store,
        episode_engine=ElectricalEpisodeEngine(asset_id=target_asset),
        anomaly_engine=MultiDomainAnomalyEngine(
            asset_id=target_asset, qualification=artifact.qualification, profile=profile
        ),
        othi_engine=OTHIEngine(expected_cadence_seconds=profile.expected_cadence_s),
        exposure_engine=ThermalExposureEngine(asset_id=target_asset),
        maintenance_engine=MaintenanceEngine(
            feedback_ledger=feedback_ledger,
            is_model_promoted=thermal_gate.is_model_promoted,
            # Model-driven rules (e.g. MNT-THERM-002) only when the locked matrix qualifies them
            is_thermal_qualified=qual is not None
            and qual.maintenance_inference_qualification == QualificationStatus.QUALIFIED,
            cusum_qualification="ENABLED"
            if qual is not None and qual.cusum_qualification == QualificationStatus.QUALIFIED
            else "DISABLED",
        ),
        thermal_gate=thermal_gate,
        review_engine=ReviewFlagEngine(asset_id=target_asset),
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
        reducer_factory: Callable[[], TwinReducer] | None = None,
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
        # Optional: rebuilds a fresh reducer (and its stateful engines) when replay restarts or seeks
        self.reducer_factory = reducer_factory

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


def get_reducer(
    state: AppState = Depends(get_app_state),
    storage: StorageEngine = Depends(get_storage),
) -> TwinReducer:
    """Provide TwinReducer dependency."""
    if state.reducer is None:
        state.reducer = build_runtime_reducer(
            settings=state.settings,
            feedback_ledger=state.feedback_ledger,
            asset_id=state.settings.default_asset_id,
            storage=storage,
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
        from app.core.registry import resolve_model_artifact
        state.model_artifact = resolve_model_artifact(asset_id=state.settings.default_asset_id)
    return state.model_artifact


def get_scenario_simulator(
    state: AppState = Depends(get_app_state),
    artifact: CalibratedThermalModelArtifact = Depends(get_model_artifact),
) -> ScenarioSimulator:
    """Provide ScenarioSimulator dependency."""
    if state.scenario_simulator is None:
        state.scenario_simulator = ScenarioSimulator.from_artifact(artifact)
    return state.scenario_simulator
