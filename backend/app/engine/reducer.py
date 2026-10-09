"""Stateful Digital Twin Reducer and State Transition Engine.

Implements the deterministic state transition function:
F(TwinState_{t-1}, CanonicalEvent_t) -> TwinState_t

Maintains synchronized asset identity, latest valid observations, derived electrical features,
and periodic deterministic checkpointing per Phase 3.2 requirements.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from app.core.checkpoint import CheckpointStore, compute_twin_state_hash
from app.engine.physics import extract_electrical_features
from app.models.anomaly import AnomalyEpisode, EvidenceItem
from app.models.features import DerivedFeatures
from app.models.maintenance import MaintenanceRecommendation, OperatorFeedbackEvent
from app.models.profile import AssetProfile
from app.models.telemetry import CanonicalEvent, Measurement, QualitySeverity
from app.models.twin_state import (
    DetectorState,
    ExposureState,
    ThermalLatentState,
    TwinState,
)


def thermal_load_driver_value(
    event: CanonicalEvent,
    derived: DerivedFeatures | None,
    driver_type: str,
) -> float | None:
    """Load value in the units of the driver the thermal artifact was fitted on.

    Mirrors calibration.extract_load_driver: 'apparent_power_kva' uses measured apparent power
    (else sqrt(P^2 + Q^2)); 'rms_current_a' uses the quadratic mean of the three phase currents.
    Only the current event is used, so a stale carried-forward reading never drives the model.
    """
    vals = {
        m.signal_id: float(m.value)
        for m in event.measurements
        if isinstance(m.value, (int, float)) and not isinstance(m.value, bool)
    }
    if driver_type == "apparent_power_kva":
        s_kva = vals.get("apparent_power_total", vals.get("apparent_power"))
        if s_kva is None and derived is not None:
            s_kva = derived.apparent_power_derived_kva
        return s_kva
    phases = [vals.get(k) for k in ("current_i1", "current_i2", "current_i3")]
    if all(v is not None for v in phases):
        return math.sqrt(sum(v * v for v in phases) / 3.0)
    if derived is not None and derived.current_mean_a is not None:
        return derived.current_mean_a
    return vals.get("current_mean")


class TwinReducer:
    """Deterministic state transition reducer for the Transformer Digital Twin."""

    def __init__(
        self,
        profile: AssetProfile | None = None,
        load_reference_kva: float = 142.898,
        checkpoint_cadence_events: int = 100,
        checkpoint_store: CheckpointStore | None = None,
        episode_engine: Any | None = None,
        anomaly_engine: Any | None = None,
        othi_engine: Any | None = None,
        exposure_engine: Any | None = None,
        maintenance_engine: Any | None = None,
        thermal_gate: Any | None = None,
        review_engine: Any | None = None,
    ) -> None:
        """Initialize TwinReducer.

        Args:
            profile: Optional verified or declared AssetProfile.
            load_reference_kva: Reference apparent power in kVA for unverified relative load index.
            checkpoint_cadence_events: Number of processed events between automatic checkpoints (0 to disable).
            checkpoint_store: Optional CheckpointStore instance to persist periodic checkpoints.
            episode_engine: Optional ElectricalEpisodeEngine instance to process stateful electrical episodes.
            anomaly_engine: Optional MultiDomainAnomalyEngine instance to evaluate multi-domain anomaly evidence.
            othi_engine: Optional OTHIEngine instance to evaluate multi-domain health and gated OTHI.
            exposure_engine: Optional ThermalExposureEngine instance to evaluate thermal exposure and ageing.
            maintenance_engine: Optional MaintenanceEngine instance to evaluate advisory maintenance policies.
            thermal_gate: Optional ThermalFallbackGate instance to step physical thermal ODE.
            review_engine: Optional ReviewFlagEngine instance to evaluate deterministic review flags.
        """
        self.profile = profile
        self.load_reference_kva = load_reference_kva
        self.checkpoint_cadence_events = checkpoint_cadence_events
        self.checkpoint_store = checkpoint_store
        self.episode_engine = episode_engine
        self.anomaly_engine = anomaly_engine
        self.othi_engine = othi_engine
        self.exposure_engine = exposure_engine
        self.maintenance_engine = maintenance_engine
        self.thermal_gate = thermal_gate
        self.review_engine = review_engine
        self.latest_emitted_evidence: list[EvidenceItem] = []

    def reduce(
        self,
        current_state: TwinState | None,
        event: CanonicalEvent,
        watermark: datetime | None = None,
    ) -> TwinState:
        """Execute single deterministic state transition F(TwinState_{t-1}, CanonicalEvent_t).

        Returns:
            TwinState: New immutable successor state vector.
        """
        # Ensure event timestamp is timezone-aware UTC
        ev_time = event.event_time_utc
        if ev_time.tzinfo is None:
            ev_time = ev_time.replace(tzinfo=timezone.utc)

        # Respect Phase 2.3 decision: late events (behind watermark) do NOT rewind active TwinState
        if current_state is not None:
            if "LATE" in event.event_quality_flags or ev_time < current_state.event_time_watermark_utc:
                return current_state

            if event.asset_id != current_state.asset_id:
                raise ValueError(
                    f"Asset mismatch in TwinReducer: incoming event has asset_id '{event.asset_id}', "
                    f"but active twin state is for asset_id '{current_state.asset_id}'"
                )

        # 1. Monotonically increasing sequence number
        seq = 1 if current_state is None else current_state.state_sequence + 1

        # 2. Watermark calculation
        default_wm = ev_time - timedelta(minutes=10)
        target_wm = watermark if watermark is not None else default_wm
        if target_wm.tzinfo is None:
            target_wm = target_wm.replace(tzinfo=timezone.utc)

        if current_state is not None:
            state_wm = max(current_state.event_time_watermark_utc, target_wm)
        else:
            state_wm = target_wm

        # 3. Update current observations by signal key
        observations: dict[str, Measurement] = (
            dict(current_state.current_observations) if current_state is not None else {}
        )
        for m in event.measurements:
            observations[m.signal_id] = m
            if m.phase is not None:
                observations[f"{m.signal_id}_{m.phase}"] = m

        # 4. Derive pure electrical features from current event
        derived_electrical: DerivedFeatures = extract_electrical_features(
            event=event,
            profile=self.profile,
            load_reference_kva=self.load_reference_kva,
        )

        # 5. Version metadata
        profile_ver = self.profile.profile_version if self.profile else "1.0.0"
        versions = {
            "schema": "1.0.0",
            "profile": profile_ver,
            "transform": derived_electrical.transform_version,
            "code": "0.1.0",
        }

        # 6. Preserve or initialize downstream sub-states
        if self.thermal_gate is not None:
            t_oil_m = observations.get("top_oil_temperature")
            t_amb_m = observations.get("ambient_temperature")
            load_val = thermal_load_driver_value(
                event, derived_electrical, self.thermal_gate.load_driver_type
            )
            thermal_output = self.thermal_gate.evaluate_step(
                event_time_utc=ev_time,
                top_oil_obs=t_oil_m.value if t_oil_m else None,
                ambient_obs=t_amb_m.value if t_amb_m else None,
                load_obs=load_val,
            )
            thermal_latent = ThermalLatentState(
                top_oil_expected_degc=thermal_output.expected_top_oil_degc,
                last_free_running_top_oil_degc=thermal_output.free_running_top_oil_degc,
                time_constant_tau_hours=self.thermal_gate.params.tau_hours,
                warmup_samples_remaining=thermal_output.warmup_samples_remaining,
                model_status="SHADOW_DESCRIPTIVE" if not self.thermal_gate.is_model_promoted else "PROMOTED",
                conformal_interval_lower_degc=thermal_output.conformal_interval_lower_degc,
                conformal_interval_upper_degc=thermal_output.conformal_interval_upper_degc,
            )
            if derived_electrical is not None and thermal_output.thermal_residual_degc is not None:
                derived_electrical = derived_electrical.model_copy(
                    update={"thermal_residual_degc": thermal_output.thermal_residual_degc}
                )
        else:
            thermal_latent = (
                current_state.thermal_latent if current_state is not None else ThermalLatentState()
            )
        detector_state = (
            current_state.detector_state if current_state is not None else DetectorState()
        )
        if self.exposure_engine is not None:
            exp_bundle = self.exposure_engine.step(event=event)
            exposure_state = ExposureState(
                time_above_bands_s={
                    k: v.duration_seconds for k, v in exp_bundle.observed_exposure.bands.items()
                },
                equivalent_ageing_hours=exp_bundle.standards_ageing.equivalent_ageing_hours,
                is_ageing_enabled=exp_bundle.standards_ageing.is_enabled,
            )
        else:
            exposure_state = (
                current_state.exposure_state if current_state is not None else ExposureState()
            )

        if self.episode_engine is not None:
            elec_episodes = self.episode_engine.evaluate_step(event=event, derived=derived_electrical)
            open_episodes = [ep.to_anomaly_episode() for ep in elec_episodes]
            det_timers = {k.value: v for k, v in self.episode_engine.persistence_timers.items()}
            rec_timers = {k.value: v for k, v in self.episode_engine.recovery_timers.items()}
            detector_state = detector_state.model_copy(
                update={"persistence_timers": det_timers, "cooldown_timers": rec_timers}
            )
        else:
            open_episodes = list(current_state.open_episodes) if current_state is not None else []

        if self.anomaly_engine is not None:
            self.latest_emitted_evidence = self.anomaly_engine.evaluate_event(
                event=event, derived=derived_electrical
            )
        else:
            self.latest_emitted_evidence = []

        if self.othi_engine is not None:
            health_bundle = self.othi_engine.evaluate(
                event=event,
                derived=derived_electrical,
                evidence_items=self.latest_emitted_evidence,
                open_episodes=open_episodes,
                previous_bundle=current_state.health_bundle if current_state is not None else None,
            )
        else:
            health_bundle = current_state.health_bundle if current_state is not None else None

        if self.maintenance_engine is not None:
            active_recommendations = self.maintenance_engine.evaluate(
                event=event,
                evidence_items=self.latest_emitted_evidence,
                health_bundle=health_bundle,
            )
        else:
            active_recommendations = (
                list(current_state.active_recommendations) if current_state is not None else []
            )

        if self.review_engine is not None:
            active_reviews = self.review_engine.evaluate_step(
                event_time_utc=ev_time,
                stream_position=seq,
                evidence_items=self.latest_emitted_evidence,
                open_episodes=open_episodes,
                previous_reviews=current_state.active_reviews if current_state is not None else [],
            )
        else:
            active_reviews = (
                list(current_state.active_reviews) if current_state is not None else []
            )

        # 7. Construct TwinState
        temp_state = TwinState(
            asset_id=event.asset_id,
            state_time_utc=ev_time,
            last_processed_event_id=event.event_id,
            event_time_watermark_utc=state_wm,
            state_sequence=seq,
            current_observations=observations,
            derived_electrical=derived_electrical,
            thermal_latent=thermal_latent,
            detector_state=detector_state,
            open_episodes=open_episodes,
            health_bundle=health_bundle,
            exposure_state=exposure_state,
            active_recommendations=active_recommendations,
            active_reviews=active_reviews,
            versions=versions,
            state_hash="",
        )

        # 8. Compute deterministic SHA-256 state hash over canonical JSON dump
        state_hash = compute_twin_state_hash(temp_state.model_dump(mode="json"))
        new_state = temp_state.model_copy(update={"state_hash": state_hash})

        # 9. Periodic Checkpoint Policy
        if (
            self.checkpoint_store is not None
            and self.checkpoint_cadence_events > 0
            and seq % self.checkpoint_cadence_events == 0
        ):
            self.checkpoint_store.save_checkpoint(new_state)

        return new_state

    def reduce_stream(
        self,
        events: Sequence[CanonicalEvent],
        initial_state: TwinState | None = None,
    ) -> TwinState | None:
        """Process a sequence of CanonicalEvents in deterministic order."""
        state = initial_state
        for event in events:
            state = self.reduce(state, event)
        return state

    def apply_feedback(
        self,
        current_state: TwinState,
        feedback: OperatorFeedbackEvent,
    ) -> TwinState:
        """Apply a recorded human feedback event to current TwinState deterministically.

        Guarantees zero wall-clock dependency: uses recorded feedback timestamp and stream position.
        """
        ts = feedback.timestamp_utc
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        updated_reviews = list(current_state.active_reviews)
        if feedback.review_id and self.review_engine is not None:
            updated_reviews = self.review_engine.apply_feedback_mutation(
                reviews=current_state.active_reviews,
                review_id=feedback.review_id,
                action=feedback.action.value if hasattr(feedback.action, "value") else str(feedback.action),
                actor_id=feedback.actor_id or feedback.operator_id,
                rationale=feedback.rationale or feedback.notes,
                expected_revision=feedback.expected_revision,
                idempotency_key=feedback.idempotency_key,
                event_time_utc=ts,
                stream_position=current_state.state_sequence,
            )

        updated_recs = list(current_state.active_recommendations)
        action_val = feedback.action.value if hasattr(feedback.action, "value") else str(feedback.action)
        if action_val == "ACKNOWLEDGE":
            new_recs = []
            for r in updated_recs:
                match = (feedback.recommendation_id and r.recommendation_id == feedback.recommendation_id) or (
                    feedback.merge_key and r.merge_key == feedback.merge_key
                )
                if match:
                    r_dict = r.model_dump()
                    r_dict["acknowledged"] = True
                    r_dict["acknowledged_at_utc"] = ts
                    r_dict["acknowledged_by"] = feedback.operator_id
                    new_recs.append(MaintenanceRecommendation.model_validate(r_dict))
                else:
                    new_recs.append(r)
            updated_recs = new_recs
        elif action_val == "DISMISS":
            updated_recs = [
                r for r in updated_recs
                if not (
                    (feedback.recommendation_id and r.recommendation_id == feedback.recommendation_id)
                    or (feedback.merge_key and r.merge_key == feedback.merge_key)
                )
            ]

        # Construct new immutable state and recompute deterministic hash
        temp_state = current_state.model_copy(
            update={
                "active_reviews": updated_reviews,
                "active_recommendations": updated_recs,
            }
        )
        state_hash = compute_twin_state_hash(temp_state.model_dump(mode="json"))
        return temp_state.model_copy(update={"state_hash": state_hash})

    def reduce_stream_with_feedback(
        self,
        events: Sequence[CanonicalEvent],
        feedback_events: Sequence[OperatorFeedbackEvent],
        initial_state: TwinState | None = None,
    ) -> TwinState | None:
        """Process an interleaved stream of canonical events and recorded feedback deterministically."""
        items: list[tuple[datetime, int, Any]] = []
        for ev in events:
            t = ev.event_time_utc if ev.event_time_utc.tzinfo else ev.event_time_utc.replace(tzinfo=timezone.utc)
            items.append((t, 0, ev))
        for fb in feedback_events:
            t = fb.timestamp_utc if fb.timestamp_utc.tzinfo else fb.timestamp_utc.replace(tzinfo=timezone.utc)
            items.append((t, 1, fb))

        # Stable chronological sort: at same timestamp, process telemetry (0) before feedback (1)
        items.sort(key=lambda x: (x[0], x[1]))

        state = initial_state
        for _, item_type, payload in items:
            if item_type == 0:
                state = self.reduce(state, payload)
            elif item_type == 1 and state is not None:
                state = self.apply_feedback(state, payload)
        return state
