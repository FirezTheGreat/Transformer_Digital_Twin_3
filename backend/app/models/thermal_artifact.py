"""Pydantic Schema for Calibrated Thermal Model Artifact and Provenance."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ThermalModelParamsDict(BaseModel):
    """Fitted thermal ODE parameters."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    beta_0: float = Field(..., ge=0.0, description="Load-independent rise (degC)")
    beta_1: float = Field(..., ge=0.0, description="Load-related rise at u=1.0 (degC)")
    tau_hours: float = Field(..., gt=0.0, description="Oil thermal time constant (hours)")


class ConformalUncertaintyParams(BaseModel):
    """Block-conformal empirical 90% uncertainty calibration parameters."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    horizon_steps: int = Field(default=8, description="Number of 15-minute forecast steps (2 hours)")
    horizon_scales_degc: List[float] = Field(..., description="Robust horizon scales s_1..s_8 in degC")
    block_quantile_90: float = Field(..., gt=0.0, description="90th percentile of block conformity scores q_0.90")
    horizon_half_widths_degc: List[float] = Field(..., description="Empirical 90% half-widths W_1..W_8 in degC")
    calibration_residual_median: float = Field(default=0.0, description="Median 1-step calibration residual in degC")
    calibration_residual_mad: float = Field(default=1.0, gt=0.0, description="MAD of 1-step calibration residuals in degC")
    num_calibration_origins: int = Field(..., ge=0, description="Number of valid 2h origins in CAL")


class IdentifiabilityReport(BaseModel):
    """Diagnostics on parameter identifiability and data sufficiency."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    is_identifiable: bool = Field(..., description="Whether model parameters are reliably identified")
    fit_samples_count: int = Field(..., ge=0)
    fit_span_days: float = Field(..., ge=0.0)
    load_cv: float = Field(..., ge=0.0)
    load_range: float = Field(..., ge=0.0)
    tau_cv_across_folds: float = Field(..., ge=0.0)
    boundary_hit: bool = Field(default=False)
    diagnostic_messages: List[str] = Field(default_factory=list)


class BaselineMetricEntry(BaseModel):
    """Performance metrics for a baseline or candidate model."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    model_name: str
    mae_degc: float
    rmse_degc: float
    bias_degc: float
    marginal_coverage_90_pct: Optional[float] = None
    simultaneous_path_coverage_90_pct: Optional[float] = None
    mean_width_degc: Optional[float] = None


class HorizonMetricBreakdown(BaseModel):
    """Per-step metrics across the 2-hour forecast trajectory."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    horizon_step: int = Field(..., ge=1, le=8)
    horizon_minutes: int = Field(...)
    model_mae_degc: float = Field(...)
    persistence_mae_degc: float = Field(...)
    mae_improvement_pct: float = Field(...)
    model_rmse_degc: float = Field(...)
    model_bias_degc: float = Field(...)
    conformal_coverage_pct: Optional[float] = None


class QualificationStatus(str, Enum):
    """Qualification authorization states for individual thermal capabilities."""
    QUALIFIED = "QUALIFIED"                     # Freshly validated and fully authorized for trusted use
    DESCRIPTIVE_ONLY = "DESCRIPTIVE_ONLY"       # Authorized strictly for shadow/informational visualization; NO diagnostic authority
    UNVERIFIED = "UNVERIFIED"                   # Physical parameter interpretation cannot be justified (e.g. boundary hit)
    PENDING_VALIDATION = "PENDING_VALIDATION"   # Awaiting formal validation under the revised policy
    NOT_QUALIFIED = "NOT_QUALIFIED"             # Evaluated and failed qualification criteria
    DISABLED = "DISABLED"                       # Explicitly deactivated by policy or missing prerequisites


