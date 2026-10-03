"""Test validation of mockFactBundle fixture against canonical Pydantic contracts."""

import json
from pathlib import Path
from app.models import FactBundle, CapabilityTier, EpisodeState, MaintenancePriority


def test_mock_fact_bundle_fixture_validity() -> None:
    """Verify that fixtures/mockFactBundle.json strictly validates against FactBundle model."""
    fixture_path = Path(__file__).resolve().parent.parent.parent / "fixtures" / "mockFactBundle.json"
    assert fixture_path.exists(), f"Fixture not found at {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate against FactBundle Pydantic model
    bundle = FactBundle.model_validate(data)

    assert bundle.asset_id == "DT-001"
    assert bundle.bundle_version == "1.0.0"
    assert bundle.capabilities.highest_tier == CapabilityTier.C3_THERMAL_PREDICTIVE
    assert len(bundle.health.domains) == 5
    assert "thermal" in bundle.health.domains
    assert "loading" in bundle.health.domains
    assert "phase_neutral" in bundle.health.domains
    assert "voltage_pf_freq" in bundle.health.domains
    assert "oil_protection" in bundle.health.domains

    # Check episode consistency
    assert len(bundle.open_episodes) == 1
    assert bundle.open_episodes[0].state == EpisodeState.WARNING
    assert bundle.open_episodes[0].severity_score == 0.55

    # Check recommendation consistency
    assert len(bundle.active_recommendations) == 1
    assert bundle.active_recommendations[0].priority == MaintenancePriority.P1_URGENT_INSPECTION
    assert bundle.active_recommendations[0].rule_id == "MNT-THERM-002"

    # Verify JSON serialization parity
    serialized = bundle.model_dump_json()
    reloaded = FactBundle.model_validate_json(serialized)
    assert reloaded == bundle
