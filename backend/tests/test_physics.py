"""Tests for Three-Phase Electrical Physics and Feature Derivation Engine.

Verifies Phase 3.1 requirements:
- Apparent power derivation S = sqrt(P^2 + Q^2)
- Power factor derivation PF = |P| / S
- NEMA Current magnitude imbalance (% IUB)
- NEMA Voltage magnitude imbalance (% VUB)
- Neutral current ratio In / max(Ieq, floor)
- P-Q-S inconsistency metric
- Relative load index (with unverified/reference vs verified rating)
- Missing-input handling (graceful None without crashing)
- Numerical stability on zero/near-zero denominators
- Full CanonicalEvent feature extraction pipeline
"""

import math
from datetime import datetime, timezone
import pytest

from app.engine.physics import (
    calculate_apparent_power,
    calculate_current_imbalance,
    calculate_equivalent_current,
    calculate_neutral_current_ratio,
    calculate_power_factor,
    calculate_pqs_inconsistency,
    calculate_relative_load_index,
    calculate_voltage_imbalance,
    extract_electrical_features,
)
from app.models.profile import AssetProfile, ProfileVerificationStatus
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


def _make_measurement(
    signal_id: str,
    value: float,
    unit: str,
    phase: str | None = None,
    severity: QualitySeverity = QualitySeverity.GOOD,
) -> Measurement:
    return Measurement(
        signal_id=signal_id,
        phase=phase,  # type: ignore[arg-type]
        value=value,
        value_type="float",
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=severity, flags=[]),
    )


def _make_event(measurements: list[Measurement]) -> CanonicalEvent:
    return CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt_phys_001",
        asset_id="DT-001",
        event_time_utc=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
        received_time_utc=None,
        source=SourceRef(
            system="tripura_csv",
            adapter_id="tripura_v1",
            source_record_id="rec_001",
            source_uri="data/tripura_raw/test.csv",
            raw_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        ),
        measurements=measurements,
        event_quality_flags=[],
        mapping_version="tripura-map-1.0.0",
    )


def test_apparent_power_calculation() -> None:
    """Verify S = sqrt(P^2 + Q^2) with known values and missing inputs."""
    # Classic 3-4-5 triangle: P=60 kW, Q=80 kvar -> S=100 kVA
    assert calculate_apparent_power(60.0, 80.0) == 100.0
    # Zero reactive power: P=50 kW, Q=0 kvar -> S=50 kVA
    assert calculate_apparent_power(50.0, 0.0) == 50.0
    # Negative reactive power (capacitive/leading): P=30, Q=-40 -> S=50
    assert calculate_apparent_power(30.0, -40.0) == 50.0
    # Missing input handling
    assert calculate_apparent_power(None, 80.0) is None
    assert calculate_apparent_power(60.0, None) is None
    assert calculate_apparent_power(None, None) is None


def test_power_factor_calculation() -> None:
    """Verify PF = |P| / S bounded to [0.0, 1.0] and numerical floor handling."""
    # P=80, S=100 -> PF=0.8
    assert calculate_power_factor(80.0, 100.0) == 0.8
    # Unity power factor
    assert calculate_power_factor(100.0, 100.0) == 1.0
    # Negative active power (reverse flow)
    assert calculate_power_factor(-75.0, 100.0) == 0.75
    # Near zero apparent power (below floor) -> None
    assert calculate_power_factor(0.0001, 0.0005, floor_kva=1e-3) is None
    # Missing inputs
    assert calculate_power_factor(None, 100.0) is None
    assert calculate_power_factor(80.0, None) is None