class ThermalModelQualification(BaseModel):
    """Granular capability-specific qualification matrix across 7 operational dimensions."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    # 1. Physical Parameter Interpretability (Physical Attribution)
    parameter_interpretability: QualificationStatus = Field(
        default=QualificationStatus.UNVERIFIED,
        description="Whether tau and betas represent genuine physical transformer constants",
    )
    # 2. 2-Hour Autonomous Forecast Rollout (Predictive Forecasting)
    forecast_qualification: QualificationStatus = Field(
        default=QualificationStatus.PENDING_VALIDATION,
        description="Whether 2-hour autonomous forward trajectory forecasting is authorized",
    )
    # 3. 2-Hour What-If Scenario Analysis (Interactive Operator Simulation)
    scenario_qualification: QualificationStatus = Field(
        default=QualificationStatus.PENDING_VALIDATION,
        description="Whether interactive load/ambient what-if scenario projection is authorized",
    )
    # 4. Free-Running Residual Visualization (Descriptive Monitoring)
    residual_display_qualification: QualificationStatus = Field(
        default=QualificationStatus.DESCRIPTIVE_ONLY,
        description="Whether continuous free-running residual can be displayed for descriptive/shadow monitoring",
    )
    # 5. Residual-Based Anomaly Evidence (Diagnostic Episode Input)
    residual_anomaly_qualification: QualificationStatus = Field(
        default=QualificationStatus.NOT_QUALIFIED,
        description="Whether thermal residual excursions qualify as formal diagnostic evidence items",
    )
    # 6. Two-Sided CUSUM Drift Detection (Automated Drift Alarms)
    cusum_qualification: QualificationStatus = Field(
        default=QualificationStatus.DISABLED,
        description="Whether CUSUM accumulator escalation and alarm generation are authorized",
    )
    # 7. Model-Driven Maintenance & Ageing Inference (Asset Health)
    maintenance_inference_qualification: QualificationStatus = Field(
        default=QualificationStatus.DISABLED,
        description="Whether model outputs can drive automated maintenance recommendations or health index scoring",
    )
    # Deterministic evidence and rationale supporting each qualification dimension
    dimension_reasons: Dict[str, str] = Field(
        default_factory=dict,
        description="Deterministic evidence or rationale supporting each qualification dimension",
    )

    def get_reason(self, dimension_name: str) -> Optional[str]:
        """Retrieve deterministic rationale for a specific qualification dimension."""
        return self.dimension_reasons.get(dimension_name)


class PromotionDecision(BaseModel):
    """Formal decision report on model promotion against untouched TEST."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = Field(..., description="PROMOTED or NOT_PROMOTED")
    primary_evaluation_horizon: str = Field(default="2_hour_multi_step_trajectory", description="Primary promotion evaluation horizon")
    mae_improvement_pct: float = Field(..., description="Percentage MAE improvement over persistence across 2-hour trajectory")
    passes_mae_criterion: bool = Field(..., description="True if 2-hour trajectory MAE improvement >= 5%")
    passes_bias_criterion: bool = Field(..., description="True if |Bias| <= |Bias_persist|")
    passes_coverage_criterion: bool = Field(..., description="True if Test coverage in [80%, 98%]")
    passes_scenario_criterion: bool = Field(..., description="True if no safety-critical threshold missed")
    passes_identifiability_criterion: bool = Field(default=True, description="True if parameter identifiability checks passed")
    secondary_1step_closed_loop_mae_improvement_pct: Optional[float] = Field(default=None, description="1-step closed-loop MAE improvement vs persistence")
    all_criteria_met: bool = Field(...)
    reasons: List[str] = Field(default_factory=list)


