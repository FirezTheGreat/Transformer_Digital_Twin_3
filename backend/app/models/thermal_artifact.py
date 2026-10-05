"""Pydantic Schema for Calibrated Thermal Model Artifact and Provenance."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


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

    schema_version: str = Field(default="1.1.0", description="Artifact schema version")
    model_version: str = Field(default="greybox_v1_0", description="Model semantic version")
    asset_id: str = Field(default="tripura_dt_01", description="Target transformer asset identifier")
    created_at_utc: str = Field(..., description="ISO 8601 UTC creation timestamp")
    
    selected_load_driver: str = Field(..., description="Winning load driver: 'apparent_power_kva' or 'rms_current_a'")
    load_driver_reference_value: float = Field(..., gt=0.0, description="P95 reference value on FIT partition")
    
    parameters: ThermalModelParamsDict = Field(..., description="Fitted beta_0, beta_1, tau")
    identifiability: IdentifiabilityReport = Field(..., description="Identifiability diagnostics")
    conformal_uncertainty: ConformalUncertaintyParams = Field(..., description="Calibrated empirical uncertainty bounds")
    
    baselines: Dict[str, BaselineMetricEntry] = Field(default_factory=dict, description="Metrics for baseline models on TEST (2-hour path)")
    test_metrics: BaselineMetricEntry = Field(..., description="Grey-box model metrics on untouched TEST (2-hour path)")
    promotion: PromotionDecision = Field(..., description="Locked promotion evaluation report based on 2-hour trajectory")
    
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