def test_current_imbalance_balanced_and_unbalanced() -> None:
    """Verify NEMA current magnitude imbalance percentage."""
    # Balanced three-phase: 100A, 100A, 100A -> I_mean=100A, IUB=0.0%
    mean_i, iub = calculate_current_imbalance(100.0, 100.0, 100.0)
    assert mean_i == 100.0
    assert iub == 0.0

    # Known unbalanced: 100A, 120A, 80A -> I_mean=100A, max_dev=20A -> IUB=20.0%
    mean_i2, iub2 = calculate_current_imbalance(100.0, 120.0, 80.0)
    assert mean_i2 == 100.0
    assert iub2 == 20.0

    # No load (all zero or below floor) -> IUB=0.0%
    mean_i0, iub0 = calculate_current_imbalance(0.02, 0.01, 0.03, floor_a=0.1)
    assert mean_i0 == 0.02
    assert iub0 == 0.0

    # Missing phase -> returns (None, None)
    assert calculate_current_imbalance(100.0, 120.0, None) == (None, None)
    assert calculate_current_imbalance(None, None, None) == (None, None)


def test_voltage_imbalance_calculation() -> None:
    """Verify NEMA voltage magnitude imbalance percentage."""
    # Balanced: 230V, 230V, 230V -> VUB=0.0%
    assert calculate_voltage_imbalance(230.0, 230.0, 230.0) == 0.0

    # Known unbalanced: 230V, 240V, 220V -> mean=230V, max_dev=10V -> VUB = 100 * 10 / 230 = 4.3478%
    vub = calculate_voltage_imbalance(230.0, 240.0, 220.0)
    assert vub == pytest.approx(4.3478, rel=1e-3)

    # Missing phase
    assert calculate_voltage_imbalance(230.0, 230.0, None) is None


def test_neutral_current_ratio_calculation() -> None:
    """Verify neutral current ratio In / max(Ieq, floor)."""
    # Balanced phase currents 100A, 100A, 100A -> I_eq = 100A. In = 10A -> ratio = 0.10
    ratio = calculate_neutral_current_ratio(10.0, 100.0, 100.0, 100.0)
    assert ratio == 0.10

    # Zero neutral current
    assert calculate_neutral_current_ratio(0.0, 100.0, 100.0, 100.0) == 0.0

    # Missing neutral current
    assert calculate_neutral_current_ratio(None, 100.0, 100.0, 100.0) is None
    # Missing phase current
    assert calculate_neutral_current_ratio(10.0, 100.0, None, 100.0) is None


def test_pqs_inconsistency_metric() -> None:
    """Verify P-Q-S inconsistency metric |S_obs^2 - P^2 - Q^2| / max(S_obs^2, floor)."""
    # Perfectly consistent: S_obs = 100 kVA, P = 80 kW, Q = 60 kvar -> err = 0.0
    err_zero = calculate_pqs_inconsistency(100.0, 80.0, 60.0)
    assert err_zero == 0.0

    # Inconsistent: S_obs = 110 kVA, P = 80 kW, Q = 60 kvar -> |110^2 - 100^2| / 110^2 = 2100 / 12100 = 0.173554
    err_inconsistent = calculate_pqs_inconsistency(110.0, 80.0, 60.0)
    assert err_inconsistent == pytest.approx(0.173554, rel=1e-4)

    # Missing inputs
    assert calculate_pqs_inconsistency(None, 80.0, 60.0) is None
    assert calculate_pqs_inconsistency(100.0, None, 60.0) is None


def test_relative_load_index_calculation() -> None:
    """Verify relative load index u = S / S_base with reference vs verified rating."""
    # Unverified Tripura reference (142.898 kVA): S = 71.449 kVA -> u = 0.5000
    u_ref = calculate_relative_load_index(71.449, rated_kva=None, reference_kva=142.898)
    assert u_ref == pytest.approx(0.5000, rel=1e-3)

    # Verified rating (e.g. 100 kVA nameplate): S = 71.449 kVA -> u = 0.7145
    u_rated = calculate_relative_load_index(71.449, rated_kva=100.0, reference_kva=142.898)
    assert u_rated == pytest.approx(0.7145, rel=1e-3)

    # Missing apparent power
    assert calculate_relative_load_index(None) is None


