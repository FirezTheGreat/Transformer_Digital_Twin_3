"""Phase 5.1 — Stateful Electrical Episode Engine.

Implements the deterministic temporal state machine that converts instantaneous
electrical features (current imbalance, voltage imbalance, neutral current ratio,
low power factor, P-Q-S inconsistency) into stateful operational episodes.

Lifecycle FSM:
NORMAL -> CONDITION DETECTED (CANDIDATE) -> PERSISTENCE -> ACTIVE EPISODE -> RECOVERY -> CLOSED EPISODE
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.electrical_episode import (
    DEFAULT_ELECTRICAL_THRESHOLDS,
    ElectricalEpisode,
    ElectricalEpisodeState,
    ElectricalEpisodeThresholds,
    ElectricalEpisodeType,
    EpisodeSeverity,
    EpisodeStatus,
    EvidenceGrade,
)
from app.models.features import DerivedFeatures
from app.models.telemetry import CanonicalEvent, QualitySeverity


class ElectricalEpisodeEngine:
    """Deterministic stateful temporal engine for tracking electrical anomaly episodes."""

    def __init__(
        self,
        asset_id: str,
        thresholds: Optional[Dict[ElectricalEpisodeType, ElectricalEpisodeThresholds]] = None,
        max_gap_seconds: float = 3600.0,
    ) -> None:
        self.asset_id = str(asset_id)
        self.thresholds = dict(thresholds or DEFAULT_ELECTRICAL_THRESHOLDS)
        self.max_gap_seconds = float(max_gap_seconds)

        # Stateful accumulators
        self.active_episodes: Dict[ElectricalEpisodeType, ElectricalEpisode] = {}
        self.closed_episodes: List[ElectricalEpisode] = []
        self.recurrence_counts: Dict[ElectricalEpisodeType, int] = {}
        self.persistence_timers: Dict[ElectricalEpisodeType, float] = {}
        self.recovery_timers: Dict[ElectricalEpisodeType, float] = {}
        self.evidence_counters: Dict[ElectricalEpisodeType, int] = {}
        self.last_event_time_utc: Optional[datetime] = None
        self.latched_episodes: Set[ElectricalEpisodeType] = set()
        self.cleared_episodes: Set[ElectricalEpisodeType] = set()

    def clear_latched_episode(self, ep_type: ElectricalEpisodeType) -> None:
        """Mark a latched episode as cleared by authorized resolution."""
        self.cleared_episodes.add(ep_type)
        self.latched_episodes.discard(ep_type)

    def reset(self) -> None:
        """Reset internal stateful accumulators and timers."""
        self.active_episodes.clear()
        self.closed_episodes.clear()
        self.recurrence_counts.clear()
        self.persistence_timers.clear()
        self.recovery_timers.clear()
        self.evidence_counters.clear()
        self.latched_episodes.clear()
        self.cleared_episodes.clear()
        self.last_event_time_utc = None

    def evaluate_step(
        self,
        event: CanonicalEvent,
        derived: DerivedFeatures,
    ) -> List[ElectricalEpisode]:
        """Evaluate one discrete canonical event and derived feature frame.

        Args:
            event: Canonical telemetry event envelope.
            derived: Deterministic derived electrical features.

        Returns:
            List[ElectricalEpisode]: List of all currently open (CANDIDATE, ACTIVE, RECOVERING) episodes.
        """
        ev_time = event.event_time_utc
        if ev_time.tzinfo is None:
            ev_time = ev_time.replace(tzinfo=timezone.utc)

        # 1. Timing and Gap Management
        dt_seconds = 0.0
        is_gap = False

        if self.last_event_time_utc is not None:
            dt = (ev_time - self.last_event_time_utc).total_seconds()
            if dt < 0:
                # Late/out-of-order event: do not rewind state; skip progression per Store + Flag semantics
                return list(self.active_episodes.values())
            dt_seconds = dt

            if dt_seconds > self.max_gap_seconds:
                is_gap = True

        # Handle monitoring gap across all currently open episodes
        if is_gap:
            for ep_type, ep in list(self.active_episodes.items()):
                if ep.status == EpisodeStatus.CANDIDATE:
                    # Gaps reset candidate persistence to prevent bridging over unobserved periods
                    del self.active_episodes[ep_type]
                    self.persistence_timers[ep_type] = 0.0
                elif ep.status in (EpisodeStatus.ACTIVE, EpisodeStatus.RECOVERING):
                    # Active episodes are marked with monitoring gap flag and recovery timers reset
                    self.active_episodes[ep_type] = ep.model_copy(update={"is_monitoring_gap": True})
                    self.recovery_timers[ep_type] = 0.0

        # 2. Evaluate each electrical condition independently
        for ep_type, config in self.thresholds.items():
            self._evaluate_condition(
                ep_type=ep_type,
                config=config,
                event=event,
                derived=derived,
                ev_time=ev_time,
                dt_seconds=dt_seconds,
            )

        self.last_event_time_utc = ev_time
        return list(self.active_episodes.values())

    def _evaluate_condition(
        self,
        ep_type: ElectricalEpisodeType,
        config: ElectricalEpisodeThresholds,
        event: CanonicalEvent,
        derived: DerivedFeatures,
        ev_time: datetime,
        dt_seconds: float,
    ) -> None:
        """Evaluate a single electrical condition type against its FSM state."""
        val, is_valid = self._extract_and_validate_feature(ep_type, config, derived, event)
        current_ep = self.active_episodes.get(ep_type)

        if not is_valid or val is None:
            # Quality Gating: If telemetry is invalid/BAD/missing, do not trigger false candidates.
            # If an episode is already ACTIVE, hold state without false recovery or false escalation.
            return

        is_abnormal, is_critical, is_recovery = self._check_thresholds(ep_type, config, val)

        # ------------------------------------------------------------------
        # FSM Transition Logic
        # ------------------------------------------------------------------
        if current_ep is None:
            # State: NORMAL -> CONDITION DETECTED (CANDIDATE)
            if is_abnormal:
                initial_sev = EpisodeSeverity.CRITICAL if is_critical else EpisodeSeverity.WARNING
                rec_count = self.recurrence_counts.get(ep_type, 0) + 1

                evidence = self._build_evidence_item(
                    ep_type=ep_type,
                    config=config,
                    event=event,
                    ev_time=ev_time,
                    observed_val=val,
                    severity_enum=initial_sev,
                )

                candidate_ep = ElectricalEpisode(
                    episode_id=f"ep_{self.asset_id}_{ep_type.value.lower()}_{ev_time.strftime('%Y%m%d%H%M%S')}_{rec_count}",
                    asset_id=self.asset_id,
                    episode_type=ep_type,
                    category=self._get_category(ep_type),
                    status=EpisodeStatus.CANDIDATE,
                    severity=initial_sev,
                    start_time_utc=ev_time,
                    activation_time_utc=None,
                    last_active_time_utc=ev_time,
                    recovery_start_time_utc=None,
                    closed_time_utc=None,
                    duration_seconds=0.0,
                    peak_value=val,
                    peak_severity=initial_sev,
                    initial_value=val,
                    last_observed_value=val,
                    recurrence_count=rec_count,
                    evidence_grade=self._get_evidence_grade(ep_type),
                    primary_reason=self._get_primary_reason(ep_type, initial_sev, val),
                    hypothesis_codes=self._get_hypotheses(ep_type),
                    evidence_items=[evidence],
                    is_monitoring_gap=False,
                )

                self.persistence_timers[ep_type] = 0.0
                self.recovery_timers[ep_type] = 0.0

                if config.persistence_seconds <= 0.0:
                    # Immediate activation when persistence is 0
                    candidate_ep = candidate_ep.model_copy(
                        update={
                            "status": EpisodeStatus.ACTIVE,
                            "activation_time_utc": ev_time,
                        }
                    )
                    self.recurrence_counts[ep_type] = rec_count

                self.active_episodes[ep_type] = candidate_ep

        elif current_ep.status == EpisodeStatus.CANDIDATE:
            # State: CANDIDATE -> (accumulating timer or cancelled or ACTIVE)
            if is_abnormal:
                timer = self.persistence_timers.get(ep_type, 0.0) + dt_seconds
                self.persistence_timers[ep_type] = timer

                cur_sev = EpisodeSeverity.CRITICAL if is_critical else current_ep.severity
                peak_v = self._update_peak_value(ep_type, current_ep.peak_value, val)
                peak_s = EpisodeSeverity.CRITICAL if (current_ep.peak_severity == EpisodeSeverity.CRITICAL or is_critical) else EpisodeSeverity.WARNING
                dur = (ev_time - current_ep.start_time_utc).total_seconds()

                evidence = self._build_evidence_item(
                    ep_type=ep_type,
                    config=config,
                    event=event,
                    ev_time=ev_time,
                    observed_val=val,
                    severity_enum=cur_sev,
                )

                updated_ep = current_ep.model_copy(
                    update={
                        "severity": cur_sev,
                        "last_active_time_utc": ev_time,
                        "duration_seconds": dur,
                        "peak_value": peak_v,
                        "peak_severity": peak_s,
                        "last_observed_value": val,
                        "evidence_items": current_ep.evidence_items + [evidence],
                    }
                )

                if timer >= config.persistence_seconds:
                    # Persistence satisfied -> ACTIVE EPISODE
                    updated_ep = updated_ep.model_copy(
                        update={
                            "status": EpisodeStatus.ACTIVE,
                            "activation_time_utc": ev_time,
                        }
                    )
                    self.recurrence_counts[ep_type] = updated_ep.recurrence_count

                self.active_episodes[ep_type] = updated_ep
            else:
                # Condition cleared before reaching persistence -> Transient anomaly dropped
                del self.active_episodes[ep_type]
                self.persistence_timers[ep_type] = 0.0

        elif current_ep.status == EpisodeStatus.ACTIVE:
            # State: ACTIVE -> (continue active, escalate, or enter RECOVERING)
            if is_abnormal:
                if ep_type == ElectricalEpisodeType.PROTECTION_TRIP:
                    self.latched_episodes.add(ep_type)
                    self.cleared_episodes.discard(ep_type)
                self.recovery_timers[ep_type] = 0.0
                cur_sev = EpisodeSeverity.CRITICAL if is_critical else current_ep.severity
                peak_v = self._update_peak_value(ep_type, current_ep.peak_value, val)
                peak_s = EpisodeSeverity.CRITICAL if (current_ep.peak_severity == EpisodeSeverity.CRITICAL or is_critical) else current_ep.peak_severity
                dur = (ev_time - current_ep.start_time_utc).total_seconds()

                evidence = self._build_evidence_item(
                    ep_type=ep_type,
                    config=config,
                    event=event,
                    ev_time=ev_time,
                    observed_val=val,
                    severity_enum=cur_sev,
                )

                self.active_episodes[ep_type] = current_ep.model_copy(
                    update={
                        "severity": cur_sev,
                        "last_active_time_utc": ev_time,
                        "duration_seconds": dur,
                        "peak_value": peak_v,
                        "peak_severity": peak_s,
                        "last_observed_value": val,
                        "evidence_items": current_ep.evidence_items + [evidence],
                    }
                )

            elif is_recovery:
                if ep_type == ElectricalEpisodeType.PROTECTION_TRIP and ep_type not in self.cleared_episodes:
                    # Protection trip is latched: normal telemetry alone does not recover without authorization
                    dur = (ev_time - current_ep.start_time_utc).total_seconds()
                    self.active_episodes[ep_type] = current_ep.model_copy(
                        update={
                            "last_active_time_utc": ev_time,
                            "duration_seconds": dur,
                            "last_observed_value": val,
                        }
                    )
                else:
                    # Value dropped below recovery threshold T_off -> enter RECOVERING
                    self.recovery_timers[ep_type] = 0.0
                    dur = (ev_time - current_ep.start_time_utc).total_seconds()

                    if config.recovery_seconds <= 0.0:
                        # Immediate closure
                        closed_ep = current_ep.model_copy(
                            update={
                                "status": EpisodeStatus.CLOSED,
                                "last_active_time_utc": ev_time,
                                "recovery_start_time_utc": ev_time,
                                "closed_time_utc": ev_time,
                                "duration_seconds": dur,
                                "last_observed_value": val,
                            }
                        )
                        self.closed_episodes.append(closed_ep)
                        del self.active_episodes[ep_type]
                    else:
                        self.active_episodes[ep_type] = current_ep.model_copy(
                            update={
                                "status": EpisodeStatus.RECOVERING,
                                "last_active_time_utc": ev_time,
                                "recovery_start_time_utc": ev_time,
                                "duration_seconds": dur,
                                "last_observed_value": val,
                            }
                        )
            else:
                # In hysteresis band (between T_off and T_on): remain ACTIVE
                dur = (ev_time - current_ep.start_time_utc).total_seconds()
                self.active_episodes[ep_type] = current_ep.model_copy(
                    update={
                        "last_active_time_utc": ev_time,
                        "duration_seconds": dur,
                        "last_observed_value": val,
                    }
                )

        elif current_ep.status == EpisodeStatus.RECOVERING:
            # State: RECOVERING -> (re-excursion to ACTIVE or close when recovery timer completes)
            if is_abnormal:
                # Chatter prevention: re-excursion back above T_on returns to ACTIVE immediately
                self.recovery_timers[ep_type] = 0.0
                cur_sev = EpisodeSeverity.CRITICAL if is_critical else current_ep.severity
                peak_v = self._update_peak_value(ep_type, current_ep.peak_value, val)
                peak_s = EpisodeSeverity.CRITICAL if (current_ep.peak_severity == EpisodeSeverity.CRITICAL or is_critical) else current_ep.peak_severity
                dur = (ev_time - current_ep.start_time_utc).total_seconds()

                evidence = self._build_evidence_item(
                    ep_type=ep_type,
                    config=config,
                    event=event,
                    ev_time=ev_time,
                    observed_val=val,
                    severity_enum=cur_sev,
                )

                self.active_episodes[ep_type] = current_ep.model_copy(
                    update={
                        "status": EpisodeStatus.ACTIVE,
                        "severity": cur_sev,
                        "recovery_start_time_utc": None,
                        "last_active_time_utc": ev_time,
                        "duration_seconds": dur,
                        "peak_value": peak_v,
                        "peak_severity": peak_s,
                        "last_observed_value": val,
                        "evidence_items": current_ep.evidence_items + [evidence],
                    }
                )

            elif is_recovery:
                rec_timer = self.recovery_timers.get(ep_type, 0.0) + dt_seconds
                self.recovery_timers[ep_type] = rec_timer
                dur = (ev_time - current_ep.start_time_utc).total_seconds()

                if rec_timer >= config.recovery_seconds:
                    # Clean recovery period satisfied -> CLOSE EPISODE
                    closed_ep = current_ep.model_copy(
                        update={
                            "status": EpisodeStatus.CLOSED,
                            "last_active_time_utc": ev_time,
                            "closed_time_utc": ev_time,
                            "duration_seconds": dur,
                            "last_observed_value": val,
                        }
                    )
                    self.closed_episodes.append(closed_ep)
                    del self.active_episodes[ep_type]
                    self.recovery_timers[ep_type] = 0.0
                else:
                    self.active_episodes[ep_type] = current_ep.model_copy(
                        update={
                            "last_active_time_utc": ev_time,
                            "duration_seconds": dur,
                            "last_observed_value": val,
                        }
                    )
            else:
                # In hysteresis band: hold recovery status without resetting timer
                dur = (ev_time - current_ep.start_time_utc).total_seconds()
                self.active_episodes[ep_type] = current_ep.model_copy(
                    update={
                        "last_active_time_utc": ev_time,
                        "duration_seconds": dur,
                        "last_observed_value": val,
                    }
                )

    # -----------------------------------------------------------------------
    # Feature Extraction & Quality Prerequisites
    # -----------------------------------------------------------------------

    def _extract_and_validate_feature(
        self,
        ep_type: ElectricalEpisodeType,
        config: ElectricalEpisodeThresholds,
        derived: DerivedFeatures,
        event: Optional[CanonicalEvent] = None,
    ) -> Tuple[Optional[float], bool]:
        """Extract canonical feature and enforce prerequisite validity floors."""
        if ep_type == ElectricalEpisodeType.PROTECTION_TRIP:
            if event is None:
                return 0.0, True
            is_trip = False
            has_prot_signal = False
            for m in event.measurements:
                s_id = m.signal_id.lower()
                flags = m.quality.flags if m.quality else []
                if s_id in (
                    "oil_temp_trip_flag",
                    "top_oil_temp_trip",
                    "breaker_trip",
                    "buchholz_trip",
                    "wti",
                    "oti_t",
                    "oti_trip",
                    "oti_trip_contact",
                    "lv_breaker_trip",
                    "hv_fuse_operated",
                    "prd_operated",
                    "pressure_relief_operated",
                ) or "DIRECT_TRIP" in flags:
                    has_prot_signal = True
                    val = m.value
                    if val is True or val == 1 or str(val).lower() in ("true", "1", "trip", "tripped"):
                        is_trip = True
                        break
                elif s_id in ("lv_breaker_closed", "52a_status"):
                    has_prot_signal = True
                    val = m.value
                    if val in (0, 0.0, "0", False, "false", "open", "OPEN"):
                        is_trip = True
                        break
            if "PROTECTION_TRIP_ACTIVE" in event.event_quality_flags or "DIRECT_PROTECTION_TRIP" in event.event_quality_flags:
                is_trip = True
                has_prot_signal = True
            if not has_prot_signal:
                return 0.0, True
            return (1.0 if is_trip else 0.0), True

        if ep_type == ElectricalEpisodeType.CURRENT_IMBALANCE:
            val = derived.current_magnitude_imbalance_pct
            if val is None or not math.isfinite(val):
                return None, False
            if derived.current_mean_a is not None and derived.current_mean_a < config.min_current_a:
                # Suppress when transformer is essentially unloaded (<5A noise floor)
                return val, False
            return val, True

        elif ep_type == ElectricalEpisodeType.VOLTAGE_IMBALANCE:
            val = derived.voltage_magnitude_imbalance_pct
            if val is None or not math.isfinite(val):
                return None, False
            return val, True

        elif ep_type == ElectricalEpisodeType.NEUTRAL_CURRENT_RATIO:
            val = derived.neutral_current_ratio
            if val is None or not math.isfinite(val):
                return None, False
            if derived.current_mean_a is not None and derived.current_mean_a < config.min_current_a:
                # Suppress when phase current is below denominator floor
                return val, False
            return val, True

        elif ep_type == ElectricalEpisodeType.LOW_POWER_FACTOR:
            val = derived.power_factor_derived
            if val is None or not math.isfinite(val):
                return None, False
            # CRITICAL PREREQUISITE: Only evaluate PF under meaningful load (S >= 10 kVA)
            s_kva = derived.apparent_power_derived_kva
            if s_kva is None or s_kva < config.min_load_kva:
                return val, False
            return val, True

        elif ep_type == ElectricalEpisodeType.PQS_INCONSISTENCY:
            val = derived.pqs_inconsistency
            if val is None or not math.isfinite(val):
                return None, False
            s_kva = derived.apparent_power_derived_kva
            if s_kva is None or s_kva < config.min_load_kva:
                return val, False
            return val, True

        return None, False

    def _check_thresholds(
        self,
        ep_type: ElectricalEpisodeType,
        config: ElectricalEpisodeThresholds,
        val: float,
    ) -> Tuple[bool, bool, bool]:
        """Check if value is abnormal, critical, or in recovery band."""
        if ep_type == ElectricalEpisodeType.LOW_POWER_FACTOR:
            # Low power factor: lower is worse
            is_critical = val <= config.critical_threshold
            is_warning = val <= config.warning_threshold
            is_abnormal = is_warning
            is_recovery = val > config.recovery_threshold
        else:
            # Imbalance, neutral ratio, PQS inconsistency: higher is worse
            is_critical = val >= config.critical_threshold
            is_warning = val >= config.warning_threshold
            is_abnormal = is_warning
            is_recovery = val < config.recovery_threshold

        return is_abnormal, is_critical, is_recovery

    def _update_peak_value(
        self,
        ep_type: ElectricalEpisodeType,
        curr_peak: float,
        new_val: float,
    ) -> float:
        """Update peak/worst value during an episode."""
        if ep_type == ElectricalEpisodeType.LOW_POWER_FACTOR:
            return min(curr_peak, new_val)
        return max(curr_peak, new_val)

    # -----------------------------------------------------------------------
    # Evidence & Taxonomy Helper Methods
    # -----------------------------------------------------------------------

    def _get_category(self, ep_type: ElectricalEpisodeType) -> AnomalyCategory:
        """Map episode type to canonical operator category."""
        if ep_type == ElectricalEpisodeType.PROTECTION_TRIP:
            return AnomalyCategory.PROTECTION_OR_OIL_STATUS
        elif ep_type in (ElectricalEpisodeType.CURRENT_IMBALANCE, ElectricalEpisodeType.NEUTRAL_CURRENT_RATIO):
            return AnomalyCategory.PHASE_OR_NEUTRAL
        elif ep_type in (ElectricalEpisodeType.VOLTAGE_IMBALANCE, ElectricalEpisodeType.LOW_POWER_FACTOR):
            return AnomalyCategory.VOLTAGE_PF_FREQUENCY
        elif ep_type == ElectricalEpisodeType.PQS_INCONSISTENCY:
            # STRICT REQUIREMENT: PQS inconsistency is DATA_QUALITY evidence, NOT transformer fault!
            return AnomalyCategory.DATA_QUALITY
        return AnomalyCategory.PHASE_OR_NEUTRAL

    def _get_evidence_grade(self, ep_type: ElectricalEpisodeType) -> EvidenceGrade:
        """Assign evidence classification grade."""
        if ep_type == ElectricalEpisodeType.PQS_INCONSISTENCY:
            return EvidenceGrade.GRADE_B_DATA_QUALITY
        return EvidenceGrade.GRADE_A_PHYSICAL

    def _get_primary_reason(
        self,
        ep_type: ElectricalEpisodeType,
        severity: EpisodeSeverity,
        val: float,
    ) -> str:
        """Generate deterministic human-readable reason string."""
        sev_str = severity.value
        if ep_type == ElectricalEpisodeType.PROTECTION_TRIP:
            return f"{sev_str}: Direct hardware protection relay trip contact operated."
        elif ep_type == ElectricalEpisodeType.CURRENT_IMBALANCE:
            return f"{sev_str}: Three-phase current magnitude unbalance reached {val:.1f}% (NEMA limit exceeded)."
        elif ep_type == ElectricalEpisodeType.VOLTAGE_IMBALANCE:
            return f"{sev_str}: Three-phase voltage magnitude unbalance reached {val:.2f}%."
        elif ep_type == ElectricalEpisodeType.NEUTRAL_CURRENT_RATIO:
            return f"{sev_str}: Neutral return current ratio reached {val:.2f} relative to equivalent phase current."
        elif ep_type == ElectricalEpisodeType.LOW_POWER_FACTOR:
            return f"{sev_str}: Operating power factor dropped to {val:.2f} under active transformer load."
        elif ep_type == ElectricalEpisodeType.PQS_INCONSISTENCY:
            return f"{sev_str}: Apparent vs active/reactive power discrepancy |S^2 - (P^2 + Q^2)| reached {val:.3f} (Measurement Consistency Check)."
        return f"{sev_str}: Electrical abnormal condition {ep_type.value}."

    def _get_hypotheses(self, ep_type: ElectricalEpisodeType) -> List[str]:
        """Generate non-assertive candidate hypotheses."""
        if ep_type == ElectricalEpisodeType.PROTECTION_TRIP:
            return ["TRIP_RELAY_CONTACT_CLOSED", "TRANSFORMER_ISOLATED", "DIRECT_PROTECTION_DISCRETE"]
        elif ep_type == ElectricalEpisodeType.CURRENT_IMBALANCE:
            return ["UNBALANCED_SINGLE_PHASE_LOADS", "LOOSE_TERMINAL_CONNECTION", "ASYMMETRIC_FEEDER_DEMAND"]
        elif ep_type == ElectricalEpisodeType.VOLTAGE_IMBALANCE:
            return ["GRID_SUPPLY_UNBALANCE", "UPSTREAM_PHASE_REGULATION_MISMATCH", "UNBALANCED_LINE_IMPEDANCE"]
        elif ep_type == ElectricalEpisodeType.NEUTRAL_CURRENT_RATIO:
            return ["HIGH_ZERO_SEQUENCE_CURRENT", "HEAVY_UNBALANCED_NEUTRAL_RETURN", "POSSIBLE_NEUTRAL_GROUNDING_STRESS"]
        elif ep_type == ElectricalEpisodeType.LOW_POWER_FACTOR:
            return ["HIGHLY_INDUCTIVE_MOTOR_LOAD", "UNCOMPENSATED_REACTIVE_DEMAND", "CAPACITOR_BANK_OFFLINE"]
        elif ep_type == ElectricalEpisodeType.PQS_INCONSISTENCY:
            # STRICT: Hypotheses must point to measurement/instrumentation mismatch, NOT transformer internal fault!
            return [
                "INSTRUMENTATION_CALIBRATION_MISMATCH",
                "CT_OR_PT_SCALING_MISCONFIGURATION",
                "METER_TRANSDUCER_CALIBRATION_DRIFT",
            ]
        return []

    def _build_evidence_item(
        self,
        ep_type: ElectricalEpisodeType,
        config: ElectricalEpisodeThresholds,
        event: CanonicalEvent,
        ev_time: datetime,
        observed_val: float,
        severity_enum: EpisodeSeverity,
    ) -> EvidenceItem:
        """Create structured typed EvidenceItem."""
        count = self.evidence_counters.get(ep_type, 0) + 1
        self.evidence_counters[ep_type] = count

        sev_score = 0.90 if severity_enum == EpisodeSeverity.CRITICAL else 0.50
        ev_id = f"ev_{self.asset_id}_{ep_type.value.lower()}_{ev_time.strftime('%Y%m%d%H%M%S')}_{count}"

        threshold_str = (
            f"T_on={config.warning_threshold}, T_crit={config.critical_threshold}, T_off={config.recovery_threshold}"
        )

        return EvidenceItem(
            evidence_id=ev_id,
            asset_id=self.asset_id,
            event_time_utc=ev_time,
            category=self._get_category(ep_type),
            detector_id=f"elec_{ep_type.value.lower()}_detector",
            observed_value=round(observed_val, 4),
            expected_value=None,
            unit="%" if "IMBALANCE" in ep_type.value else ("ratio" if "RATIO" in ep_type.value else None),
            threshold_or_band=threshold_str,
            direction="LOW" if ep_type == ElectricalEpisodeType.LOW_POWER_FACTOR else "HIGH",
            severity=sev_score,
            confidence=0.90 if ep_type != ElectricalEpisodeType.PQS_INCONSISTENCY else 0.80,
            input_lineage=[m.signal_id for m in event.measurements if m.quality.severity != QualitySeverity.BAD],
            reason_codes=[f"{ep_type.value}_{severity_enum.value}"],
            hypothesis_codes=self._get_hypotheses(ep_type),
        )

    def reset(self) -> None:
        """Reset all stateful episode accumulators to clean initial baseline."""
        self.active_episodes.clear()
        self.closed_episodes.clear()
        self.recurrence_counts.clear()
        self.persistence_timers.clear()
        self.recovery_timers.clear()
        self.evidence_counters.clear()
        self.last_event_time_utc = None

    # -----------------------------------------------------------------------
    # State Inspection & Checkpoint Synchronization
    # -----------------------------------------------------------------------

    def get_active_episodes(self) -> List[ElectricalEpisode]:
        """Return list of currently open episodes in CANDIDATE, ACTIVE, or RECOVERING status."""
        return list(self.active_episodes.values())

    def get_closed_episodes(self) -> List[ElectricalEpisode]:
        """Return list of all finalized closed episodes."""
        return list(self.closed_episodes)

    def get_state(self) -> ElectricalEpisodeState:
        """Export serialized snapshot of engine state for deterministic checkpointing."""
        return ElectricalEpisodeState(
            asset_id=self.asset_id,
            active_episodes={k.value: v for k, v in self.active_episodes.items()},
            closed_episodes=list(self.closed_episodes),
            recurrence_counts={k.value: v for k, v in self.recurrence_counts.items()},
            persistence_timers={k.value: v for k, v in self.persistence_timers.items()},
            recovery_timers={k.value: v for k, v in self.recovery_timers.items()},
            last_event_time_utc=self.last_event_time_utc,
        )

    def load_state(self, state: ElectricalEpisodeState) -> None:
        """Restore engine state from a serialized checkpoint."""
        self.asset_id = state.asset_id
        self.active_episodes = {
            ElectricalEpisodeType(k): v for k, v in state.active_episodes.items()
        }
        self.closed_episodes = list(state.closed_episodes)
        self.recurrence_counts = {
            ElectricalEpisodeType(k): v for k, v in state.recurrence_counts.items()
        }
        self.persistence_timers = {
            ElectricalEpisodeType(k): v for k, v in state.persistence_timers.items()
        }
        self.recovery_timers = {
            ElectricalEpisodeType(k): v for k, v in state.recovery_timers.items()
        }
        self.last_event_time_utc = state.last_event_time_utc