class CalibratedThermalModelArtifact(BaseModel):
    """Complete frozen calibrated thermal model artifact for runtime consumption."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="1.2.0", description="Artifact schema version")
    model_version: str = Field(default="greybox_v1_0", description="Model semantic version")
    dataset_id: str = Field(..., description="Source dataset identifier")
    asset_id: str = Field(..., description="Target transformer asset identifier")
    created_at_utc: str = Field(..., description="ISO 8601 UTC creation timestamp")

    @model_validator(mode="before")
    @classmethod
    def _handle_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "dataset_id" not in data:
                data["dataset_id"] = "tripura_dev"
            if "asset_id" not in data:
                data["asset_id"] = "tripura_dt_01"
        return data
    
    selected_load_driver: Optional[str] = Field(default=None, description="Winning load driver: 'apparent_power_kva' or 'rms_current_a'")
    load_driver_reference_value: Optional[float] = Field(default=None, gt=0.0, description="P95 reference value on FIT partition")
    
    parameters: Optional[ThermalModelParamsDict] = Field(default=None, description="Fitted beta_0, beta_1, tau (None if uncalibrated)")
    identifiability: Optional[IdentifiabilityReport] = Field(default=None, description="Identifiability diagnostics")
    conformal_uncertainty: Optional[ConformalUncertaintyParams] = Field(default=None, description="Calibrated empirical uncertainty bounds")
    
    baselines: Dict[str, BaselineMetricEntry] = Field(default_factory=dict, description="Metrics for baseline models on TEST (2-hour path)")
    test_metrics: Optional[BaselineMetricEntry] = Field(default=None, description="Grey-box model metrics on untouched TEST (2-hour path)")
    promotion: PromotionDecision = Field(..., description="Locked promotion evaluation report based on 2-hour trajectory")
    qualification: ThermalModelQualification = Field(default_factory=ThermalModelQualification, description="Capability-specific qualification matrix")
    
    dataset_hashes: Dict[str, str] = Field(default_factory=dict, description="SHA-256 hashes of fit, cal, and test parquets")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional provenance and training configuration")

    def save_json(self, file_path: str | Path) -> None:
        """Serialize artifact to formatted JSON file."""
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load_json(cls, file_path: str | Path) -> CalibratedThermalModelArtifact:
        """Deserialize and validate artifact from JSON file."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Calibrated thermal model artifact not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    @classmethod
    def create_uncalibrated(cls, dataset_id: str, asset_id: str) -> CalibratedThermalModelArtifact:
        """Construct deterministic uncalibrated artifact without fake numerical constants."""
        now_str = datetime.now(timezone.utc).isoformat()
        return cls(
            schema_version="1.2.0",
            model_version="uncalibrated",
            dataset_id=dataset_id,
            asset_id=asset_id,
            created_at_utc=now_str,
            selected_load_driver="uncalibrated",
            load_driver_reference_value=None,
            parameters=None,
            identifiability=IdentifiabilityReport(
                is_identifiable=False,
                fit_samples_count=0,
                fit_span_days=0.0,
                load_cv=0.0,
                load_range=0.0,
                tau_cv_across_folds=0.0,
                boundary_hit=False,
                diagnostic_messages=["Model has not been calibrated for this dataset and asset."],
            ),
            conformal_uncertainty=None,
            test_metrics=BaselineMetricEntry(
                model_name="uncalibrated",
                mae_degc=0.0,
                rmse_degc=0.0,
                bias_degc=0.0,
            ),
            promotion=PromotionDecision(
                status="UNCALIBRATED",
                primary_evaluation_horizon="uncalibrated",
                mae_improvement_pct=0.0,
                passes_mae_criterion=False,
                passes_bias_criterion=False,
                passes_coverage_criterion=False,
                passes_scenario_criterion=False,
                passes_identifiability_criterion=False,
                all_criteria_met=False,
                reasons=["No training/calibration partition processed for this asset."],
            ),
            qualification=ThermalModelQualification(
                parameter_interpretability=QualificationStatus.UNVERIFIED,
                forecast_qualification=QualificationStatus.NOT_QUALIFIED,
                scenario_qualification=QualificationStatus.NOT_QUALIFIED,
                residual_display_qualification=QualificationStatus.NOT_QUALIFIED,
                residual_anomaly_qualification=QualificationStatus.NOT_QUALIFIED,
                cusum_qualification=QualificationStatus.DISABLED,
                maintenance_inference_qualification=QualificationStatus.DISABLED,
                dimension_reasons={"all": "Uncalibrated asset; all thermal model capabilities disabled."},
            ),
        )
