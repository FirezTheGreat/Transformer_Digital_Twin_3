"""Phase 5.3 — Dynamic Synthetic Scenario Injector Models & Contracts.

Provides typed configuration, ground-truth metadata, and injection context schemas
for controlled deterministic evaluation of anomaly detection and digital twin engines.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class InjectorType(str, Enum):
    """The 5 canonical synthetic scenario injection types."""
    INJ_SENSOR_SPIKE = "INJ_SENSOR_SPIKE"
    INJ_STUCK_SENSOR = "INJ_STUCK_SENSOR"
    INJ_PERSISTENT_BIAS = "INJ_PERSISTENT_BIAS"
    INJ_SUSTAINED_OVERLOAD = "INJ_SUSTAINED_OVERLOAD"
    INJ_PHASE_IMBALANCE = "INJ_PHASE_IMBALANCE"


class GroundTruthCondition(str, Enum):
    """Explicit ground-truth classifications for injected scenarios."""
    SENSOR_SPIKE_TRANSIENT = "SENSOR_SPIKE_TRANSIENT"
    STUCK_SENSOR = "STUCK_SENSOR"
    PERSISTENT_SENSOR_BIAS = "PERSISTENT_SENSOR_BIAS"
    SUSTAINED_ELECTRICAL_OVERLOAD = "SUSTAINED_ELECTRICAL_OVERLOAD"
    PHASE_CURRENT_IMBALANCE = "PHASE_CURRENT_IMBALANCE"


class GroundTruthMetadata(BaseModel):
    """Deterministic ground-truth record for scenario evaluation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(..., description="Unique scenario instance identifier")
    scenario_type: InjectorType = Field(..., description="Canonical injector type")
    asset_id: str = Field(..., description="Target transformer asset identifier")
    start_time_utc: datetime = Field(..., description="Inclusive injection start time in UTC")
    end_time_utc: datetime = Field(..., description="Exclusive injection end time in UTC")
    severity: str = Field(default="WARNING", description="Intended scenario severity level or tag")
    affected_signals: List[str] = Field(..., description="List of canonical signal IDs modified")
    affected_phases: List[str] = Field(default_factory=list, description="List of phases affected if applicable")
    injection_parameters: Dict[str, Any] = Field(..., description="Complete injection parameter dictionary")
    ground_truth_condition: GroundTruthCondition = Field(..., description="Canonical ground-truth condition")
    is_data_quality_anomaly: bool = Field(
        ...,
        description="True if anomaly is instrumentation/sensor quality; False if genuine physical stress",
    )
    description: str = Field(..., description="Human-readable description of the injected ground truth")
    provenance: str = Field(
        default="SYNTHETIC_INJECTOR_TESTING_LAYER",
        description="Provenance tag marking this as synthetic evaluation tooling",
    )


