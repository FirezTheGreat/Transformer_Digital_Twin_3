"""Unit and Integration Tests for Phase 6.2 — Gated Thermal Exposure & Standards-Derived Ageing.

Verifies:
1. Standards-derived relative ageing rate equations:
   - IEEE Std C57.91-2011 Arrhenius formulation (Ref: 110 Cel) within 0.5% of standard tables.
   - IEC 60076-7:2018 relative ageing rate equation (Ref: 98 Cel).
2. Observed top-oil thermal exposure accumulation:
   - Actual timestamp intervals (dt), time-in-band integration (> 85C, > 95C, > 105C), and degree-hours.
3. Telemetry gap detection and coverage tracking.
4. Discrete WTI alarm/trip contacts isolation from continuous hot-spot measurements.
5. Capability-specific gating:
   - Direct hot-spot measurement enabled even when C3 grey-box model is unpromoted.
   - Model-derived hot-spot enabled only when model is promoted.
   - Gated off when insulation profile is UNKNOWN or unsupported.
6. Explicit standards edition metadata tracking.
7. Explicit project exclusions (whole_life_rul_supported is False, failure_probability_supported is False).
8. End-to-end integration with TwinReducer.
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.engine.exposure import (
    ThermalExposureEngine,
    compute_relative_ageing_rate,
)
from app.engine.reducer import TwinReducer
from app.models.exposure import (
    AgeingStandardMetadata,
    InsulationProfile,
    ThermalExposureBundle,
)
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
    unit: str = "Cel",
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
        event_quality_flags=[],
        measurements=measurements or [],
        mapping_version="test-map-1.0.0",
    )


# ---------------------------------------------------------------------------
# 1. Equation Verification Tests
# ---------------------------------------------------------------------------


def test_ieee_thermally_upgraded_paper_arrhenius_values() -> None:
    """Verify IEEE Std C57.91-2011 Table 1 F_AA values across operating temperatures."""
    profile = InsulationProfile.CELLULOSIC_THERMALLY_UPGRADED

    # At reference temp 110 Cel: F_AA == 1.0 exactly
    rate_110, meta_110 = compute_relative_ageing_rate(110.0, profile)
    assert rate_110 == pytest.approx(1.0, rel=1e-5)
    assert meta_110.standard_id == "IEEE_C57_91_2011"
    assert meta_110.reference_temp_c == 110.0

    # At 120 Cel: F_AA approx 2.709
    rate_120, _ = compute_relative_ageing_rate(120.0, profile)
    assert rate_120 == pytest.approx(2.7088, rel=1e-3)

    # At 100 Cel: F_AA approx 0.350 (0.3499)
    rate_100, _ = compute_relative_ageing_rate(100.0, profile)
    assert rate_100 == pytest.approx(0.3499, rel=1e-3)

    # At 90 Cel: F_AA approx 0.116
    rate_90, _ = compute_relative_ageing_rate(90.0, profile)
    assert rate_90 == pytest.approx(0.1156, rel=1e-3)

    # At 80 Cel: F_AA approx 0.03585
    rate_80, _ = compute_relative_ageing_rate(80.0, profile)
    assert rate_80 == pytest.approx(0.03585, rel=1e-3)


def test_iec_non_thermally_upgraded_paper_half_life_values() -> None:
    """Verify IEC 60076-7:2018 relative ageing rate V values across temperatures."""
    profile = InsulationProfile.CELLULOSIC_NON_THERMALLY_UPGRADED

    # At reference temp 98 Cel: V == 1.0 exactly
    rate_98, meta_98 = compute_relative_ageing_rate(98.0, profile)
    assert rate_98 == pytest.approx(1.0, rel=1e-5)
    assert meta_98.standard_id == "IEC_60076_7_2018"
    assert meta_98.reference_temp_c == 98.0

    # At 104 Cel (98 + 6): V == 2.0
    rate_104, _ = compute_relative_ageing_rate(104.0, profile)
    assert rate_104 == pytest.approx(2.0, rel=1e-5)

    # At 110 Cel (98 + 12): V == 4.0
    rate_110, _ = compute_relative_ageing_rate(110.0, profile)
    assert rate_110 == pytest.approx(4.0, rel=1e-5)

    # At 92 Cel (98 - 6): V == 0.5
    rate_92, _ = compute_relative_ageing_rate(92.0, profile)
    assert rate_92 == pytest.approx(0.5, rel=1e-5)


def test_unknown_or_unsupported_profile_raises_value_error() -> None:
    """Unknown or unsupported insulation profiles raise ValueError in direct computation."""
    with pytest.raises(ValueError, match="unsupported insulation profile"):
        compute_relative_ageing_rate(110.0, InsulationProfile.UNKNOWN)

    with pytest.raises(ValueError, match="unsupported insulation profile"):
        compute_relative_ageing_rate(110.0, InsulationProfile.OTHER_UNSUPPORTED)


# ---------------------------------------------------------------------------
# 2. Observed Top-Oil Exposure & Degree-Hours Tests
# ---------------------------------------------------------------------------


def test_observed_top_oil_exposure_accumulation() -> None:
    """Top-oil exposure accumulates continuous time-in-band and degree-hours."""
    engine = ThermalExposureEngine(asset_id="DT-001", max_gap_seconds=7200.0)

    t0 = _make_utc(12, 0, 0)
    # Event 0: 80 Cel (12:00)
    e0 = _make_canonical_event("e0", t0, measurements=[_make_measurement("top_oil_temperature", 80.0)])
    b0 = engine.step(e0)
    assert b0.observed_exposure.valid_sample_count == 1
    assert b0.observed_exposure.peak_top_oil_temp_c == 80.0
    assert b0.observed_exposure.total_monitored_seconds == 0.0

    # Event 1: 90 Cel (12:30 -> dt = 1800s / 0.5h)
    # 90 Cel > 85 Cel by 5 Cel -> degree-hours_85 = 5 * 0.5 = 2.5 degree-hours
    t1 = t0 + timedelta(minutes=30)
    e1 = _make_canonical_event("e1", t1, measurements=[_make_measurement("top_oil_temperature", 90.0)])
    b1 = engine.step(e1)
    assert b1.observed_exposure.valid_sample_count == 2
    assert b1.observed_exposure.total_monitored_seconds == 1800.0
    assert b1.observed_exposure.total_monitored_hours == pytest.approx(0.5)
    assert b1.observed_exposure.peak_top_oil_temp_c == 90.0
    assert b1.observed_exposure.degree_hours_above_85c == pytest.approx(2.5)
    assert b1.observed_exposure.degree_hours_above_95c == 0.0
    assert b1.observed_exposure.bands["T_gt_85C"].duration_seconds == 1800.0
    assert b1.observed_exposure.bands["T_gt_95C"].duration_seconds == 0.0

    # Event 2: 100 Cel (13:00 -> dt = 1800s / 0.5h)
    # 100 Cel > 85 Cel by 15 Cel -> +7.5 deg-h (total 10.0)
    # 100 Cel > 95 Cel by 5 Cel -> +2.5 deg-h (total 2.5)
    t2 = t1 + timedelta(minutes=30)
    e2 = _make_canonical_event("e2", t2, measurements=[_make_measurement("top_oil_temperature", 100.0)])
    b2 = engine.step(e2)
    assert b2.observed_exposure.valid_sample_count == 3
    assert b2.observed_exposure.total_monitored_hours == pytest.approx(1.0)
    assert b2.observed_exposure.peak_top_oil_temp_c == 100.0
    assert b2.observed_exposure.degree_hours_above_85c == pytest.approx(10.0)
    assert b2.observed_exposure.degree_hours_above_95c == pytest.approx(2.5)
    assert b2.observed_exposure.degree_hours_above_105c == 0.0
    assert b2.observed_exposure.bands["T_gt_85C"].duration_seconds == 3600.0
    assert b2.observed_exposure.bands["T_gt_95C"].duration_seconds == 1800.0


def test_telemetry_gap_does_not_accumulate_thermal_stress() -> None:
    """Intervals exceeding max_gap_seconds are treated as coverage gaps without accumulation."""
    engine = ThermalExposureEngine(asset_id="DT-001", max_gap_seconds=3600.0)  # 1 hour max gap

    t0 = _make_utc(12, 0, 0)
    e0 = _make_canonical_event("e0", t0, measurements=[_make_measurement("top_oil_temperature", 90.0)])
    engine.step(e0)

    # 4 hours later: gap occurs
    t1 = t0 + timedelta(hours=4)
    e1 = _make_canonical_event("e1", t1, measurements=[_make_measurement("top_oil_temperature", 95.0)])
    b1 = engine.step(e1)

    assert b1.observed_exposure.total_gap_seconds == 14400.0  # 4 hours gap recorded
    assert b1.observed_exposure.total_monitored_seconds == 0.0  # Did not falsely integrate across 4h gap
    assert b1.observed_exposure.degree_hours_above_85c == 0.0


# ---------------------------------------------------------------------------
# 3. Discrete WTI Contact Isolation Tests
# ---------------------------------------------------------------------------


def test_discrete_wti_contacts_are_isolated_from_continuous_measurements() -> None:
    """Discrete binary alarm/trip contacts are strictly rejected from temperature integration."""
    engine = ThermalExposureEngine(
        asset_id="DT-001",
        insulation_profile=InsulationProfile.CELLULOSIC_THERMALLY_UPGRADED,
    )
    t0 = _make_utc(12, 0, 0)

    # Event containing discrete binary trips/alarms
    meas = [
        _make_measurement("top_oil_temp_trip", True, unit="1"),
        _make_measurement("winding_temp_alarm", 1, unit="1"),
        _make_measurement("breaker_trip", "TRIP", unit="1"),
    ]
    event = _make_canonical_event("e-discrete", t0, measurements=meas)
    bundle = engine.step(event)

    # Neither top-oil nor direct hot-spot is populated from binary contacts
    assert bundle.observed_exposure.valid_sample_count == 0
    assert bundle.observed_exposure.peak_top_oil_temp_c is None
    assert bundle.standards_ageing.hotspot_source == "UNAVAILABLE"
    assert bundle.standards_ageing.is_enabled is False


# ---------------------------------------------------------------------------
# 4. Capability Gating Tests (Decoupled C4 vs C3)
# ---------------------------------------------------------------------------


def test_direct_hotspot_enabled_with_verified_profile_even_if_model_unpromoted() -> None:
    """Direct hot-spot measurement enables standards ageing even if thermal model is unpromoted."""
    engine = ThermalExposureEngine(
        asset_id="DT-001",
        insulation_profile=InsulationProfile.CELLULOSIC_THERMALLY_UPGRADED,
    )

    t0 = _make_utc(12, 0, 0)
    meas0 = [
        _make_measurement("top_oil_temperature", 85.0),
        _make_measurement("winding_temperature_hotspot", 110.0),
    ]
    e0 = _make_canonical_event("e0", t0, measurements=meas0)

    # Model is unpromoted (is_model_promoted=False)
    b0 = engine.step(e0, is_model_promoted=False)

    assert b0.standards_ageing.is_enabled is True
    assert b0.standards_ageing.hotspot_source == "DIRECT_MEASUREMENT"
    assert b0.standards_ageing.current_relative_ageing_rate == pytest.approx(1.0)
    assert b0.standards_ageing.peak_hotspot_temp_c == 110.0

    # Step forward 1 hour at 120 Cel
    t1 = t0 + timedelta(hours=1)
    meas1 = [
        _make_measurement("top_oil_temperature", 95.0),
        _make_measurement("winding_temperature_hotspot", 120.0),
    ]
    e1 = _make_canonical_event("e1", t1, measurements=meas1)
    b1 = engine.step(e1, is_model_promoted=False)

    assert b1.standards_ageing.is_enabled is True
    assert b1.standards_ageing.current_relative_ageing_rate == pytest.approx(2.7088, rel=1e-3)
    assert b1.standards_ageing.equivalent_ageing_hours == pytest.approx(2.7088, rel=1e-3)
    assert b1.standards_ageing.observed_interval_hours == pytest.approx(1.0)
    assert b1.standards_ageing.average_relative_ageing_rate == pytest.approx(2.7088, rel=1e-3)


def test_missing_direct_hotspot_gates_off_when_model_unpromoted() -> None:
    """When direct hot-spot is absent and thermal model is unpromoted, standards ageing is gated off."""
    engine = ThermalExposureEngine(
        asset_id="DT-001",
        insulation_profile=InsulationProfile.CELLULOSIC_THERMALLY_UPGRADED,
    )

    t0 = _make_utc(12, 0, 0)
    meas0 = [_make_measurement("top_oil_temperature", 85.0)]
    e0 = _make_canonical_event("e0", t0, measurements=meas0)

    # Unpromoted grey-box model without direct hot-spot
    bundle = engine.step(e0, modeled_hotspot_degc=105.0, is_model_promoted=False)

    assert bundle.standards_ageing.is_enabled is False
    assert bundle.standards_ageing.hotspot_source == "UNAVAILABLE"
    assert "unpromoted" in bundle.standards_ageing.gate_reason.lower()
    assert bundle.standards_ageing.equivalent_ageing_hours is None


def test_model_derived_hotspot_enabled_when_model_is_promoted() -> None:
    """When thermal model is promoted, model-derived hot-spot is used for standards ageing."""
    engine = ThermalExposureEngine(
        asset_id="DT-001",
        insulation_profile=InsulationProfile.CELLULOSIC_NON_THERMALLY_UPGRADED,
    )

    t0 = _make_utc(12, 0, 0)
    meas0 = [_make_measurement("top_oil_temperature", 80.0)]
    e0 = _make_canonical_event("e0", t0, measurements=meas0)

    # Promoted grey-box model providing modeled hot-spot 98 Cel (V = 1.0)
    b0 = engine.step(e0, modeled_hotspot_degc=98.0, is_model_promoted=True)

    assert b0.standards_ageing.is_enabled is True
    assert b0.standards_ageing.hotspot_source == "PROMOTED_MODEL"
    assert b0.standards_ageing.current_relative_ageing_rate == pytest.approx(1.0)
    assert b0.standards_ageing.standard_metadata.standard_id == "IEC_60076_7_2018"


def test_unknown_insulation_profile_gates_off_ageing() -> None:
    """Insulation profile UNKNOWN suppresses standards ageing even with valid hot-spot telemetry."""
    engine = ThermalExposureEngine(
        asset_id="DT-001",
        insulation_profile=InsulationProfile.UNKNOWN,
    )

    t0 = _make_utc(12, 0, 0)
    meas0 = [
        _make_measurement("top_oil_temperature", 85.0),
        _make_measurement("winding_temperature_hotspot", 110.0),
    ]
    e0 = _make_canonical_event("e0", t0, measurements=meas0)
    bundle = engine.step(e0)

    assert bundle.standards_ageing.is_enabled is False
    assert "unknown" in bundle.standards_ageing.gate_reason.lower()
    assert bundle.standards_ageing.equivalent_ageing_hours is None
    # Observed top-oil exposure is still active
    assert bundle.observed_exposure.is_valid is True


# ---------------------------------------------------------------------------
# 5. Metadata & Exclusion Assertions
# ---------------------------------------------------------------------------


def test_project_exclusions_and_metadata() -> None:
    """Verify explicit flags documenting unsupported whole-life RUL and failure probability."""
    engine = ThermalExposureEngine(asset_id="DT-001")
    t0 = _make_utc(12, 0, 0)
    e0 = _make_canonical_event("e0", t0, measurements=[_make_measurement("top_oil_temperature", 75.0)])
    bundle = engine.step(e0)

    assert bundle.whole_life_rul_supported is False
    assert bundle.failure_probability_supported is False


# ---------------------------------------------------------------------------
# 6. TwinReducer Integration Tests
# ---------------------------------------------------------------------------


def test_twin_reducer_with_exposure_engine_integration() -> None:
    """Verify TwinReducer updates exposure_state seamlessly when exposure_engine is provided."""
    exposure_engine = ThermalExposureEngine(
        asset_id="DT-001",
        insulation_profile=InsulationProfile.CELLULOSIC_THERMALLY_UPGRADED,
    )
    reducer = TwinReducer(exposure_engine=exposure_engine)

    t0 = _make_utc(12, 0, 0)
    meas0 = [
        _make_measurement("top_oil_temperature", 90.0),
        _make_measurement("winding_temperature_hotspot", 110.0),
        _make_measurement("current_l1", 100.0, "A", phase="L1"),
    ]
    e0 = _make_canonical_event("e0", t0, measurements=meas0)
    state0 = reducer.reduce(current_state=None, event=e0)

    assert state0.exposure_state.is_ageing_enabled is True
    assert state0.exposure_state.equivalent_ageing_hours == 0.0

    # Step 2: 1 hour later at 110 Cel
    t1 = t0 + timedelta(hours=1)
    meas1 = [
        _make_measurement("top_oil_temperature", 90.0),
        _make_measurement("winding_temperature_hotspot", 110.0),
        _make_measurement("current_l1", 100.0, "A", phase="L1"),
    ]
    e1 = _make_canonical_event("e1", t1, measurements=meas1)
    state1 = reducer.reduce(current_state=state0, event=e1)

    assert state1.exposure_state.equivalent_ageing_hours == pytest.approx(1.0)
    assert state1.exposure_state.time_above_bands_s["T_gt_85C"] == 3600.0
    assert len(state1.state_hash) == 64
