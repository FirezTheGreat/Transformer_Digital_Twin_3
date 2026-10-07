"""Comprehensive API Tests for Analytics, Scenarios & Operator Feedback Endpoints (Phase 7.3).

Tests:
- GET /v1/assets/{asset_id}/health (domain health breakdown, evidence grades, gated OTHI)
- GET /v1/assets/{asset_id}/episodes (open/resolved episode filtering)
- GET /v1/assets/{asset_id}/recommendations (priority, rule_id, action windows, provenance)
- GET /v1/assets/{asset_id}/model-card (physical parameters, calibration metrics, bounds)
- POST /v1/assets/{asset_id}/scenario (2-hour what-if projection, conformal bounds, fallback trust states)
- POST /v1/feedback (operator acknowledge, dismissal safety invariants, inspection outcome, overrides)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from app.api.deps import AppState, build_default_model_artifact
from app.core.config import Settings
from app.core.storage import StorageEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.fact_bundle import assemble_fact_bundle, build_default_health_bundle
from app.engine.feedback import OperatorFeedbackLedger
from app.engine.reducer import TwinReducer
from app.engine.replay import ReplayEngine
from app.engine.scenario_simulator import ScenarioSimulator
from app.main import create_app
from app.models.anomaly import (
    AnomalyCategory,
    AnomalyEpisode,
    EpisodeState,
    EvidenceItem,
)
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
    FeedbackAction,
    MaintenancePriority,
    MaintenanceRecommendation,
)
from app.models.scenario import ScenarioRequest
from app.models.telemetry import CanonicalEvent, Measurement, QualitySeverity
from app.models.thermal_artifact import CalibratedThermalModelArtifact, QualificationStatus, ThermalModelQualification
from app.models.twin_state import ThermalLatentState, TwinState


@pytest.fixture
def mock_storage(tmp_path) -> StorageEngine:
    db_file = tmp_path / "test_api_analytics.db"
    storage = StorageEngine(db_path=str(db_file))
    yield storage
    storage.close()


@pytest.fixture
def test_app_state(mock_storage: StorageEngine) -> AppState:
    settings = Settings(
        app_name="Test Digital Twin",
        db_path=":memory:",
        default_asset_id="DT-TRIPURA-001",
    )
    reducer = TwinReducer(load_reference_kva=100.0)
    evaluator = CapabilityEvaluator()
    ledger = OperatorFeedbackLedger()
    replay = ReplayEngine(storage=mock_storage, asset_id="DT-TRIPURA-001")
    artifact = build_default_model_artifact("DT-TRIPURA-001")
    simulator = ScenarioSimulator.from_artifact(artifact)

    return AppState(
        settings=settings,
        storage=mock_storage,
        reducer=reducer,
        capability_evaluator=evaluator,
        feedback_ledger=ledger,
        replay_engine=replay,
        model_artifact=artifact,
        scenario_simulator=simulator,
    )


@pytest.fixture
def client(test_app_state: AppState) -> Generator[TestClient, None, None]:
    app = create_app(settings=test_app_state.settings, app_state=test_app_state)
    with TestClient(app) as test_client:
        yield test_client


def _make_sample_state(
    asset_id: str = "DT-TRIPURA-001",
    top_oil: float = 72.5,
    ambient: float = 31.0,
    current_a: float = 120.0,
    with_episodes: bool = True,
    with_recommendations: bool = True,
    with_health: bool = True,
) -> TwinState:
    now = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
    obs = {
        "top_oil_temperature_c": Measurement(
            signal_id="top_oil_temperature_c",
            value=top_oil,
            value_type="float",
            unit_ucum="Cel",
            original_name="OTI",
            original_value=str(top_oil),
            original_unit="degC",
        ),
        "ambient_temperature_c": Measurement(
            signal_id="ambient_temperature_c",
            value=ambient,
            value_type="float",
            unit_ucum="Cel",
            original_name="ATI",
            original_value=str(ambient),
            original_unit="degC",
        ),
        "current_r_a": Measurement(
            signal_id="current_r_a",
            value=current_a,
            value_type="float",
            unit_ucum="A",
            original_name="Current_R",
            original_value=str(current_a),
            original_unit="A",
        ),
    }


    episodes = []
    if with_episodes:
        episodes.append(
            AnomalyEpisode(
                episode_id="EP-THERM-001",
                asset_id=asset_id,
                category=AnomalyCategory.THERMAL_DEVIATION,
                state=EpisodeState.WARNING,
                severity_score=0.65,
                start_time_utc=now - timedelta(minutes=45),
                last_seen_time_utc=now,
                evidence_ids=["EV-001"],
                primary_reason="Top-oil temperature higher than expected given ambient and load context",
            )
        )
        episodes.append(
            AnomalyEpisode(
                episode_id="EP-VOLT-002",
                asset_id=asset_id,
                category=AnomalyCategory.VOLTAGE_PF_FREQUENCY,
                state=EpisodeState.CRITICAL,
                severity_score=0.85,
                start_time_utc=now - timedelta(minutes=15),
                last_seen_time_utc=now,
                evidence_ids=["EV-002"],
                primary_reason="Severe voltage unbalance and phase asymmetry",
            )
        )



    recommendations = []
    if with_recommendations:
        recommendations.append(
            MaintenanceRecommendation(
                recommendation_id="REC-001-P0",
                rule_id="MNT-PROT-001",
                rule_version="1.0.0",
                title="Immediate Protection Trip Followup",
                priority=MaintenancePriority.P0_SAFETY,
                priority_label="P0 SAFETY",
                action_window=ActionWindow.IMMEDIATE,
                window_provenance_type=ActionWindowProvenanceType.PROTECTION_OR_SITE_PROCEDURE,
                window_source_reference="Substation Safety Operating Procedure SOP-502",
                advisory_wording="Follow substation protection trip procedure. Verify physical clearance before re-energization.",
                rationale="Direct protection trip contact detected.",
                evidence_ids=["EV-PROT-001"],
                source_reference="IEEE Std C57.91-2011",
                merge_key="PROTECTION_TRIP_FOLLOWUP",
                created_at_utc=now,
            )
        )
        recommendations.append(
            MaintenanceRecommendation(
                recommendation_id="REC-002-P2",
                rule_id="MNT-PHASE-004",
                rule_version="1.0.0",
                title="Phase Imbalance Inspection",
                priority=MaintenancePriority.P2_PLANNED_ACTION,
                priority_label="P2 PLANNED ACTION",
                action_window=ActionWindow.NEXT_AUTHORIZED_MAINTENANCE_WINDOW,
                window_provenance_type=ActionWindowProvenanceType.ENGINEERING_POLICY,
                window_source_reference="Distribution transformer maintenance policy standard",
                advisory_wording="Schedule phase balance inspection at next planned maintenance window.",
                rationale="Persistent neutral current and phase imbalance detected.",
                evidence_ids=["EV-PHASE-001"],
                source_reference="CIGRE TB 738",
                merge_key="PHASE_IMBALANCE",
                created_at_utc=now,
            )
        )

    health_bundle = None
    if with_health:
        health_bundle = OTHIBundle(
            asset_id=asset_id,
            timestamp_utc=now,
            othi_score=78,
            raw_othi=78,
            status=HealthStatus.WATCH,
            raw_status=HealthStatus.WATCH,
            operational_status=HealthStatus.WATCH,
            evidence_grade=EvidenceGrade.A,
            driving_domain="thermal",
            driving_condition_family="THERMAL_RESIDUAL",
            base_penalty=0.20,
            secondary_penalty=0.02,
            total_penalty=0.22,
            is_gated=False,
            gate_reason=None,
            available_domains=["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"],
            current_domains=["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"],
            stale_domains=[],
            domains={
                "thermal": DomainHealth(
                    domain_name="thermal",
                    severity=0.20,
                    status=HealthStatus.WATCH,
                    details="Mild top-oil elevation",
                    freshness=DomainFreshness.CURRENT,
                ),
                "loading": DomainHealth(
                    domain_name="loading",
                    severity=0.10,
                    status=HealthStatus.NORMAL,
                    details="Normal loading",
                    freshness=DomainFreshness.CURRENT,
                ),
                "phase_neutral": DomainHealth(
                    domain_name="phase_neutral",
                    severity=0.0,
                    status=HealthStatus.NORMAL,
                    details="Balanced",
                    freshness=DomainFreshness.CURRENT,
                ),
                "voltage_pf_freq": DomainHealth(
                    domain_name="voltage_pf_freq",
                    severity=0.0,
                    status=HealthStatus.NORMAL,
                    details="Normal voltage/frequency",
                    freshness=DomainFreshness.CURRENT,
                ),
                "oil_protection": DomainHealth(
                    domain_name="oil_protection",
                    severity=0.0,
                    status=HealthStatus.NORMAL,
                    details="Normal oil & protection",
                    freshness=DomainFreshness.CURRENT,
                ),
            },
        )

    return TwinState(
        asset_id=asset_id,
        state_time_utc=now,
        last_processed_event_id="EVT-001",
        event_time_watermark_utc=now,
        state_sequence=1,
        current_observations=obs,
        thermal_latent=ThermalLatentState(
            top_oil_expected_degc=71.2,
            last_free_running_top_oil_degc=71.0,
            time_constant_tau_hours=3.0,
            warmup_samples_remaining=0,
            model_status="PROMOTED",
        ),
        open_episodes=episodes,
        health_bundle=health_bundle,
        active_recommendations=recommendations,
        state_hash="mock_state_hash_12345",
    )


# ==============================================================================
# Health Endpoint Tests
# ==============================================================================

def test_get_health_uninitialized(client: TestClient) -> None:
    """Uninitialized state returns valid default health bundle with OTHI=100 and EvidenceGrade.U."""
    resp = client.get("/v1/assets/DT-TRIPURA-001/health")
    assert resp.status_code == 200
    data = resp.json()

    assert data["asset_id"] == "DT-TRIPURA-001"
    assert data["othi_score"] == 100
    assert data["evidence_grade"] == "U"
    assert data["is_gated"] is False
    assert len(data["domains"]) == 5
    assert "thermal" in data["domains"]
    assert "loading" in data["domains"]
    assert "oil_protection" in data["domains"]


def test_get_health_active_state(client: TestClient, test_app_state: AppState) -> None:
    """Active state returns evaluated OTHIBundle with correct score, driving domain, and grade."""
    state = _make_sample_state(asset_id="DT-TRIPURA-001")
    manifest = test_app_state.capability_evaluator.evaluate(state)
    fact_bundle = assemble_fact_bundle(state=state, capabilities=manifest)
    test_app_state.update_state(state, fact_bundle)

    resp = client.get("/v1/assets/DT-TRIPURA-001/health")
    assert resp.status_code == 200
    data = resp.json()

    assert data["asset_id"] == "DT-TRIPURA-001"
    assert data["othi_score"] == 78
    assert data["driving_domain"] == "thermal"
    assert data["evidence_grade"] == "A"
    assert data["is_gated"] is False
    assert data["domains"]["thermal"]["severity"] == 0.20


# ==============================================================================
# Episodes Endpoint Tests
# ==============================================================================

def test_get_episodes_filtering(client: TestClient, test_app_state: AppState) -> None:
    """Episodes endpoint returns open episodes with category and state filters."""
    state = _make_sample_state(asset_id="DT-TRIPURA-001")
    test_app_state.update_state(state)

    # 1. Fetch all episodes
    resp = client.get("/v1/assets/DT-TRIPURA-001/episodes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert {ep["episode_id"] for ep in data} == {"EP-THERM-001", "EP-VOLT-002"}

    # 2. Filter by category
    resp_cat = client.get("/v1/assets/DT-TRIPURA-001/episodes?category=THERMAL_DEVIATION")
    assert resp_cat.status_code == 200
    data_cat = resp_cat.json()
    assert len(data_cat) == 1
    assert data_cat[0]["episode_id"] == "EP-THERM-001"

    # 3. Filter by state
    resp_state = client.get("/v1/assets/DT-TRIPURA-001/episodes?state=CRITICAL")
    assert resp_state.status_code == 200
    data_state = resp_state.json()
    assert len(data_state) == 1
    assert data_state[0]["episode_id"] == "EP-VOLT-002"

    # 4. Limit parameter
    resp_lim = client.get("/v1/assets/DT-TRIPURA-001/episodes?limit=1")
    assert resp_lim.status_code == 200
    assert len(resp_lim.json()) == 1


# ==============================================================================
# Recommendations Endpoint Tests
# ==============================================================================

def test_get_recommendations_filtering(client: TestClient, test_app_state: AppState) -> None:
    """Recommendations endpoint returns deterministic recommendations with priority and rule_id filtering."""
    state = _make_sample_state(asset_id="DT-TRIPURA-001")
    test_app_state.update_state(state)

    # 1. Fetch all recommendations
    resp = client.get("/v1/assets/DT-TRIPURA-001/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    p0_rec = next(r for r in data if r["priority"] == "P0")
    assert p0_rec["rule_id"] == "MNT-PROT-001"
    assert p0_rec["action_window"] == "IMMEDIATE"
    assert p0_rec["window_provenance_type"] == "PROTECTION_OR_SITE_PROCEDURE"
    assert "SOP-502" in p0_rec["window_source_reference"]

    # 2. Filter by priority
    resp_p2 = client.get("/v1/assets/DT-TRIPURA-001/recommendations?priority=P2")
    assert resp_p2.status_code == 200
    data_p2 = resp_p2.json()
    assert len(data_p2) == 1
    assert data_p2[0]["rule_id"] == "MNT-PHASE-004"

    # 3. Filter by rule_id
    resp_rule = client.get("/v1/assets/DT-TRIPURA-001/recommendations?rule_id=MNT-PROT-001")
    assert resp_rule.status_code == 200
    data_rule = resp_rule.json()
    assert len(data_rule) == 1
    assert data_rule[0]["recommendation_id"] == "REC-001-P0"


# ==============================================================================
# Model-Card Endpoint Tests
# ==============================================================================

def test_get_model_card(client: TestClient) -> None:
    """Model card endpoint returns parameters, bounds, test metrics, and qualification matrix."""
    resp = client.get("/v1/assets/DT-TRIPURA-001/model-card")
    assert resp.status_code == 200
    data = resp.json()

    assert data["asset_id"] == "DT-TRIPURA-001"
    assert "parameters" in data
    assert data["parameters"]["beta_0"] > 0
    assert data["parameters"]["beta_1"] > 0
    assert data["parameters"]["tau_hours"] > 0

    assert "identifiability" in data
    assert isinstance(data["identifiability"]["is_identifiable"], bool)

    assert "conformal_uncertainty" in data
    assert len(data["conformal_uncertainty"]["horizon_half_widths_degc"]) == 8

    assert "promotion" in data
    assert data["promotion"]["status"] in ("PROMOTED", "NOT_PROMOTED", "REJECTED")

    assert "qualification" in data
    assert data["qualification"]["scenario_qualification"] in ("QUALIFIED", "PENDING_VALIDATION")


# ==============================================================================
# Scenario Endpoint Tests
# ==============================================================================

def test_post_scenario_successful_projection(client: TestClient, test_app_state: AppState) -> None:
    """Scenario simulation generates 8-step 2-hour projection with empirical conformal bounds."""
    state = _make_sample_state(asset_id="DT-TRIPURA-001", top_oil=65.0, ambient=30.0, current_a=120.0)
    test_app_state.update_state(state)

    payload = {
        "load_multiplier": 1.10,
        "ambient_delta_degc": 2.0,
        "warning_threshold_degc": 85.0,
        "critical_threshold_degc": 95.0,
    }

    resp = client.post("/v1/assets/DT-TRIPURA-001/scenario", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["asset_id"] == "DT-TRIPURA-001"
    assert data["is_enabled"] is True
    assert data["trust_state"] == "MODEL_HEALTHY"
    assert len(data["trajectory"]) == 8
    assert data["asymptotic_steady_state_degc"] is not None

    # Step validation
    for i, step in enumerate(data["trajectory"]):
        assert step["horizon_step"] == i + 1
        assert step["horizon_minutes"] == (i + 1) * 15
        assert step["projected_top_oil_degc"] >= 20.0
        assert step["conformal_lower_degc"] < step["projected_top_oil_degc"]
        assert step["conformal_upper_degc"] > step["projected_top_oil_degc"]


def test_post_scenario_extrapolation_warning(client: TestClient, test_app_state: AppState) -> None:
    """Extreme scenario conditions trigger extrapolation warning and wider bounds."""
    state = _make_sample_state(asset_id="DT-TRIPURA-001", top_oil=65.0, ambient=30.0)
    test_app_state.update_state(state)

    payload = {
        "target_load_u": 1.80,  # Extreme overload (>1.20)
        "ambient_delta_degc": 28.0,  # Ambient reaches 58 degC (>55 degC limit)
    }

    resp = client.post("/v1/assets/DT-TRIPURA-001/scenario", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_extrapolated"] is True
    assert data["extrapolation_warning"] is not None


def test_post_scenario_fallback_trust_state(client: TestClient, test_app_state: AppState) -> None:
    """When twin state is in FALLBACK_PERSISTENCE, scenario simulator reports fallback mode."""
    state = _make_sample_state(asset_id="DT-TRIPURA-001")
    # Mutate thermal latent state to fallback
    state = state.model_copy(
        update={
            "thermal_latent": ThermalLatentState(
                model_status="FALLBACK_PERSISTENCE",
                top_oil_expected_degc=65.0,
            )
        }
    )
    test_app_state.update_state(state)

    payload = {"load_multiplier": 1.0, "ambient_delta_degc": 0.0}
    resp = client.post("/v1/assets/DT-TRIPURA-001/scenario", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["trust_state"] == "FALLBACK_PERSISTENCE"
    assert data["is_enabled"] is False



# ==============================================================================
# Operator Feedback Endpoint Tests
# ==============================================================================

def test_post_feedback_acknowledge(client: TestClient, test_app_state: AppState) -> None:
    """Operator ACKNOWLEDGE updates recommendation workflow state and is recorded in audit ledger."""
    state = _make_sample_state(asset_id="DT-TRIPURA-001")
    manifest = test_app_state.capability_evaluator.evaluate(state)
    fact_bundle = assemble_fact_bundle(state=state, capabilities=manifest)
    test_app_state.update_state(state, fact_bundle)


    payload = {
        "asset_id": "DT-TRIPURA-001",
        "action": "ACKNOWLEDGE",
        "operator_id": "op_alice",
        "recommendation_id": "REC-002-P2",
    }

    resp = client.post("/v1/feedback", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["action"] == "ACKNOWLEDGE"
    assert data["operator_id"] == "op_alice"
    assert data["recommendation_id"] == "REC-002-P2"

    # Verify state reflects acknowledgement
    rec = next(r for r in test_app_state.current_state.active_recommendations if r.recommendation_id == "REC-002-P2")
    assert rec.acknowledged is True
    assert rec.acknowledged_by == "op_alice"
    assert rec.acknowledged_at_utc is not None

    # Verify ledger history
    history = test_app_state.feedback_ledger.get_history(asset_id="DT-TRIPURA-001")
    assert len(history) == 1
    assert history[0].action == FeedbackAction.ACKNOWLEDGE


def test_post_feedback_dismiss_p0_safety_guardrail(client: TestClient, test_app_state: AppState) -> None:
    """P0 Safety recommendation CANNOT be dismissed without authorized documented resolution reason code."""
    state = _make_sample_state(asset_id="DT-TRIPURA-001")
    test_app_state.update_state(state)

    # 1. Attempt dismissal with invalid / arbitrary reason code -> Must fail with 422
    invalid_payload = {
        "asset_id": "DT-TRIPURA-001",
        "action": "DISMISS",
        "operator_id": "op_bob",
        "recommendation_id": "REC-001-P0",
        "reason_code": "IGNORE_ALARM",
        "rationale": "Attempting to ignore protection trip without clearance.",
    }
    resp_bad = client.post("/v1/feedback", json=invalid_payload)
    assert resp_bad.status_code == 422
    err_body = resp_bad.json()
    assert "error" in err_body
    assert "cannot be dismissed without documented resolution" in err_body["error"]["message"]

    # 2. Attempt dismissal with valid resolution reason code -> Must succeed
    valid_payload = {
        "asset_id": "DT-TRIPURA-001",
        "action": "DISMISS",
        "operator_id": "op_bob",
        "recommendation_id": "REC-001-P0",
        "reason_code": "SITE_CLEARANCE_VERIFIED",
        "rationale": "Field technician inspected transformer; clearance certificate #491 filed.",
    }
    resp_good = client.post("/v1/feedback", json=valid_payload)
    assert resp_good.status_code == 200

    # Verify P0 recommendation was removed from active recommendations
    active_ids = [r.recommendation_id for r in test_app_state.current_state.active_recommendations]
    assert "REC-001-P0" not in active_ids


def test_post_feedback_inspection_outcome(client: TestClient, test_app_state: AppState) -> None:
    """Inspection findings are recorded in ledger and generate structured Grade-A inspection evidence."""
    payload = {
        "asset_id": "DT-TRIPURA-001",
        "action": "INSPECTION_OUTCOME",
        "operator_id": "tech_charlie",
        "notes": "Physical DGA oil sample collected; dielectric breakdown voltage = 62 kV.",
        "inspection_outcome": {
            "category": "PROTECTION_OR_OIL_STATUS",
            "severity": 0.05,
            "summary": "Oil dielectric strength healthy",
        },
    }

    resp = client.post("/v1/feedback", json=payload)
    assert resp.status_code == 200

    evidence = test_app_state.feedback_ledger.generate_inspection_evidence("DT-TRIPURA-001")
    assert len(evidence) == 1
    assert evidence[0].category == AnomalyCategory.PROTECTION_OR_OIL_STATUS
    assert evidence[0].detector_id == "PHYSICAL_INSPECTION:tech_charlie"
    assert "tech_charlie" in evidence[0].detector_id


def test_post_feedback_authorized_override(client: TestClient, test_app_state: AppState) -> None:
    """Authorized override requires authorized_role, rationale, and expiry timestamp."""
    future_expiry = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()

    # 1. Missing authorized_role -> 422
    resp_no_role = client.post(
        "/v1/feedback",
        json={
            "asset_id": "DT-TRIPURA-001",
            "action": "OVERRIDE",
            "operator_id": "op_dan",
            "rationale": "Temporary maintenance bypass",
            "override_expiry_utc": future_expiry,
        },
    )
    assert resp_no_role.status_code == 422

    # 2. Valid override -> 200
    resp_valid = client.post(
        "/v1/feedback",
        json={
            "asset_id": "DT-TRIPURA-001",
            "action": "OVERRIDE",
            "operator_id": "op_dan",
            "authorized_role": "SUBSTATION_SUPERVISOR",
            "rationale": "Transformer under supervised manual load transfer procedure",
            "override_expiry_utc": future_expiry,
            "merge_key": "PHASE_IMBALANCE",
        },
    )
    assert resp_valid.status_code == 200

    active_overrides = test_app_state.feedback_ledger.get_active_overrides(
        "DT-TRIPURA-001", datetime.now(timezone.utc)
    )
    assert "PHASE_IMBALANCE" in active_overrides