class InjectorScenarioConfig(BaseModel):
    """Configuration for an individual deterministic scenario injector."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(..., description="Unique scenario identifier")
    scenario_type: InjectorType = Field(..., description="Scenario type from the 5 canonical types")
    asset_id: str = Field(..., description="Target asset ID")
    start_time_utc: datetime = Field(..., description="Start timestamp of injection (inclusive)")
    end_time_utc: Optional[datetime] = Field(
        default=None, description="End timestamp of injection (exclusive). Required if duration_seconds is None"
    )
    duration_seconds: Optional[float] = Field(
        default=None, ge=0.0, description="Duration in seconds. Used if end_time_utc is None"
    )
    target_signal: Optional[str] = Field(
        default=None,
        description="Target signal ID (e.g. 'oti_degc', 'current_l1'). Required for sensor/bias/stuck injections",
    )
    target_phase: Optional[str] = Field(
        default=None,
        description="Optional phase filter (e.g. 'L1', 'L2', 'L3', 'N') for signal-specific injections",
    )
    magnitude: Optional[float] = Field(
        default=None,
        description="Generic magnitude parameter (interpreted per scenario type if specific delta/multiplier is None)",
    )
    spike_delta: Optional[float] = Field(
        default=None, description="Additive spike delta for INJ_SENSOR_SPIKE"
    )
    bias_delta: Optional[float] = Field(
        default=None, description="Signed additive bias for INJ_PERSISTENT_BIAS"
    )
    load_multiplier: Optional[float] = Field(
        default=None, ge=0.0, description="Electrical load scaling multiplier for INJ_SUSTAINED_OVERLOAD"
    )
    phase_multiplier: Optional[float] = Field(
        default=None, ge=0.0, description="Phase current scaling multiplier for INJ_PHASE_IMBALANCE"
    )
    phase_delta_a: Optional[float] = Field(
        default=None, description="Additive phase current delta in Amperes for INJ_PHASE_IMBALANCE"
    )
    stuck_value: Optional[float] = Field(
        default=None,
        description="Optional explicit freeze value for INJ_STUCK_SENSOR. If None, uses last observed value",
    )
    severity: str = Field(default="WARNING", description="Scenario severity metadata")
    seed: Optional[int] = Field(
        default=None, description="Deterministic random seed if scenario requires stochastic variations"
    )
    custom_parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Additional custom metadata or parameters"
    )

    @model_validator(mode="after")
    def validate_scenario(self) -> InjectorScenarioConfig:
        """Validate temporal boundaries and scenario-specific required fields."""
        # 1. Resolve end_time_utc from duration_seconds if needed
        if self.end_time_utc is None and self.duration_seconds is None:
            raise ValueError(
                f"Scenario '{self.scenario_id}' must specify either 'end_time_utc' or 'duration_seconds'"
            )
        
        start = self.start_time_utc
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
            
        end = self.end_time_utc
        if end is None:
            end = start + timedelta(seconds=self.duration_seconds or 0.0)
        elif end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        if end <= start:
            raise ValueError(
                f"Scenario '{self.scenario_id}' end_time_utc ({end}) must be strictly greater than start_time_utc ({start})"
            )

        # 2. Validate type-specific constraints
        if self.scenario_type in (
            InjectorType.INJ_SENSOR_SPIKE,
            InjectorType.INJ_STUCK_SENSOR,
            InjectorType.INJ_PERSISTENT_BIAS,
        ):
            if not self.target_signal:
                raise ValueError(
                    f"Scenario '{self.scenario_id}' of type {self.scenario_type.value} requires 'target_signal'"
                )

        if self.scenario_type == InjectorType.INJ_SENSOR_SPIKE:
            if self.spike_delta is None and self.magnitude is None:
                raise ValueError(
                    f"INJ_SENSOR_SPIKE scenario '{self.scenario_id}' requires 'spike_delta' or 'magnitude'"
                )

        if self.scenario_type == InjectorType.INJ_PERSISTENT_BIAS:
            if self.bias_delta is None and self.magnitude is None:
                raise ValueError(
                    f"INJ_PERSISTENT_BIAS scenario '{self.scenario_id}' requires 'bias_delta' or 'magnitude'"
                )

        if self.scenario_type == InjectorType.INJ_SUSTAINED_OVERLOAD:
            if self.load_multiplier is None and self.magnitude is None:
                raise ValueError(
                    f"INJ_SUSTAINED_OVERLOAD scenario '{self.scenario_id}' requires 'load_multiplier' or 'magnitude'"
                )

        if self.scenario_type == InjectorType.INJ_PHASE_IMBALANCE:
            if (
                self.phase_multiplier is None
                and self.phase_delta_a is None
                and self.magnitude is None
            ):
                raise ValueError(
                    f"INJ_PHASE_IMBALANCE scenario '{self.scenario_id}' requires 'phase_multiplier', 'phase_delta_a', or 'magnitude'"
                )
            if not self.target_phase:
                raise ValueError(
                    f"INJ_PHASE_IMBALANCE scenario '{self.scenario_id}' requires 'target_phase' (e.g. 'L1')"
                )

        return self

    @property
    def effective_end_time_utc(self) -> datetime:
        """Get the resolved UTC end timestamp."""
        start = self.start_time_utc if self.start_time_utc.tzinfo is not None else self.start_time_utc.replace(tzinfo=timezone.utc)
        if self.end_time_utc is not None:
            return self.end_time_utc if self.end_time_utc.tzinfo is not None else self.end_time_utc.replace(tzinfo=timezone.utc)
        return start + timedelta(seconds=self.duration_seconds or 0.0)

    @property
    def effective_start_time_utc(self) -> datetime:
        """Get the resolved UTC start timestamp."""
        return self.start_time_utc if self.start_time_utc.tzinfo is not None else self.start_time_utc.replace(tzinfo=timezone.utc)

    def is_active_at(self, timestamp: datetime) -> bool:
        """Check if scenario is active at timestamp under half-open [start, end) semantics."""
        t = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
        return self.effective_start_time_utc <= t < self.effective_end_time_utc

    def to_ground_truth(self) -> GroundTruthMetadata:
        """Construct the explicit GroundTruthMetadata record for this scenario."""
        affected_sigs: List[str] = []
        affected_ph: List[str] = []
        is_dq = True
        desc = ""
        params: Dict[str, Any] = dict(self.custom_parameters)
        if self.seed is not None:
            params["seed"] = self.seed

        if self.scenario_type == InjectorType.INJ_SENSOR_SPIKE:
            gt_cond = GroundTruthCondition.SENSOR_SPIKE_TRANSIENT
            delta = self.spike_delta if self.spike_delta is not None else self.magnitude
            params["spike_delta"] = delta
            affected_sigs = [self.target_signal or ""]
            if self.target_phase:
                affected_ph = [self.target_phase]
            is_dq = True
            desc = f"Sensor spike anomaly of {delta} on signal '{self.target_signal}'"

        elif self.scenario_type == InjectorType.INJ_STUCK_SENSOR:
            gt_cond = GroundTruthCondition.STUCK_SENSOR
            params["stuck_value"] = self.stuck_value
            affected_sigs = [self.target_signal or ""]
            if self.target_phase:
                affected_ph = [self.target_phase]
            is_dq = True
            desc = f"Stuck sensor anomaly holding value on signal '{self.target_signal}'"

        elif self.scenario_type == InjectorType.INJ_PERSISTENT_BIAS:
            gt_cond = GroundTruthCondition.PERSISTENT_SENSOR_BIAS
            delta = self.bias_delta if self.bias_delta is not None else self.magnitude
            params["bias_delta"] = delta
            affected_sigs = [self.target_signal or ""]
            if self.target_phase:
                affected_ph = [self.target_phase]
            is_dq = True
            desc = f"Persistent sensor bias of {delta} on signal '{self.target_signal}'"

        elif self.scenario_type == InjectorType.INJ_SUSTAINED_OVERLOAD:
            gt_cond = GroundTruthCondition.SUSTAINED_ELECTRICAL_OVERLOAD
            mult = self.load_multiplier if self.load_multiplier is not None else self.magnitude
            params["load_multiplier"] = mult
            affected_sigs = [
                "active_power",
                "active_power_total",
                "reactive_power",
                "reactive_power_total",
                "apparent_power",
                "apparent_power_total",
                "current_l1",
                "current_l2",
                "current_l3",
            ]
            is_dq = False
            desc = f"Sustained electrical load scaling by {mult}x across power and current drivers"

        elif self.scenario_type == InjectorType.INJ_PHASE_IMBALANCE:
            gt_cond = GroundTruthCondition.PHASE_CURRENT_IMBALANCE
            if self.phase_multiplier is not None:
                params["phase_multiplier"] = self.phase_multiplier
            elif self.magnitude is not None:
                params["phase_multiplier"] = self.magnitude
            if self.phase_delta_a is not None:
                params["phase_delta_a"] = self.phase_delta_a
            target_ph = self.target_phase or "L1"
            affected_sigs = [f"current_{target_ph.lower()}", "current", f"current_i{target_ph[-1]}"]
            affected_ph = [target_ph]
            is_dq = False
            desc = f"Phase current imbalance on phase {target_ph} with params {params}"

        return GroundTruthMetadata(
            scenario_id=self.scenario_id,
            scenario_type=self.scenario_type,
            asset_id=self.asset_id,
            start_time_utc=self.effective_start_time_utc,
            end_time_utc=self.effective_end_time_utc,
            severity=self.severity,
            affected_signals=affected_sigs,
            affected_phases=affected_ph,
            injection_parameters=params,
            ground_truth_condition=gt_cond,
            is_data_quality_anomaly=is_dq,
            description=desc,
        )


class InjectedEventContext(BaseModel):
    """Metadata accompanying an injected CanonicalEvent for offline evaluation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    is_injected: bool = Field(..., description="Whether one or more injections modified the event")
    active_scenario_ids: List[str] = Field(default_factory=list, description="IDs of scenarios active at event timestamp")
    ground_truth_records: List[GroundTruthMetadata] = Field(
        default_factory=list, description="Ground truth metadata for all active scenarios"
    )
    modified_signals: List[str] = Field(
        default_factory=list, description="List of signal IDs whose measurement values were changed"
    )
