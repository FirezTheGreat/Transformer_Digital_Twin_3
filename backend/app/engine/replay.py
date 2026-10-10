"""Deterministic Chronological Replay Engine.

Provides runtime simulation of historical canonical telemetry streams.
Emits CanonicalEvents sequentially in strict chronological order with configurable
replay speeds (1x, 5x, 10x, max), playback controls (play, pause, step, reset, seek),
historical range selection (defaulting to the held-out TEST partition), and an optional
controlled chaos/test mode for watermarking verification.
"""

from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from app.core.storage import StorageEngine
from app.models.telemetry import CanonicalEvent


class ReplayEngine:
    """Deterministic, stateful chronological replay engine for canonical telemetry."""

    def __init__(
        self,
        storage: StorageEngine | None = None,
        events: Sequence[CanonicalEvent] | None = None,
        asset_id: str = "DT-001",
        speed_multiplier: float = 0.0,  # 0.0 = maximum speed (no artificial delay)
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        chaos_mode: bool = False,
        chaos_seed: int = 42,
    ) -> None:
        """Initialize ReplayEngine.

        Args:
            storage: Optional StorageEngine instance to query canonical events from.
            events: Optional pre-loaded list of CanonicalEvents.
            asset_id: Target asset identifier.
            speed_multiplier: 0.0 for max speed, or 1.0 (1x), 5.0 (5x), 10.0 (10x) real-time scaling.
            start_time: Optional start timestamp boundary (inclusive).
            end_time: Optional end timestamp boundary (inclusive).
            chaos_mode: When True, deliberately introduces deterministic out-of-order jitter
                        for testing watermark buffering without modifying stored data.
            chaos_seed: Random seed used for deterministic chaos mode.
        """
        self.storage = storage
        self.asset_id = asset_id
        self.speed_multiplier = speed_multiplier
        self.start_time = start_time
        self.end_time = end_time
        self.chaos_mode = chaos_mode
        self.chaos_seed = chaos_seed

        self._cursor: int = 0
        self._is_running: bool = False
        self._is_paused: bool = False
        self._events: list[CanonicalEvent] = []

        if events is not None:
            self.set_events(events)
        elif self.storage is not None:
            self.load_from_storage()

    def set_events(self, events: Sequence[CanonicalEvent]) -> int:
        """Set events directly and sort them deterministically."""
        # Filter by asset_id and time bounds if specified
        filtered: list[CanonicalEvent] = []
        for ev in events:
            if ev.asset_id != self.asset_id:
                continue
            ev_time = ev.event_time_utc
            if ev_time.tzinfo is None:
                ev_time = ev_time.replace(tzinfo=timezone.utc)
            if self.start_time is not None and ev_time < self.start_time:
                continue
            if self.end_time is not None and ev_time > self.end_time:
                continue
            filtered.append(ev)

        # Strict deterministic chronological sort: event_time_utc ASC, event_id ASC
        filtered.sort(key=lambda e: (e.event_time_utc, e.event_id))

        if self.chaos_mode and len(filtered) > 1:
            filtered = self._apply_deterministic_chaos(filtered)

        self._events = filtered
        self._cursor = 0
        self._is_running = False
        self._is_paused = False
        return len(self._events)

    def load_from_storage(self) -> int:
        """Query canonical events from storage and prepare deterministic replay queue."""
        if self.storage is None:
            return 0

        raw_events = self.storage.get_canonical_events(
            asset_id=self.asset_id,
            start_time=self.start_time,
            end_time=self.end_time,
            order_asc=True,
        )
        return self.set_events(raw_events)

    def configure_tripura_test_period(
        self,
        metadata_path: Path | str | None = None,
    ) -> tuple[datetime, datetime]:
        """Configure replay range to strictly cover the Tripura holdout TEST partition.

        Default test window: 2020-02-13 16:00:00 UTC to 2020-04-14 00:30:00 UTC.
        """
        if metadata_path is None:
            # Default location
            metadata_path = Path(__file__).resolve().parents[3] / "data" / "processed" / "tripura_partitions_metadata.json"

        p = Path(metadata_path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                meta = json.load(f)
            test_info = meta.get("partitions", {}).get("test", {})
            min_str = test_info.get("min_timestamp", "2020-02-13T16:00")
            max_str = test_info.get("max_timestamp", "2020-04-14T00:30")
            self.start_time = datetime.fromisoformat(min_str).replace(tzinfo=timezone.utc)
            self.end_time = datetime.fromisoformat(max_str).replace(tzinfo=timezone.utc)
        else:
            # Fallback to frozen architecture test dates
            self.start_time = datetime(2020, 2, 13, 16, 0, tzinfo=timezone.utc)
            self.end_time = datetime(2020, 4, 14, 0, 30, tzinfo=timezone.utc)

        if self.storage is not None:
            self.load_from_storage()

        return self.start_time, self.end_time

    def step(self) -> CanonicalEvent | None:
        """Emit the next single CanonicalEvent in sequence."""
        if self._cursor >= len(self._events):
            self._is_running = False
            return None

        event = self._events[self._cursor]
        self._cursor += 1
        return event

    def stream(
        self,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> Iterator[CanonicalEvent]:
        """Generator yielding events sequentially, applying scaled delays if speed_multiplier > 0."""
        self._is_running = True
        self._is_paused = False

        prev_event_time: datetime | None = None

        while self._cursor < len(self._events):
            if self._is_paused:
                break

            current_event = self._events[self._cursor]
            self._cursor += 1

            # Compute inter-event delay if real-time simulation is requested
            if self.speed_multiplier > 0 and prev_event_time is not None and sleep_fn is not None:
                curr_time = current_event.event_time_utc
                if curr_time.tzinfo is None:
                    curr_time = curr_time.replace(tzinfo=timezone.utc)
                delta_sec = (curr_time - prev_event_time).total_seconds()
                if delta_sec > 0:
                    scaled_sleep = delta_sec / self.speed_multiplier
                    # Bound single sleep to 5 seconds to avoid hanging on long gaps
                    sleep_fn(min(scaled_sleep, 5.0))

            prev_event_time = current_event.event_time_utc
            if prev_event_time.tzinfo is None:
                prev_event_time = prev_event_time.replace(tzinfo=timezone.utc)

            yield current_event

        self._is_running = False

    def play(
        self,
        sink: Callable[[CanonicalEvent], Any] | None = None,
        max_events: int | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> int:
        """Play events sequentially and deliver them to a sink callback (e.g. WatermarkManager).

        Returns:
            int: Number of events emitted during this play execution.
        """
        count = 0
        actual_sleep = sleep_fn if sleep_fn is not None else (time.sleep if self.speed_multiplier > 0 else None)

        for event in self.stream(sleep_fn=actual_sleep):
            if sink is not None:
                sink(event)
            count += 1
            if max_events is not None and count >= max_events:
                break

        return count

    def pause(self) -> None:
        """Pause playback without resetting the cursor."""
        self._is_paused = True
        self._is_running = False

    def stop(self) -> None:
        """Stop playback without resetting cursor."""
        self._is_running = False
        self._is_paused = False

    def reset(self, clear_time_bounds: bool = False) -> None:
        """Reset replay cursor to the beginning of the selected range."""
        self._cursor = 0
        self._is_running = False
        self._is_paused = False
        if clear_time_bounds:
            self.start_time = None
            self.end_time = None

    def seek(self, index: int) -> None:
        """Seek cursor to a specific event index."""
        self._cursor = max(0, min(index, len(self._events)))

    def seek_time(self, target_time: datetime) -> int:
        """Seek cursor to the first event with event_time_utc >= target_time."""
        target_utc = target_time if target_time.tzinfo is not None else target_time.replace(tzinfo=timezone.utc)
        for idx, ev in enumerate(self._events):
            ev_time = ev.event_time_utc if ev.event_time_utc.tzinfo is not None else ev.event_time_utc.replace(tzinfo=timezone.utc)
            if ev_time >= target_utc:
                self._cursor = idx
                return self._cursor
        self._cursor = len(self._events)
        return self._cursor

    def get_progress(self) -> dict[str, Any]:
        """Get current replay progress and state."""
        current_ev = self._events[self._cursor] if self._cursor < len(self._events) else None
        return {
            "cursor": self._cursor,
            "total_events": len(self._events),
            "remaining_events": max(0, len(self._events) - self._cursor),
            "is_running": self._is_running,
            "is_paused": self._is_paused,
            "is_finished": len(self._events) > 0 and self._cursor >= len(self._events),
            "current_event_id": current_ev.event_id if current_ev else None,
            "current_event_time": current_ev.event_time_utc.isoformat() if current_ev else None,
            "speed_multiplier": self.speed_multiplier,
            "chaos_mode": self.chaos_mode,
        }

    def _apply_deterministic_chaos(self, events: list[CanonicalEvent]) -> list[CanonicalEvent]:
        """Deterministically permute a small subset of events to test out-of-order watermarking."""
        rng = random.Random(self.chaos_seed)
        shuffled = list(events)
        n = len(shuffled)

        # Swap a few pairs deterministically
        for i in range(0, n - 1, 4):
            if rng.random() < 0.6 and i + 1 < n:
                shuffled[i], shuffled[i + 1] = shuffled[i + 1], shuffled[i]

        return shuffled