def test_full_electrical_feature_extraction_pipeline() -> None:
    """Verify extract_electrical_features correctly maps CanonicalEvent into DerivedFeatures."""
    measurements = [
        _make_measurement("active_power_total", 80.0, "kW"),
        _make_measurement("reactive_power_total", 60.0, "kvar"),
        _make_measurement("apparent_power_total", 100.0, "kVA"),
        _make_measurement("current_l1", 100.0, "A", phase="L1"),
        _make_measurement("current_l2", 120.0, "A", phase="L2"),
        _make_measurement("current_l3", 80.0, "A", phase="L3"),
        _make_measurement("neutral_current", 10.0, "A", phase="N"),
        _make_measurement("voltage_l1_n", 230.0, "V", phase="L1"),
        _make_measurement("voltage_l2_n", 240.0, "V", phase="L2"),
        _make_measurement("voltage_l3_n", 220.0, "V", phase="L3"),
    ]
    event = _make_event(measurements)

    features = extract_electrical_features(event, load_reference_kva=142.898)

    assert features.timestamp_utc == event.event_time_utc
    assert features.apparent_power_derived_kva == 100.0
    assert features.power_factor_derived == 0.8
    assert features.current_mean_a == 100.0
    assert features.current_magnitude_imbalance_pct == 20.0
    assert features.voltage_magnitude_imbalance_pct == pytest.approx(4.3478, rel=1e-3)
    assert features.neutral_current_ratio == pytest.approx(10.0 / math.sqrt((100**2 + 120**2 + 80**2) / 3), rel=1e-3)
    assert features.pqs_inconsistency == 0.0
    assert features.relative_load_index == pytest.approx(100.0 / 142.898, rel=1e-3)
    assert features.transform_version == "1.0.0"


def test_partial_measurements_feature_extraction() -> None:
    """Verify feature extraction with sparse inputs (missing voltage, missing Q)."""
    # Event with only active power and current
    measurements = [
        _make_measurement("active_power_total", 50.0, "kW"),
        _make_measurement("current_l1", 50.0, "A", phase="L1"),
        _make_measurement("current_l2", 50.0, "A", phase="L2"),
        _make_measurement("current_l3", 50.0, "A", phase="L3"),
    ]
    event = _make_event(measurements)
    features = extract_electrical_features(event)

    assert features.apparent_power_derived_kva is None  # Q missing
    assert features.power_factor_derived is None
    assert features.current_mean_a == 50.0
    assert features.current_magnitude_imbalance_pct == 0.0
    assert features.voltage_magnitude_imbalance_pct is None  # Voltage missing
    assert features.neutral_current_ratio is None            # In missing
    assert features.pqs_inconsistency is None


def test_tripura_adapter_to_physics_integration() -> None:
    """Verify physics transforms work on real-shaped Tripura adapter events."""
    from app.adapters.tripura import TripuraCSVAdapter

    adapter = TripuraCSVAdapter()
    raw_record = {
        "DeviceTimeStamp": "2020-03-01 12:00:00",
        "OTI": "58.4",
        "ATI": "27.2",
        "IL1": "45.2",
        "IL2": "48.1",
        "IL3": "42.0",
        "INUT": "4.5",
        "VL1": "232.0",
        "VL2": "230.5",
        "VL3": "229.0",
        "KW": "30.5",
        "KVAR": "12.2",
    }
    event = adapter.transform_record(raw_record, asset_id="DT-001")
    features = extract_electrical_features(event, load_reference_kva=142.898)

    assert features.apparent_power_derived_kva == pytest.approx(math.sqrt(30.5**2 + 12.2**2), rel=1e-3)
    assert features.current_mean_a == pytest.approx((45.2 + 48.1 + 42.0) / 3, rel=1e-3)
    assert features.current_magnitude_imbalance_pct is not None and features.current_magnitude_imbalance_pct > 0.0
    assert features.voltage_magnitude_imbalance_pct is not None and features.voltage_magnitude_imbalance_pct > 0.0
    assert features.neutral_current_ratio is not None and features.neutral_current_ratio > 0.0
    assert features.relative_load_index is not None and features.relative_load_index > 0.0

