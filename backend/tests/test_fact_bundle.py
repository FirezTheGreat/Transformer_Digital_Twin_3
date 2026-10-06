"""Unit and Conformance Tests for FactBundle Aggregator (Phase 7.1).

Tests:
1. FactBundle assembly from TwinState with full Phase 6 metadata.
2. Cross-view consistency: Dashboard, 3D, and Reports receive identical state facts.
3. Preservation of OTHI gating, evidence grades, open episodes, and recommendations.
4. Deterministic provenance hash generation across identical states.
5. JSON serialization and schema roundtrip conformance.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from app.core.checkpoint import compute_twin_state_hash
from app.engine.capability import CapabilityEvaluator
from app.engine.fact_bundle import (
    FactBundleAssembler,
    assemble_fact_bundle,
    build_default_health_bundle,
    compute_fact_bundle_hash,
)
from app.models.anomaly import AnomalyCategory, AnomalyEpisode, EpisodeState
from app.models.capability import CapabilityItem, CapabilityManifest, CapabilityTier
from app.models.fact_bundle import FactBundle
from app.models.health import (
    DomainFreshness,
    DomainHealth,
    EvidenceGrade,
    HealthStatus,
    OTHIBundle,
)
from app.models.maintenance import (
    ActionWindow,
    ActionWindowProvenanceType,
    MaintenancePriority,
    MaintenanceRecommendation,
)
from app.models.twin_state import TwinState


def sample_utc_now() -> datetime:
    """Return fixed UTC test timestamp."""
    return datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)


def create_mock_twin_state(
    asset_id: str = "DT-TRIPURA-001",
    sequence: int = 42,
    with_health: bool = True,
    with_episodes: bool = False,
    with_recommendations: bool = False,
    is_gated: bool = False,
) -> TwinState:
    """Construct deterministic TwinState for testing."""
    now = sample_utc_now()
    domains: dict[str, DomainHealth] = {
        "thermal": DomainHealth(
            domain_name="thermal",
            severity=0.50 if is_gated else 0.10,
            status=HealthStatus.WATCH if is_gated else HealthStatus.NORMAL,
            details="Thermal observation",
            freshness=DomainFreshness.CURRENT,
        ),
        "loading": DomainHealth(
            domain_name="loading",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Loading normal",
            freshness=DomainFreshness.CURRENT,
        ),
        "phase_neutral": DomainHealth(
            domain_name="phase_neutral",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Phase balance normal",
            freshness=DomainFreshness.CURRENT,
        ),
        "voltage_pf_freq": DomainHealth(
            domain_name="voltage_pf_freq",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Voltage and PF normal",
            freshness=DomainFreshness.CURRENT,
        ),
        "oil_protection": DomainHealth(
            domain_name="oil_protection",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Protection normal",
            freshness=DomainFreshness.CURRENT,
        ),
    }

    health = OTHIBundle(
        asset_id=asset_id,
        timestamp_utc=now,
        othi_score=None if is_gated else 98,
        raw_othi=50 if is_gated else 98,
        status=None if is_gated else HealthStatus.NORMAL,
        raw_status=HealthStatus.WATCH if is_gated else HealthStatus.NORMAL,
        operational_status=HealthStatus.WATCH if is_gated else HealthStatus.NORMAL,
        evidence_grade=EvidenceGrade.B,
        driving_domain="thermal" if is_gated else None,
        driving_condition_family="THERMAL_OVERHEAT" if is_gated else None,
        base_penalty=0.50 if is_gated else 0.10,
        secondary_penalty=0.0,
        total_penalty=0.50 if is_gated else 0.10,
        is_gated=is_gated,
        gate_reason="Insufficient independent domain corroboration" if is_gated else None,
        available_domains=["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"],
        current_domains=["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"],
        stale_domains=[],
        domains=domains,
    )

    open_episodes = []
    if with_episodes:
        open_episodes.append(
            AnomalyEpisode(
                episode_id="ep-phase-imbalance-001",
                asset_id=asset_id,
                category=AnomalyCategory.PHASE_OR_NEUTRAL,
                state=EpisodeState.WARNING,
                severity_score=0.65,
                start_time_utc=now,
                last_seen_time_utc=now,
                primary_reason="Persistent phase current imbalance observed",
                evidence_ids=["ev-phase-001"],
            )
        )

    recommendations = []
    if with_recommendations:
        recommendations.append(
            MaintenanceRecommendation(
                recommendation_id="rec-phase-001",
                rule_id="MNT-PHASE-004",
                title="Phase Imbalance Load Balancing Review",
                priority=MaintenancePriority.P2_PLANNED_ACTION,
                priority_label="P2 PLANNED ACTION",
                action_window=ActionWindow.NEXT_AUTHORIZED_MAINTENANCE_WINDOW,
                window_provenance_type=ActionWindowProvenanceType.ENGINEERING_POLICY,
                window_source_reference="DISTRIBUTION_OPERATING_MANUAL_SEC_4",
                advisory_wording="Plan phase rebalancing during next scheduled outage.",
                rationale="Persistent current imbalance observed between phases.",
                source_reference="IS 2026 / IEC 60076",
                merge_key="MNT-PHASE-004",
                binding_vs_advisory="ADVISORY",
                created_at_utc=now,
            )
        )

    base_state = TwinState(
        asset_id=asset_id,
        state_time_utc=now,
        last_processed_event_id=f"evt-{sequence:04d}",
        event_time_watermark_utc=now,
        state_sequence=sequence,
        health_bundle=health if with_health else None,
        open_episodes=open_episodes,
        active_recommendations=recommendations,
        state_hash="",
    )
    computed_hash = compute_twin_state_hash(base_state.model_dump())
    return base_state.model_copy(update={"state_hash": computed_hash})


def test_fact_bundle_assembly_healthy():
    """Verify FactBundle properly aggregates healthy TwinState and Phase 6 data."""
    state = create_mock_twin_state(sequence=10, with_health=True, is_gated=False)
    bundle = assemble_fact_bundle(state)

    assert isinstance(bundle, FactBundle)
    assert bundle.asset_id == "DT-TRIPURA-001"
    assert bundle.fact_bundle_id == "fb-DT-TRIPURA-001-000010"
    assert bundle.timestamp_utc == state.state_time_utc
    assert bundle.twin_state == state
    assert bundle.health.othi_score == 98
    assert bundle.health.is_gated is False
    assert bundle.health.evidence_grade == EvidenceGrade.B
    assert len(bundle.provenance_hash) == 64


def test_fact_bundle_preserves_gating():
    """Verify FactBundle preserves OTHI gating, reason, and evidence quality."""
    state = create_mock_twin_state(sequence=15, is_gated=True)
    bundle = assemble_fact_bundle(state)

    assert bundle.health.is_gated is True
    assert bundle.health.othi_score is None
    assert bundle.health.raw_othi == 50
    assert bundle.health.gate_reason == "Insufficient independent domain corroboration"


def test_fact_bundle_with_episodes_and_recommendations():
    """Verify FactBundle captures active episodes and maintenance recommendations."""
    state = create_mock_twin_state(
        sequence=20,
        with_episodes=True,
        with_recommendations=True,
    )
    bundle = assemble_fact_bundle(state)

    assert len(bundle.open_episodes) == 1
    assert bundle.open_episodes[0].episode_id == "ep-phase-imbalance-001"
    assert len(bundle.active_recommendations) == 1
    assert bundle.active_recommendations[0].rule_id == "MNT-PHASE-004"
    assert bundle.active_recommendations[0].priority == MaintenancePriority.P2_PLANNED_ACTION


def test_fact_bundle_fallback_when_health_none():
    """Verify FactBundle builds baseline default health bundle if state has none."""
    state = create_mock_twin_state(sequence=1, with_health=False)
    assert state.health_bundle is None

    bundle = assemble_fact_bundle(state)
    assert bundle.health is not None
    assert bundle.health.othi_score == 100
    assert bundle.health.evidence_grade == EvidenceGrade.U
    assert len(bundle.health.domains) == 5


def test_fact_bundle_deterministic_hash():
    """Verify provenance hash is identical for identical states and differs on changes."""
    state1 = create_mock_twin_state(sequence=5)
    state2 = create_mock_twin_state(sequence=5)
    state3 = create_mock_twin_state(sequence=6)

    bundle1 = assemble_fact_bundle(state1)
    bundle2 = assemble_fact_bundle(state2)
    bundle3 = assemble_fact_bundle(state3)

    assert bundle1.provenance_hash == bundle2.provenance_hash
    assert bundle1.provenance_hash != bundle3.provenance_hash


def test_fact_bundle_json_serialization_roundtrip():
    """Verify FactBundle serializes to valid JSON matching schema and loads back losslessly."""
    state = create_mock_twin_state(
        sequence=100,
        with_episodes=True,
        with_recommendations=True,
    )
    bundle = assemble_fact_bundle(state)

    json_str = bundle.model_dump_json()
    assert isinstance(json_str, str)

    loaded = FactBundle.model_validate_json(json_str)
    assert loaded.fact_bundle_id == bundle.fact_bundle_id
    assert loaded.asset_id == bundle.asset_id
    assert loaded.provenance_hash == bundle.provenance_hash
    assert loaded.twin_state.state_hash == bundle.twin_state.state_hash
    assert loaded.health.othi_score == bundle.health.othi_score
    assert len(loaded.open_episodes) == len(bundle.open_episodes)
    assert len(loaded.active_recommendations) == len(bundle.active_recommendations)


def test_fact_bundle_schema_conformance_with_mock_fixture():
    """Verify that fixtures/mockFactBundle.json validates cleanly against FactBundle contract."""
    fixture_path = Path(__file__).resolve().parent.parent.parent / "fixtures" / "mockFactBundle.json"
    assert fixture_path.exists(), f"Fixture file not found: {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    bundle = FactBundle.model_validate(data)
    assert bundle.asset_id == "DT-001"
    assert bundle.capabilities.highest_tier == CapabilityTier.C3_THERMAL_PREDICTIVE
