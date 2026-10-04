"""Watermarking and Late-Event Handling Service.

Maintains an event-time watermark with a configurable lateness bound (default: 10 minutes).
Provides deterministic re-ordering for in-window out-of-order events and handles late
events per Option A: Store & Flag Late without live runtime state rollback.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from app.core.storage import StorageEngine
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
)


class WatermarkManager:
    """Deterministic event-time watermark and out-of-order event reordering buffer."""

    def __init__(
        self,
        lateness_budget_seconds: float = 600.0,  # 10 minutes
        storage: StorageEngine | None = None,
    ) -> None:
        """Initialize watermark manager with lateness budget and optional storage engine."""
        self.lateness_budget = timedelta(seconds=lateness_budget_seconds)
        self.storage = storage

        self.max_event_time: datetime | None = None
        self.watermark: datetime | None = None

        self._buffer: list[CanonicalEvent] = []
        self._late_events: list[CanonicalEvent] = []
        self._notifications: list[dict[str, Any]] = []

    def is_late(self, event: CanonicalEvent) -> bool:
        """Check if an event timestamp is strictly behind the current watermark."""
        if self.watermark is None:
            return False
        ev_time = event.event_time_utc
        if ev_time.tzinfo is None:
            ev_time = ev_time.replace(tzinfo=timezone.utc)
        return ev_time < self.watermark

    def process_event(self, event: CanonicalEvent) -> list[CanonicalEvent]:
        """Process a single incoming CanonicalEvent.

        Returns:
            list[CanonicalEvent]: Ready events in deterministic order (event_time_utc ASC, event_id ASC).
            If the incoming event is late (event_time_utc < watermark), it is stored and flagged
            with OUT_OF_ORDER and LATE quality flags, but not emitted into the active stream.
        """
        return self.process_events([event])

    def process_events(self, events: Sequence[CanonicalEvent]) -> list[CanonicalEvent]:
        """Process a batch of incoming CanonicalEvents.

        Maintains watermark progression, buffers in-watermark events for deterministic
        re-ordering, and handles late events according to Option A.
        """
        ready_to_emit: list[CanonicalEvent] = []

        for event in events:
            ev_time = event.event_time_utc
            if ev_time.tzinfo is None:
                ev_time = ev_time.replace(tzinfo=timezone.utc)

            # Check if event is late (behind watermark)
            if self.is_late(event):
                late_event = self._annotate_late_event(event)
                self._late_events.append(late_event)

                # Persist to storage if storage engine is configured
                if self.storage is not None:
                    self.storage.insert_canonical_events([late_event])

                # Record audit / quality notification
                self._notifications.append({
                    "event_id": event.event_id,
                    "asset_id": event.asset_id,
                    "event_time_utc": ev_time.isoformat(),
                    "watermark": self.watermark.isoformat() if self.watermark else None,
                    "lateness_seconds": (self.watermark - ev_time).total_seconds() if self.watermark else 0.0,
                    "action": "STORED_AND_FLAGGED_LATE",
                    "reason": "Event timestamp is behind active watermark; runtime state not rewound.",
                })
                continue

            # In-watermark event: add to active reordering buffer
            self._buffer.append(event)

            # Update max observed event time and advance watermark
            if self.max_event_time is None or ev_time > self.max_event_time:
                self.max_event_time = ev_time
                self.watermark = self.max_event_time - self.lateness_budget

            # Drain events from buffer that are now <= watermark
            remaining_buffer: list[CanonicalEvent] = []
            for buffered in self._buffer:
                buf_time = buffered.event_time_utc
                if buf_time.tzinfo is None:
                    buf_time = buf_time.replace(tzinfo=timezone.utc)

                if self.watermark is not None and buf_time <= self.watermark:
                    ready_to_emit.append(buffered)
                else:
                    remaining_buffer.append(buffered)

            self._buffer = remaining_buffer

        # Sort ready events deterministically
        ready_to_emit.sort(key=lambda e: (e.event_time_utc, e.event_id))

        # Persist emitted events to storage if storage is configured
        if self.storage is not None and ready_to_emit:
            self.storage.insert_canonical_events(ready_to_emit)

        return ready_to_emit

    def flush(self) -> list[CanonicalEvent]:
        """Drain and emit all remaining buffered events in deterministic order.

        Useful at end of batch, stream termination, or test verification.
        """
        drained = sorted(self._buffer, key=lambda e: (e.event_time_utc, e.event_id))
        self._buffer = []
        if self.storage is not None and drained:
            self.storage.insert_canonical_events(drained)
        return drained

    def get_watermark(self) -> datetime | None:
        """Get current event-time watermark."""
        return self.watermark

    def get_max_event_time(self) -> datetime | None:
        """Get maximum observed event timestamp."""
        return self.max_event_time

    def get_buffer_size(self) -> int:
        """Get number of events currently held in the reordering buffer."""
        return len(self._buffer)

    def get_late_events(self) -> list[CanonicalEvent]:
        """Get all late events processed so far."""
        return list(self._late_events)

    def get_late_notifications(self) -> list[dict[str, Any]]:
        """Get audit notifications for all processed late events."""
        return list(self._notifications)

    def clear(self) -> None:
        """Reset watermark and clear all internal buffers."""
        self.max_event_time = None
        self.watermark = None
        self._buffer.clear()
        self._late_events.clear()
        self._notifications.clear()

    def _annotate_late_event(self, event: CanonicalEvent) -> CanonicalEvent:
        """Create an annotated copy of a late event with OUT_OF_ORDER and LATE flags."""
        flags = list(event.event_quality_flags)
        for flag in ["OUT_OF_ORDER", "LATE"]:
            if flag not in flags:
                flags.append(flag)

        annotated_meas: list[Measurement] = []
        for m in event.measurements:
            m_flags = list(m.quality.flags)
            for flag in ["OUT_OF_ORDER", "LATE"]:
                if flag not in m_flags:
                    m_flags.append(flag)

            new_quality = m.quality.model_copy(
                update={
                    "flags": m_flags,
                    "severity": QualitySeverity.UNCERTAIN if m.quality.severity == QualitySeverity.GOOD else m.quality.severity,
                }
            )
            annotated_meas.append(m.model_copy(update={"quality": new_quality}))

        return event.model_copy(
            update={
                "event_quality_flags": flags,
                "measurements": annotated_meas,
            }
        )
