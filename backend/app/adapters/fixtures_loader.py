"""Static Error & Edge-Case Fixture Loader.

Phase 1, Substep 1.3 Implementation.
Loads, validates, and parses canonical static test fixtures for unit/scale errors,
timestamp gaps, conflicting duplicates, and direct protection trips without mixing
them into real historical dataset partitions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.telemetry import CanonicalEvent


@dataclass(frozen=True)
class ExpectedBehavior:
    detection_target: str
    expected_severity: str
    quarantine_measurement: bool
    capability_impact: str


@dataclass(frozen=True)
class StaticFixture:
    fixture_id: str
    category: str
    description: str
    is_synthetic: bool
    target_asset_id: str
    expected_behavior: ExpectedBehavior
    events: List[CanonicalEvent]
    raw_payload: Dict[str, Any]


class StaticFixtureLoader:
    """Deterministic loader and validator for static regression fixtures in fixtures/."""

    KNOWN_FIXTURES = [
        "fixture_scale_error.json",
        "fixture_timestamp_gaps.json",
        "fixture_conflicting_duplicates.json",
        "fixture_direct_protection_trip.json",
    ]

    def __init__(self, fixtures_dir: Path | str = "fixtures") -> None:
        self.fixtures_dir = Path(fixtures_dir)

    def load_fixture(self, filename_or_id: str) -> StaticFixture:
        """Loads and validates a static fixture JSON file against CanonicalEvent model."""
        fname = filename_or_id if filename_or_id.endswith(".json") else f"{filename_or_id}.json"
        fpath = self.fixtures_dir / fname

        if not fpath.exists():
            raise FileNotFoundError(f"Fixture file not found: {fpath.resolve()}")

        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        exp_data = data.get("expected_behavior", {})
        exp_behavior = ExpectedBehavior(
            detection_target=exp_data.get("detection_target", ""),
            expected_severity=exp_data.get("expected_severity", "GOOD"),
            quarantine_measurement=exp_data.get("quarantine_measurement", False),
            capability_impact=exp_data.get("capability_impact", ""),
        )

        parsed_events: List[CanonicalEvent] = []
        for raw_evt in data.get("events", []):
            event_obj = CanonicalEvent.model_validate(raw_evt)
            parsed_events.append(event_obj)

        return StaticFixture(
            fixture_id=data.get("fixture_id", fpath.stem),
            category=data.get("category", "unknown"),
            description=data.get("description", ""),
            is_synthetic=data.get("is_synthetic", True),
            target_asset_id=data.get("target_asset_id", "TX_UNKNOWN"),
            expected_behavior=exp_behavior,
            events=parsed_events,
            raw_payload=data,
        )

    def load_all_fixtures(self) -> Dict[str, StaticFixture]:
        """Loads and validates all known static regression fixtures."""
        fixtures: Dict[str, StaticFixture] = {}
        for fname in self.KNOWN_FIXTURES:
            fix = self.load_fixture(fname)
            fixtures[fix.fixture_id] = fix
        return fixtures


def load_fixture(filename_or_id: str, fixtures_dir: Path | str = "fixtures") -> StaticFixture:
    """Convenience function to load a single static fixture."""
    loader = StaticFixtureLoader(fixtures_dir=fixtures_dir)
    return loader.load_fixture(filename_or_id)
