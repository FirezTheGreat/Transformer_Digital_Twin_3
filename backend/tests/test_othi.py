"""Tests for Phase 6.1 — Multi-Domain OTHI & Domain Aggregation Engine.

Verifies:
1. MAX_PLUS_SECONDARY_V1 mathematical invariants:
   - Monotonicity
   - Permutation invariance
   - Max/Tie invariance
   - Severe vs moderate dominance
   - Duplicate-family invariance
   - Direct-protection dominance
   - Missing-domain anti-uplift
   - Saturation clamping to [0, 100]
2. Evidence-family dependency grouping and deduplication
3. Exact multi-domain evidence gating (>= 2 current domains or 1 decisive direct trip)
4. Hybrid stale-domain cadence tracking and Anti-Uplift Rule
5. Raw instantaneous score vs persisted operational health band
6. Evidence Grade (A, B, C, U) classification
7. End-to-end integration with TwinReducer
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.engine.othi import (
    CANONICAL_DOMAINS,
    OTHIEngine,
    aggregate_othi_max_plus_secondary,
    status_from_othi,
    status_from_severity,
)
from app.engine.reducer import TwinReducer
from app.models.anomaly import AnomalyCategory, AnomalyEpisode, EpisodeState, EvidenceItem
from app.models.health import DomainFreshness, EvidenceGrade, HealthStatus, OTHIBundle
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


def _make_utc(hour: int = 12, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 10, 2, hour, minute, second, tzinfo=timezone.utc)


def _make_measurement(
    signal_id: str,
    value: float | int | str | bool,
    unit: str = "1",
    phase: str | None = None,
    severity: QualitySeverity = QualitySeverity.GOOD,
) -> Measurement:
    if isinstance(value, bool):
        val_type = "bool"
    elif isinstance(value, int):
        val_type = "int"
    elif isinstance(value, float):
        val_type = "float"
    else:
        val_type = "str"

    return Measurement(
        signal_id=signal_id,
        phase=phase,  # type: ignore[arg-type]
        value=value,
        value_type=val_type,
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=severity, flags=[]),
    )


def _make_canonical_event(
    event_id: str,
    event_time: datetime,
    asset_id: str = "DT-001",
    measurements: list[Measurement] | None = None,
) -> CanonicalEvent:
    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=event_time,
        received_time_utc=None,
        source=SourceRef(
            system="test_system",
            adapter_id="test_v1",
            source_record_id=f"rec_{event_id}",
            source_uri="data/test.csv",
            raw_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        ),
        measurements=measurements or [],
        event_quality_flags=[],
        mapping_version="test-map-1.0.0",
    )


# ---------------------------------------------------------------------------
# 1. Mathematical Invariant Tests for MAX_PLUS_SECONDARY_V1
# ---------------------------------------------------------------------------


def test_max_plus_secondary_formula_exact_values() -> None:
    """Verify exact formula calculation against manual arithmetic."""
    # Case 1: Healthy asset across 5 domains
    severities = {"thermal": 0.0, "loading": 0.0, "phase_neutral": 0.0, "voltage_pf_freq": 0.0, "oil_protection": 0.0}
    score, base, sec, tot, driving = aggregate_othi_max_plus_secondary(severities, 0.20)
    assert score == 100
    assert base == 0.0
    assert sec == 0.0
    assert tot == 0.0

    # Case 2: One moderate domain (0.50) + one mild domain (0.30)
    severities = {"thermal": 0.50, "loading": 0.30}
    score, base, sec, tot, driving = aggregate_othi_max_plus_secondary(severities, 0.20)
    # base = 0.50, sec = 0.20 * 0.30 = 0.06, tot = 0.56 -> OTHI = round(100 * 0.44) = 44
    assert base == 0.50
    assert pytest.approx(sec, abs=1e-5) == 0.06
    assert pytest.approx(tot, abs=1e-5) == 0.56
    assert score == 44
    assert driving == "thermal"


def test_max_plus_secondary_monotonicity() -> None:
    """Monotonicity: worsening any domain severity s_d never improves OTHI score."""
    base_sevs = {"thermal": 0.20, "loading": 0.30, "phase_neutral": 0.10}
    initial_score, _, _, _, _ = aggregate_othi_max_plus_secondary(base_sevs, 0.20)

    for delta in [0.05, 0.10, 0.30, 0.50]:
        worsened_sevs = {"thermal": 0.20 + delta, "loading": 0.30, "phase_neutral": 0.10}
        worsened_score, _, _, _, _ = aggregate_othi_max_plus_secondary(worsened_sevs, 0.20)
        assert worsened_score <= initial_score


def test_max_plus_secondary_permutation_invariance() -> None:
    """Permutation Invariance: order of domains in dictionary does not alter score."""
    sevs_1 = {"thermal": 0.60, "loading": 0.40, "phase_neutral": 0.20, "voltage_pf_freq": 0.10}
    sevs_2 = {"voltage_pf_freq": 0.10, "loading": 0.40, "thermal": 0.60, "phase_neutral": 0.20}
    score1, base1, sec1, tot1, driv1 = aggregate_othi_max_plus_secondary(sevs_1, 0.20)
    score2, base2, sec2, tot2, driv2 = aggregate_othi_max_plus_secondary(sevs_2, 0.20)
    assert score1 == score2
    assert base1 == base2
    assert sec1 == sec2
    assert tot1 == tot2
    assert driv1 == driv2 == "thermal"


def test_max_plus_secondary_max_tie_invariance() -> None:
    """Max/Tie Invariance: ties in maximum severity are resolved symmetrically and deterministically."""
    sevs = {"thermal": 0.50, "loading": 0.50, "phase_neutral": 0.20}
    score, base, sec, tot, driving = aggregate_othi_max_plus_secondary(sevs, 0.20)
    # base = 0.50, other domains = 0.50 + 0.20 = 0.70, sec = 0.20 * 0.70 = 0.14, tot = 0.64 -> OTHI = 36
    assert base == 0.50
    assert pytest.approx(sec, abs=1e-5) == 0.14
    assert pytest.approx(tot, abs=1e-5) == 0.64
    assert score == 36
    assert driving in ("loading", "thermal")


def test_max_plus_secondary_severe_vs_moderate_dominance() -> None:
    """Severe vs Moderate: one critical domain dominates multiple mild deviations."""
    # 1 critical domain (1.0)
    crit_sevs = {"oil_protection": 1.0, "thermal": 0.0, "loading": 0.0}
    crit_score, _, _, _, _ = aggregate_othi_max_plus_secondary(crit_sevs, 0.20)
    assert crit_score == 0  # CRITICAL

    # 4 mild deviations (0.10 each)
    mild_sevs = {"thermal": 0.10, "loading": 0.10, "phase_neutral": 0.10, "voltage_pf_freq": 0.10}
    mild_score, _, _, _, _ = aggregate_othi_max_plus_secondary(mild_sevs, 0.20)
    # base = 0.10, sec = 0.20 * 0.30 = 0.06, tot = 0.16 -> OTHI = 84 (NORMAL)
    assert mild_score == 84
    assert mild_score > crit_score


def test_max_plus_secondary_saturation_clamping() -> None:
    """Saturation Clamping: total penalty is clamped to [0.0, 1.0], score in [0, 100]."""
    extreme_sevs = {
        "thermal": 1.0,
        "loading": 1.0,
        "phase_neutral": 1.0,
        "voltage_pf_freq": 1.0,
        "oil_protection": 1.0,
    }
    score, base, sec, tot, driving = aggregate_othi_max_plus_secondary(extreme_sevs, 0.20)
    assert base == 1.0
    assert sec == 0.20 * 4.0 == 0.80
    assert tot == 1.0  # strictly clamped at 1.0
    assert score == 0


# ---------------------------------------------------------------------------
# 2. Evidence-Family Deduplication Tests
# ---------------------------------------------------------------------------


def test_evidence_family_deduplication_within_domain() -> None:
    """Verify that multiple evidence items within the same condition family do not double-count."""
    engine = OTHIEngine(expected_cadence_seconds=900.0)
    t = _make_utc(12, 0, 0)

    # Telemetry providing all 5 domains
    measurements = [
        _make_measurement("top_oil_temperature", 92.0, "Cel"),
        _make_measurement("ambient_temperature", 30.0, "Cel"),
        _make_measurement("current_l1", 100.0, "A", phase="L1"),
        _make_measurement("current_l2", 100.0, "A", phase="L2"),
        _make_measurement("current_l3", 100.0, "A", phase="L3"),
        _make_measurement("voltage_l1_n", 230.0, "V", phase="L1"),
        _make_measurement("voltage_l2_n", 230.0, "V", phase="L2"),
        _make_measurement("voltage_l3_n", 230.0, "V", phase="L3"),
        _make_measurement("oil_level_percent", 80.0, "%"),
    ]
    event = _make_canonical_event("ev-01", t, measurements=measurements)

    # 2 EvidenceItems both in THERMAL_LIMIT_EXCEEDANCE (OTI limit and Rise limit)
    ev1 = EvidenceItem(
        evidence_id="ev-oti-01",
        asset_id="DT-001",
        event_time_utc=t,
        category=AnomalyCategory.THERMAL_LIMIT,
        detector_id="DET_THERMAL_LIMIT_OTI",
        observed_value=92.0,
        expected_value=85.0,
        severity=0.60,
        confidence=1.0,
    )
    ev2 = EvidenceItem(
        evidence_id="ev-rise-01",
        asset_id="DT-001",
        event_time_utc=t,
        category=AnomalyCategory.THERMAL_LIMIT,
        detector_id="DET_THERMAL_LIMIT_RISE",
        observed_value=62.0,
        expected_value=55.0,
        severity=0.50,
        confidence=1.0,
    )

    bundle = engine.evaluate(event=event, evidence_items=[ev1, ev2])

    # Thermal domain severity must be max(0.60, 0.50) = 0.60, NOT sum(0.60 + 0.50) = 1.10
    assert bundle.domains["thermal"].severity == 0.60
    assert bundle.domains["thermal"].driving_evidence_id == "ev-oti-01"
    assert bundle.domains["thermal"].driving_condition_family == "THERMAL_LIMIT_EXCEEDANCE"
    assert bundle.domains["thermal"].evidence_count == 2


def test_data_quality_evidence_does_not_penalize_physical_health() -> None:
    """DATA_QUALITY evidence (e.g. P-Q-S inconsistency) must NOT add a physical domain penalty."""
    engine = OTHIEngine(expected_cadence_seconds=900.0)
    t = _make_utc(12, 0, 0)

    measurements = [
        _make_measurement("top_oil_temperature", 60.0, "Cel"),
        _make_measurement("ambient_temperature", 25.0, "Cel"),
        _make_measurement("current_l1", 80.0, "A", phase="L1"),
        _make_measurement("current_l2", 80.0, "A", phase="L2"),
        _make_measurement("current_l3", 80.0, "A", phase="L3"),
        _make_measurement("voltage_l1_n", 230.0, "V", phase="L1"),
        _make_measurement("oil_level_percent", 80.0, "%"),
    ]
    event = _make_canonical_event("ev-dq", t, measurements=measurements)

    # Emit DATA_QUALITY evidence
    ev_dq = EvidenceItem(
        evidence_id="ev-pqs-01",
        asset_id="DT-001",
        event_time_utc=t,
        category=AnomalyCategory.DATA_QUALITY,
        detector_id="DET_DQ_PQS_INCONSISTENCY",
        observed_value=0.25,
        expected_value=0.0,
        severity=0.80,
        confidence=1.0,
    )

    bundle = engine.evaluate(event=event, evidence_items=[ev_dq])

    # Physical domains remain 0.0 severity -> OTHI = 100
    for d in bundle.current_domains:
        assert bundle.domains[d].severity == 0.0
    assert bundle.othi_score == 100
    # But evidence grade is downgraded from A due to data quality issue
    assert bundle.evidence_grade in (EvidenceGrade.B, EvidenceGrade.C)


# ---------------------------------------------------------------------------
# 3. Evidence Gating & Status Tests
# ---------------------------------------------------------------------------


def test_healthy_transformer_gating_and_score() -> None:
    """Healthy transformer with valid multi-domain telemetry receives OTHI = 100."""
    engine = OTHIEngine(expected_cadence_seconds=900.0)
    t = _make_utc(12, 0, 0)

    measurements = [
        _make_measurement("top_oil_temperature", 60.0, "Cel"),
        _make_measurement("ambient_temperature", 25.0, "Cel"),
        _make_measurement("current_l1", 80.0, "A", phase="L1"),
        _make_measurement("current_l2", 80.0, "A", phase="L2"),
        _make_measurement("current_l3", 80.0, "A", phase="L3"),
        _make_measurement("voltage_l1_n", 230.0, "V", phase="L1"),
        _make_measurement("voltage_l2_n", 230.0, "V", phase="L2"),
        _make_measurement("voltage_l3_n", 230.0, "V", phase="L3"),
        _make_measurement("oil_level_percent", 90.0, "%"),
    ]
    event = _make_canonical_event("ev-healthy", t, measurements=measurements)

    bundle = engine.evaluate(event=event, evidence_items=[])

    assert bundle.is_gated is False
    assert bundle.othi_score == 100
    assert bundle.status == HealthStatus.NORMAL
    assert bundle.base_penalty == 0.0
    assert bundle.secondary_penalty == 0.0
    assert bundle.evidence_grade == EvidenceGrade.A


def test_single_domain_mild_issue_is_gated_withheld() -> None:
    """Asset with only 1 current domain withholds numeric OTHI (is_gated = True)."""
    engine = OTHIEngine(expected_cadence_seconds=900.0)
    t = _make_utc(12, 0, 0)

    # Only top-oil temperature is present (1 domain: thermal)
    measurements = [
        _make_measurement("top_oil_temperature", 88.0, "Cel"),
    ]
    event = _make_canonical_event("ev-single-dom", t, measurements=measurements)

    ev = EvidenceItem(
        evidence_id="ev-oti-single",
        asset_id="DT-001",
        event_time_utc=t,
        category=AnomalyCategory.THERMAL_LIMIT,
        detector_id="DET_THERMAL_LIMIT_OTI",
        observed_value=88.0,
        expected_value=85.0,
        severity=0.45,
        confidence=1.0,
    )

    bundle = engine.evaluate(event=event, evidence_items=[ev])

    assert bundle.is_gated is True
    assert bundle.othi_score is None
    assert bundle.status is None
    assert bundle.gate_reason == "Insufficient current evidence"
    assert len(bundle.current_domains) == 1
    assert bundle.domains["thermal"].severity == 0.45


def test_two_medium_domains_calculate_numeric_othi_with_secondary_penalty() -> None:
    """Two valid domains calculate numeric OTHI applying 0.20 secondary penalty."""
    engine = OTHIEngine(expected_cadence_seconds=900.0)
    t = _make_utc(12, 0, 0)

    measurements = [
        _make_measurement("top_oil_temperature", 88.0, "Cel"),
        _make_measurement("current_l1", 150.0, "A", phase="L1"),
        _make_measurement("active_power_total", 120.0, "kW"),
    ]
    event = _make_canonical_event("ev-two-dom", t, measurements=measurements)

    ev_therm = EvidenceItem(
        evidence_id="ev-th-01",
        asset_id="DT-001",
        event_time_utc=t,
        category=AnomalyCategory.THERMAL_LIMIT,
        detector_id="DET_THERMAL_LIMIT_OTI",
        observed_value=88.0,
        severity=0.50,
        confidence=1.0,
    )
    ev_load = EvidenceItem(
        evidence_id="ev-ld-01",
        asset_id="DT-001",
        event_time_utc=t,
        category=AnomalyCategory.LOADING,
        detector_id="DET_LOADING_OVERLOAD",
        observed_value=1.15,
        severity=0.40,
        confidence=1.0,
    )

    bundle = engine.evaluate(event=event, evidence_items=[ev_therm, ev_load])

    assert bundle.is_gated is False
    # base = 0.50, sec = 0.20 * 0.40 = 0.08, total = 0.58 -> OTHI = 42 (WARNING)
    assert bundle.base_penalty == 0.50
    assert pytest.approx(bundle.secondary_penalty, abs=1e-5) == 0.08
    assert pytest.approx(bundle.total_penalty, abs=1e-5) == 0.58
    assert bundle.othi_score == 42
    assert bundle.status == HealthStatus.WARNING
    assert bundle.driving_domain == "thermal"


def test_direct_protection_trip_decisive_precedence() -> None:
    """Direct protection trip is decisive on its own, producing OTHI = 0, CRITICAL."""
    engine = OTHIEngine(expected_cadence_seconds=900.0)
    t = _make_utc(12, 0, 0)

    # Event only has protection trip bit
    measurements = [
        _make_measurement("top_oil_temp_trip", True, severity=QualitySeverity.GOOD),
    ]
    event = _make_canonical_event("ev-trip", t, measurements=measurements)

    ev_trip = EvidenceItem(
        evidence_id="ev-trip-01",
        asset_id="DT-001",
        event_time_utc=t,
        category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
        detector_id="DET_PROT_TRIP_DISCRETE",
        observed_value=True,
        severity=1.0,
        confidence=1.0,
    )

    bundle = engine.evaluate(event=event, evidence_items=[ev_trip])

    assert bundle.is_gated is False
    assert bundle.othi_score == 0
    assert bundle.status == HealthStatus.CRITICAL
    assert bundle.operational_status == HealthStatus.CRITICAL
    assert bundle.driving_domain == "oil_protection"
    assert bundle.driving_condition_family == "DIRECT_PROTECTION_TRIP"
    assert bundle.base_penalty == 1.0


# ---------------------------------------------------------------------------
# 4. Hybrid Stale-Domain & Anti-Uplift Policy Tests
# ---------------------------------------------------------------------------


def test_stale_domain_cadence_tracking() -> None:
    """Telemetry age transitions: CURRENT -> WARNING_STALE (HELD_STALE) -> HARD_STALE."""
    engine = OTHIEngine(expected_cadence_seconds=900.0)  # 15 min cadence
    # warning_stale = 30 min (1800s), hard_stale = 60 min (3600s)

    t0 = _make_utc(12, 0, 0)
    meas_all = [
        _make_measurement("top_oil_temperature", 60.0, "Cel"),
        _make_measurement("current_l1", 100.0, "A", phase="L1"),
    ]
    event0 = _make_canonical_event("ev0", t0, measurements=meas_all)
    bundle0 = engine.evaluate(event=event0, evidence_items=[])
    assert bundle0.domains["thermal"].freshness == DomainFreshness.CURRENT
    assert bundle0.domains["loading"].freshness == DomainFreshness.CURRENT

    # Step 1: 20 minutes later, loading drops out (only thermal arrives)
    t1 = t0 + timedelta(minutes=20)
    meas_t1 = [_make_measurement("top_oil_temperature", 62.0, "Cel")]
    event1 = _make_canonical_event("ev1", t1, measurements=meas_t1)
    bundle1 = engine.evaluate(event=event1, evidence_items=[])
    # 20 min <= 30 min -> loading is still considered CURRENT (within warning threshold)
    assert bundle1.domains["loading"].freshness == DomainFreshness.CURRENT

    # Step 2: 45 minutes after t0, only thermal arrives
    t2 = t0 + timedelta(minutes=45)
    meas_t2 = [_make_measurement("top_oil_temperature", 63.0, "Cel")]
    event2 = _make_canonical_event("ev2", t2, measurements=meas_t2)
    bundle2 = engine.evaluate(event=event2, evidence_items=[])
    # 45 min > 30 min and <= 60 min -> loading is WARNING_STALE
    assert bundle2.domains["loading"].freshness == DomainFreshness.WARNING_STALE
    assert bundle2.domains["loading"].is_stale is True

    # Step 3: 75 minutes after t0, only thermal arrives
    t3 = t0 + timedelta(minutes=75)
    meas_t3 = [_make_measurement("top_oil_temperature", 64.0, "Cel")]
    event3 = _make_canonical_event("ev3", t3, measurements=meas_t3)
    bundle3 = engine.evaluate(event=event3, evidence_items=[])
    # 75 min > 60 min -> loading is HARD_STALE
    assert bundle3.domains["loading"].freshness == DomainFreshness.HARD_STALE


def test_anti_uplift_rule_prevents_health_improvement_on_loss_of_observability() -> None:
    """Anti-Uplift Rule: losing degraded telemetry must NEVER cause OTHI to improve."""
    engine = OTHIEngine(expected_cadence_seconds=900.0)

    # Step 1: Asset has thermal issue (0.60) and clean loading (0.0) -> OTHI = 40 (WARNING)
    t0 = _make_utc(12, 0, 0)
    meas0 = [
        _make_measurement("top_oil_temperature", 90.0, "Cel"),
        _make_measurement("current_l1", 80.0, "A", phase="L1"),
        _make_measurement("voltage_l1_n", 230.0, "V", phase="L1"),
    ]
    ev_th = EvidenceItem(
        evidence_id="ev-th-01",
        asset_id="DT-001",
        event_time_utc=t0,
        category=AnomalyCategory.THERMAL_LIMIT,
        detector_id="DET_THERMAL_LIMIT_OTI",
        observed_value=90.0,
        severity=0.60,
        confidence=1.0,
    )
    event0 = _make_canonical_event("ev0", t0, measurements=meas0)
    bundle0 = engine.evaluate(event=event0, evidence_items=[ev_th])

    assert bundle0.is_gated is False
    assert bundle0.othi_score == 40
    assert bundle0.status == HealthStatus.WARNING
    assert bundle0.last_valid_othi == 40

    # Step 2: 45 minutes later, thermal sensor drops out (becomes stale).
    # Only clean loading and voltage arrive.
    # Without anti-uplift, the score would jump from 40 to 100 (NORMAL).
    # With anti-uplift, numeric score is withheld with explicit reason.
    t1 = t0 + timedelta(minutes=45)
    meas1 = [
        _make_measurement("current_l1", 80.0, "A", phase="L1"),
        _make_measurement("voltage_l1_n", 230.0, "V", phase="L1"),
    ]
    event1 = _make_canonical_event("ev1", t1, measurements=meas1)
    bundle1 = engine.evaluate(event=event1, evidence_items=[])

    assert bundle1.is_gated is True
    assert bundle1.othi_score is None
    assert bundle1.gate_reason == "Insufficient fresh evidence; last known condition was degraded"
    assert bundle1.last_valid_othi == 40
    assert bundle1.last_valid_status == HealthStatus.WARNING


# ---------------------------------------------------------------------------
# 5. Operational Band & Episode Persistence Tests
# ---------------------------------------------------------------------------


def test_operational_status_reflects_active_episodes() -> None:
    """Operational health band reflects active episode states."""
    engine = OTHIEngine(expected_cadence_seconds=900.0)
    t = _make_utc(12, 0, 0)

    measurements = [
        _make_measurement("top_oil_temperature", 60.0, "Cel"),
        _make_measurement("current_l1", 80.0, "A", phase="L1"),
    ]
    event = _make_canonical_event("ev-ep", t, measurements=measurements)

    # Active AnomalyEpisode in WARNING state
    active_ep = AnomalyEpisode(
        episode_id="ep-warn-01",
        asset_id="DT-001",
        state=EpisodeState.WARNING,
        category=AnomalyCategory.PHASE_OR_NEUTRAL,
        severity_score=0.50,
        start_time_utc=t,
        last_seen_time_utc=t,
        primary_reason="Persistent current imbalance",
    )

    bundle = engine.evaluate(event=event, evidence_items=[], open_episodes=[active_ep])

    # Raw score is 100 (NORMAL), but operational status is persisted WARNING
    assert bundle.raw_status == HealthStatus.NORMAL
    assert bundle.operational_status == HealthStatus.WARNING


# ---------------------------------------------------------------------------
# 6. TwinReducer End-to-End Integration Tests
# ---------------------------------------------------------------------------


def test_twin_reducer_with_othi_engine_end_to_end() -> None:
    """Verify TwinReducer produces full state with health_bundle and deterministic state hash."""
    othi_engine = OTHIEngine(expected_cadence_seconds=900.0)
    reducer = TwinReducer(othi_engine=othi_engine)

    t0 = _make_utc(12, 0, 0)
    meas = [
        _make_measurement("top_oil_temperature", 65.0, "Cel"),
        _make_measurement("ambient_temperature", 28.0, "Cel"),
        _make_measurement("current_l1", 100.0, "A", phase="L1"),
        _make_measurement("active_power_total", 60.0, "kW"),
    ]
    event = _make_canonical_event("ev-reducer-01", t0, measurements=meas)

    state = reducer.reduce(current_state=None, event=event)

    assert state.health_bundle is not None
    assert state.health_bundle.othi_score == 100
    assert state.health_bundle.is_gated is False
    assert state.health_bundle.algorithm_version == "MAX_PLUS_SECONDARY_V1"
    assert len(state.state_hash) == 64


def test_health_status_band_exact_mappings() -> None:
    """Verify exact 4-tier health band boundaries (NORMAL: 80-100, WATCH: 60-79, WARNING: 40-59, CRITICAL: 0-39)."""
    assert status_from_othi(100) == HealthStatus.NORMAL
    assert status_from_othi(80) == HealthStatus.NORMAL
    assert status_from_othi(79) == HealthStatus.WATCH
    assert status_from_othi(60) == HealthStatus.WATCH
    assert status_from_othi(59) == HealthStatus.WARNING
    assert status_from_othi(40) == HealthStatus.WARNING
    assert status_from_othi(39) == HealthStatus.CRITICAL
    assert status_from_othi(0) == HealthStatus.CRITICAL
    assert status_from_othi(None) is None

    assert status_from_severity(0.0) == HealthStatus.NORMAL
    assert status_from_severity(0.20) == HealthStatus.NORMAL
    assert status_from_severity(0.21) == HealthStatus.WATCH
    assert status_from_severity(0.40) == HealthStatus.WATCH
    assert status_from_severity(0.41) == HealthStatus.WARNING
    assert status_from_severity(0.60) == HealthStatus.WARNING
    assert status_from_severity(0.61) == HealthStatus.CRITICAL
    assert status_from_severity(1.0) == HealthStatus.CRITICAL


def test_multi_domain_secondary_penalty_sum() -> None:
    """Verify secondary penalty sums all non-base domain severities at 0.20."""
    # 4 active domains: base = 0.50 (loading), others = 0.30 (thermal), 0.20 (phase_neutral), 0.10 (voltage_pf_freq)
    severities = {
        "loading": 0.50,
        "thermal": 0.30,
        "phase_neutral": 0.20,
        "voltage_pf_freq": 0.10,
    }
    # base = 0.50
    # secondary = 0.20 * (0.30 + 0.20 + 0.10) = 0.20 * 0.60 = 0.12
    # total = 0.50 + 0.12 = 0.62
    # OTHI = round(100 * (1 - 0.62)) = 38 (CRITICAL)
    score, base_p, sec_p, tot_p, driving = aggregate_othi_max_plus_secondary(severities)
    assert driving == "loading"
    assert base_p == pytest.approx(0.50)
    assert sec_p == pytest.approx(0.12)
    assert tot_p == pytest.approx(0.62)
    assert score == 38
    assert status_from_othi(score) == HealthStatus.CRITICAL


def test_evidence_grade_transitions() -> None:
    """Verify deterministic evidence grade classification (A, B, C, U)."""
    engine = OTHIEngine(expected_cadence_seconds=900.0)

    # 4 clean current domains -> Grade A
    grade_a = engine._compute_evidence_grade(
        current_domains=["thermal", "loading", "phase_neutral", "voltage_pf_freq"],
        stale_domains=[],
        has_data_quality_issue=False,
    )
    assert grade_a == EvidenceGrade.A

    # 2 clean current domains -> Grade B
    grade_b = engine._compute_evidence_grade(
        current_domains=["thermal", "loading"],
        stale_domains=[],
        has_data_quality_issue=False,
    )
    assert grade_b == EvidenceGrade.B

    # 2 current domains but with data quality issue -> Grade C
    grade_c_dq = engine._compute_evidence_grade(
        current_domains=["thermal", "loading"],
        stale_domains=[],
        has_data_quality_issue=True,
    )
    assert grade_c_dq == EvidenceGrade.C

    # 1 current domain -> Grade C
    grade_c_1dom = engine._compute_evidence_grade(
        current_domains=["thermal"],
        stale_domains=[],
        has_data_quality_issue=False,
    )
    assert grade_c_1dom == EvidenceGrade.C

    # 0 current domains -> Grade U
    grade_u = engine._compute_evidence_grade(
        current_domains=[],
        stale_domains=["thermal"],
        has_data_quality_issue=False,
    )
    assert grade_u == EvidenceGrade.U

