"""Phase 5.3 — Dynamic Synthetic Scenario Injector Engine.

Provides deterministic, non-mutating scenario injection for telemetry streams.
Allows controlled evaluation of anomaly detectors and digital twin reducers against
explicit ground-truth conditions without altering base physics or thermal models.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from app.models.injector import (
    GroundTruthCondition,
    GroundTruthMetadata,
    InjectedEventContext,
    InjectorScenarioConfig,
    InjectorType,
)
from app.models.telemetry import CanonicalEvent, Measurement, MeasurementQuality, QualitySeverity


# Power signals affected by electrical overload
_OVERLOAD_POWER_SIGNALS: Set[str] = {
    "active_power",
    "active_power_total",
    "active_power_l1",
    "active_power_l2",
    "active_power_l3",
    "reactive_power",
    "reactive_power_total",
    "reactive_power_l1",
    "reactive_power_l2",
    "reactive_power_l3",
    "apparent_power",
    "apparent_power_total",
    "apparent_power_l1",
    "apparent_power_l2",
    "apparent_power_l3",
}

# Current signals affected by electrical overload
_OVERLOAD_CURRENT_SIGNALS: Set[str] = {
    "current_l1",
    "current_l2",
    "current_l3",
    "current_i1",
    "current_i2",
    "current_i3",
    "current",
}


def _matches_phase(measurement_phase: Optional[str], target_phase: Optional[str]) -> bool:
    """Check if measurement phase matches target phase (handling aliases like L1/A)."""
    if target_phase is None:
        return True
    if measurement_phase is None:
        return False
    t_clean = target_phase.upper()
    m_clean = measurement_phase.upper()
    if t_clean == m_clean:
        return True
    aliases = {
        "L1": {"L1", "A", "PHASE_A"},
        "L2": {"L2", "B", "PHASE_B"},
        "L3": {"L3", "C", "PHASE_C"},
        "N": {"N", "NEUTRAL"},
    }
    target_set = aliases.get(t_clean, {t_clean})
    return m_clean in target_set


def _is_target_phase_current(signal_id: str, phase: Optional[str], target_phase: str) -> bool:
    """Check if measurement represents the current of a specific target phase."""
    t = target_phase.upper()
    s = signal_id.lower()

    # Direct signal_id matching (e.g. current_l1, current_i1)
    if t == "L1" and s in ("current_l1", "current_i1", "current_a"):
        return True
    if t == "L2" and s in ("current_l2", "current_i2", "current_b"):
        return True
    if t == "L3" and s in ("current_l3", "current_i3", "current_c"):
        return True

    # Generic signal_id "current" with phase tag
    if s in ("current", "phase_current") and _matches_phase(phase, target_phase):
        return True

    return False


class ScenarioInjectorEngine:
    """Deterministic, non-mutating scenario injection engine.

    Applies configured injection scenarios to CanonicalEvent streams, generating
    modified events alongside explicit InjectedEventContext metadata.
    """

    def __init__(self, scenarios: Optional[Sequence[InjectorScenarioConfig]] = None) -> None:
        """Initialize ScenarioInjectorEngine with optional scenarios."""
        self._scenarios: Dict[str, InjectorScenarioConfig] = {}
        self._last_observed_values: Dict[Tuple[str, str, Optional[str]], float] = {}
        self._stuck_latches: Dict[str, float] = {}

        if scenarios:
            for s in scenarios:
                self.add_scenario(s)

    def add_scenario(self, scenario: InjectorScenarioConfig) -> None:
        """Register a scenario configuration."""
        self._scenarios[scenario.scenario_id] = scenario

    def remove_scenario(self, scenario_id: str) -> Optional[InjectorScenarioConfig]:
        """Remove a scenario by ID."""
        self._stuck_latches.pop(scenario_id, None)
        return self._scenarios.pop(scenario_id, None)

    def clear_scenarios(self) -> None:
        """Clear all registered scenarios and latches."""
        self._scenarios.clear()
        self._stuck_latches.clear()

    def reset_state(self) -> None:
        """Reset internal observation history and stuck latches."""
        self._last_observed_values.clear()
        self._stuck_latches.clear()

    def get_active_scenarios(
        self, timestamp: datetime, asset_id: str
    ) -> List[InjectorScenarioConfig]:
        """Get all scenarios active at timestamp for the given asset, sorted deterministically."""
        t = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
        active = [
            s
            for s in self._scenarios.values()
            if s.asset_id == asset_id and s.is_active_at(t)
        ]
        return sorted(active, key=lambda s: (s.effective_start_time_utc, s.scenario_id))

    def inject_event(self, event: CanonicalEvent) -> Tuple[CanonicalEvent, InjectedEventContext]:
        """Inject active scenarios into a single CanonicalEvent.

        Returns:
            Tuple[CanonicalEvent, InjectedEventContext]:
                - The resulting (potentially modified) CanonicalEvent.
                - The injection context with ground-truth records (not passed to the twin).
        """
        ev_time = event.event_time_utc
        if ev_time.tzinfo is None:
            ev_time = ev_time.replace(tzinfo=timezone.utc)

        # 1. Update baseline observation cache for all numeric measurements
        for m in event.measurements:
            if isinstance(m.value, (int, float)) and not isinstance(m.value, bool):
                self._last_observed_values[(event.asset_id, m.signal_id, m.phase)] = float(m.value)

        # 2. Identify active scenarios
        active_scenarios = self.get_active_scenarios(ev_time, event.asset_id)
        if not active_scenarios:
            ctx = InjectedEventContext(
                is_injected=False,
                active_scenario_ids=[],
                ground_truth_records=[],
                modified_signals=[],
            )
            return event, ctx

        # 3. Apply active scenarios in deterministic order
        current_measurements = list(event.measurements)
        modified_signals_set: Set[str] = set()
        ground_truth_records: List[GroundTruthMetadata] = []
        active_ids: List[str] = []

        for scenario in active_scenarios:
            active_ids.append(scenario.scenario_id)
            ground_truth_records.append(scenario.to_ground_truth())
            updated_measurements: List[Measurement] = []

            for m in current_measurements:
                if not isinstance(m.value, (int, float)) or isinstance(m.value, bool):
                    updated_measurements.append(m)
                    continue

                curr_val = float(m.value)
                new_val: Optional[float] = None

                if scenario.scenario_type == InjectorType.INJ_SENSOR_SPIKE:
                    if m.signal_id == scenario.target_signal and _matches_phase(m.phase, scenario.target_phase):
                        delta = (
                            scenario.spike_delta
                            if scenario.spike_delta is not None
                            else scenario.magnitude
                        )
                        if delta is not None:
                            new_val = curr_val + delta

                elif scenario.scenario_type == InjectorType.INJ_STUCK_SENSOR:
                    if m.signal_id == scenario.target_signal and _matches_phase(m.phase, scenario.target_phase):
                        if scenario.stuck_value is not None:
                            frozen = scenario.stuck_value
                        elif scenario.scenario_id in self._stuck_latches:
                            frozen = self._stuck_latches[scenario.scenario_id]
                        else:
                            # Latch the last observed value
                            frozen = self._last_observed_values.get(
                                (event.asset_id, m.signal_id, m.phase), curr_val
                            )
                            self._stuck_latches[scenario.scenario_id] = frozen
                        new_val = frozen

                elif scenario.scenario_type == InjectorType.INJ_PERSISTENT_BIAS:
                    if m.signal_id == scenario.target_signal and _matches_phase(m.phase, scenario.target_phase):
                        delta = (
                            scenario.bias_delta
                            if scenario.bias_delta is not None
                            else scenario.magnitude
                        )
                        if delta is not None:
                            new_val = curr_val + delta

                elif scenario.scenario_type == InjectorType.INJ_SUSTAINED_OVERLOAD:
                    mult = (
                        scenario.load_multiplier
                        if scenario.load_multiplier is not None
                        else scenario.magnitude
                    )
                    if mult is not None:
                        # Scale power signals and currents
                        if m.signal_id in _OVERLOAD_POWER_SIGNALS or m.signal_id in _OVERLOAD_CURRENT_SIGNALS:
                            new_val = curr_val * mult

                elif scenario.scenario_type == InjectorType.INJ_PHASE_IMBALANCE:
                    target_phase = scenario.target_phase or "L1"
                    if _is_target_phase_current(m.signal_id, m.phase, target_phase):
                        if scenario.phase_multiplier is not None:
                            new_val = curr_val * scenario.phase_multiplier
                        elif scenario.phase_delta_a is not None:
                            new_val = curr_val + scenario.phase_delta_a
                        elif scenario.magnitude is not None:
                            new_val = curr_val * scenario.magnitude

                if new_val is not None:
                    new_val_rounded = round(new_val, 4)
                    modified_m = m.model_copy(
                        update={
                            "value": new_val_rounded,
                            "original_value": str(new_val_rounded),
                        }
                    )
                    updated_measurements.append(modified_m)
                    modified_signals_set.add(m.signal_id)
                else:
                    updated_measurements.append(m)

            current_measurements = updated_measurements

        # Construct modified CanonicalEvent envelope
        modified_event = event.model_copy(update={"measurements": current_measurements})
        ctx = InjectedEventContext(
            is_injected=len(modified_signals_set) > 0,
            active_scenario_ids=active_ids,
            ground_truth_records=ground_truth_records,
            modified_signals=sorted(list(modified_signals_set)),
        )
        return modified_event, ctx

    def inject_stream(
        self, events: Sequence[CanonicalEvent]
    ) -> List[Tuple[CanonicalEvent, InjectedEventContext]]:
        """Process an ordered stream of CanonicalEvents deterministically."""
        return [self.inject_event(ev) for ev in events]

    def inject_events_only(self, events: Sequence[CanonicalEvent]) -> List[CanonicalEvent]:
        """Convenience method returning only the modified CanonicalEvents."""
        return [self.inject_event(ev)[0] for ev in events]


# ---------------------------------------------------------------------------
# Convenience Scenario Factory Helpers
# ---------------------------------------------------------------------------


def create_sensor_spike_scenario(
    scenario_id: str,
    asset_id: str,
    start_time_utc: datetime,
    target_signal: str,
    spike_delta: float,
    duration_seconds: float = 900.0,
    target_phase: Optional[str] = None,
    severity: str = "WARNING",
) -> InjectorScenarioConfig:
    """Create a deterministic INJ_SENSOR_SPIKE scenario config."""
    return InjectorScenarioConfig(
        scenario_id=scenario_id,
        scenario_type=InjectorType.INJ_SENSOR_SPIKE,
        asset_id=asset_id,
        start_time_utc=start_time_utc,
        duration_seconds=duration_seconds,
        target_signal=target_signal,
        target_phase=target_phase,
        spike_delta=spike_delta,
        severity=severity,
    )


def create_stuck_sensor_scenario(
    scenario_id: str,
    asset_id: str,
    start_time_utc: datetime,
    target_signal: str,
    duration_seconds: float = 3600.0,
    target_phase: Optional[str] = None,
    stuck_value: Optional[float] = None,
    severity: str = "WARNING",
) -> InjectorScenarioConfig:
    """Create a deterministic INJ_STUCK_SENSOR scenario config."""
    return InjectorScenarioConfig(
        scenario_id=scenario_id,
        scenario_type=InjectorType.INJ_STUCK_SENSOR,
        asset_id=asset_id,
        start_time_utc=start_time_utc,
        duration_seconds=duration_seconds,
        target_signal=target_signal,
        target_phase=target_phase,
        stuck_value=stuck_value,
        severity=severity,
    )


def create_persistent_bias_scenario(
    scenario_id: str,
    asset_id: str,
    start_time_utc: datetime,
    target_signal: str,
    bias_delta: float,
    duration_seconds: float = 7200.0,
    target_phase: Optional[str] = None,
    severity: str = "WARNING",
) -> InjectorScenarioConfig:
    """Create a deterministic INJ_PERSISTENT_BIAS scenario config."""
    return InjectorScenarioConfig(
        scenario_id=scenario_id,
        scenario_type=InjectorType.INJ_PERSISTENT_BIAS,
        asset_id=asset_id,
        start_time_utc=start_time_utc,
        duration_seconds=duration_seconds,
        target_signal=target_signal,
        target_phase=target_phase,
        bias_delta=bias_delta,
        severity=severity,
    )


def create_sustained_overload_scenario(
    scenario_id: str,
    asset_id: str,
    start_time_utc: datetime,
    load_multiplier: float,
    duration_seconds: float = 7200.0,
    severity: str = "CRITICAL",
) -> InjectorScenarioConfig:
    """Create a deterministic INJ_SUSTAINED_OVERLOAD scenario config."""
    return InjectorScenarioConfig(
        scenario_id=scenario_id,
        scenario_type=InjectorType.INJ_SUSTAINED_OVERLOAD,
        asset_id=asset_id,
        start_time_utc=start_time_utc,
        duration_seconds=duration_seconds,
        load_multiplier=load_multiplier,
        severity=severity,
    )


def create_phase_imbalance_scenario(
    scenario_id: str,
    asset_id: str,
    start_time_utc: datetime,
    target_phase: str = "L1",
    phase_multiplier: Optional[float] = None,
    phase_delta_a: Optional[float] = None,
    duration_seconds: float = 3600.0,
    severity: str = "WARNING",
) -> InjectorScenarioConfig:
    """Create a deterministic INJ_PHASE_IMBALANCE scenario config."""
    if phase_multiplier is None and phase_delta_a is None:
        phase_multiplier = 2.0

    return InjectorScenarioConfig(
        scenario_id=scenario_id,
        scenario_type=InjectorType.INJ_PHASE_IMBALANCE,
        asset_id=asset_id,
        start_time_utc=start_time_utc,
        duration_seconds=duration_seconds,
        target_phase=target_phase,
        phase_multiplier=phase_multiplier,
        phase_delta_a=phase_delta_a,
        severity=severity,
    )
