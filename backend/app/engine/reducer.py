"""Stateful Digital Twin Reducer and State Transition Engine.

Implements the deterministic state transition function:
F(TwinState_{t-1}, CanonicalEvent_t) -> TwinState_t

Maintains synchronized asset identity, latest valid observations, derived electrical features,
and periodic deterministic checkpointing per Phase 3.2 requirements.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

from app.core.checkpoint import CheckpointStore, compute_twin_state_hash
from app.engine.physics import extract_electrical_features
from app.models.features import DerivedFeatures
from app.models.profile import AssetProfile
from app.models.telemetry import CanonicalEvent, Measurement, QualitySeverity
from app.models.twin_state import (
    DetectorState,
    ExposureState,
    ThermalLatentState,
    TwinState,
)


class TwinReducer:
    """Deterministic state transition reducer for the Transformer Digital Twin."""

    def __init__(
        self,
        profile: AssetProfile | None = None,
        load_reference_kva: float = 142.898,
        checkpoint_cadence_events: int = 100,
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        """Initialize TwinReducer.

        Args:
            profile: Optional verified or declared AssetProfile.
            load_reference_kva: Reference apparent power in kVA for unverified relative load index.
            checkpoint_cadence_events: Number of processed events between automatic checkpoints (0 to disable).
            checkpoint_store: Optional CheckpointStore instance to persist periodic checkpoints.
        """
        self.profile = profile
        self.load_reference_kva = load_reference_kva
        self.checkpoint_cadence_events = checkpoint_cadence_events
        self.checkpoint_store = checkpoint_store

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
            obs_key = m.signal_id if m.phase is None else f"{m.signal_id}_{m.phase}"
            observations[obs_key] = m

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
        thermal_latent = (
            current_state.thermal_latent if current_state is not None else ThermalLatentState()
        )
        detector_state = (
            current_state.detector_state if current_state is not None else DetectorState()
        )
        exposure_state = (
            current_state.exposure_state if current_state is not None else ExposureState()
        )
        open_episodes = list(current_state.open_episodes) if current_state is not None else []
        health_bundle = current_state.health_bundle if current_state is not None else None
        active_recommendations = (
            list(current_state.active_recommendations) if current_state is not None else []
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
