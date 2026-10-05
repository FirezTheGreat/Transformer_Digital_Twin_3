"""Tests for Phase 3.3 Dynamic Capability Tier Evaluator."""

from datetime import datetime, timezone
import pytest

from app.adapters.tripura import TripuraCSVAdapter
from app.engine.capability import CapabilityEvaluator, evaluate_capabilities
from app.engine.reducer import TwinReducer
from app.models.capability import CapabilityTier
from app.models.profile import AssetProfile, InsulationClass, ProfileField, ProfileVerificationStatus
from app.models.telemetry import CanonicalEvent, Measurement, MeasurementQuality, QualitySeverity
from app.models.twin_state import ThermalLatentState, TwinState


def _make_measurement(
    signal_id: str,
    value: float | int | str | None,
    unit: str,
    severity: QualitySeverity = QualitySeverity.GOOD,
    phase: str | None = None,
    timestamp: datetime | None = None,
) -> Measurement:
    val_type = "int" if isinstance(value, int) else ("float" if isinstance(value, float) else "str")
    return Measurement(
        signal_id=signal_id,
        phase=phase,  # type: ignore[arg-type]
        value=value if value is not None else 0.0,
        value_type=val_type,
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=severity, flags=[] if severity == QualitySeverity.GOOD else ["SUSPECT"]),
    )


def _make_twin_state(
    observations: dict[str, Measurement],
    asset_id: str = "DT-001",
    model_status: str = "UNCALIBRATED",
    is_ageing_enabled: bool = False,
) -> TwinState:
    now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    return TwinState(
        asset_id=asset_id,
        state_time_utc=now,
        last_processed_event_id="evt_001",
        event_time_watermark_utc=now,
        state_sequence=1,
        current_observations=observations,
        thermal_latent=ThermalLatentState(model_status=model_status),
        exposure_state={"time_above_bands_s": {}, "equivalent_ageing_hours": None, "is_ageing_enabled": is_ageing_enabled},
        state_hash="dummy_hash",
    )


def test_only_integrity_data_yields_c0() -> None:
    """Basic non-electrical, non-thermal signal enables C0 only."""
    obs = {
        "status_flag": _make_measurement("status_flag", 1, "dimensionless"),
    }
    state = _make_twin_state(obs)
    manifest = evaluate_capabilities(state)

    assert manifest.highest_tier == CapabilityTier.C0_INTEGRITY
    assert manifest.capabilities["C0"].enabled is True
    assert manifest.capabilities["C1"].enabled is False
    assert "MISSING_ELECTRICAL_INPUTS" in manifest.capabilities["C1"].disabled_reason_codes
    assert manifest.capabilities["C2"].enabled is False
    assert "MISSING_CONTINUOUS_TOP_OIL_TEMPERATURE" in manifest.capabilities["C2"].disabled_reason_codes
    assert manifest.capabilities["C3"].enabled is False
    assert manifest.capabilities["C4"].enabled is False


def test_valid_electrical_telemetry_yields_c1() -> None:
    """Valid electrical power and currents enable C1."""
    obs = {
        "active_power": _make_measurement("active_power", 45.0, "kW"),
        "reactive_power": _make_measurement("reactive_power", 15.0, "kvar"),
        "apparent_power": _make_measurement("apparent_power", 47.43, "kVA"),
        "current_L1": _make_measurement("current", 65.0, "A", phase="L1"),
        "current_L2": _make_measurement("current", 66.0, "A", phase="L2"),
        "current_L3": _make_measurement("current", 64.0, "A", phase="L3"),
        "voltage_L1": _make_measurement("voltage", 230.0, "V", phase="L1"),
        "voltage_L2": _make_measurement("voltage", 231.0, "V", phase="L2"),
        "voltage_L3": _make_measurement("voltage", 229.0, "V", phase="L3"),
    }
    state = _make_twin_state(obs)
    manifest = evaluate_capabilities(state)

    assert manifest.highest_tier == CapabilityTier.C1_ELECTRICAL
    assert manifest.capabilities["C0"].enabled is True
    assert manifest.capabilities["C1"].enabled is True
    assert manifest.capabilities["loading_proxy"].enabled is True
    assert manifest.capabilities["current_imbalance"].enabled is True
    assert manifest.capabilities["voltage_imbalance"].enabled is True
    assert manifest.capabilities["pqs_consistency"].enabled is True


def test_partial_electrical_inputs_disable_specific_sub_capabilities() -> None:
    """Missing phase current disables imbalance only, keeping C1 loading active."""
    obs = {
        "active_power": _make_measurement("active_power", 45.0, "kW"),
        "current_L1": _make_measurement("current", 65.0, "A", phase="L1"),
        # L2 and L3 missing
    }
    state = _make_twin_state(obs)
    manifest = evaluate_capabilities(state)

    assert manifest.highest_tier == CapabilityTier.C1_ELECTRICAL
    assert manifest.capabilities["C1"].enabled is True
    assert manifest.capabilities["loading_proxy"].enabled is True
    assert manifest.capabilities["current_imbalance"].enabled is False
    assert "MISSING_THREE_PHASE_CURRENT" in manifest.capabilities["current_imbalance"].disabled_reason_codes
    assert "current_L2" in manifest.capabilities["current_imbalance"].missing_inputs


def test_valid_continuous_top_oil_yields_c2() -> None:
    """Valid continuous top-oil temperature enables C2."""
    obs = {
        "active_power": _make_measurement("active_power", 45.0, "kW"),
        "top_oil_temperature": _make_measurement("top_oil_temperature", 62.5, "Cel"),
    }
    state = _make_twin_state(obs)
    manifest = evaluate_capabilities(state)

    assert manifest.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE
    assert manifest.capabilities["C2"].enabled is True
    assert manifest.capabilities["top_oil_monitoring"].enabled is True
    assert manifest.capabilities["C3"].enabled is False  # Missing ambient and unpromoted model


def test_wti_binary_contact_does_not_satisfy_c2() -> None:
    """CRITICAL: Discrete WTI alarm contact must NOT satisfy C2 top-oil requirement."""
    obs = {
        "active_power": _make_measurement("active_power", 45.0, "kW"),
        "winding_temp_alarm_contact": _make_measurement("winding_temp_alarm_contact", 0, "dimensionless"),
    }
    state = _make_twin_state(obs)
    manifest = evaluate_capabilities(state)

    assert manifest.highest_tier == CapabilityTier.C1_ELECTRICAL
    assert manifest.capabilities["C2"].enabled is False
    assert "DISCRETE_WTI_NOT_SUBSTITUTE_FOR_TOP_OIL" in manifest.capabilities["C2"].disabled_reason_codes
    assert "top_oil_temperature" in manifest.capabilities["C2"].missing_inputs


def test_bad_quality_signal_prevents_capability() -> None:
    """Measurements marked with BAD quality severity must not enable capabilities."""
    obs = {
        "active_power": _make_measurement("active_power", 45.0, "kW"),
        "top_oil_temperature": _make_measurement("top_oil_temperature", 62.5, "Cel", severity=QualitySeverity.BAD),
    }
    state = _make_twin_state(obs)
    manifest = evaluate_capabilities(state)

    assert manifest.highest_tier == CapabilityTier.C1_ELECTRICAL
    assert manifest.capabilities["C2"].enabled is False
    assert "BAD_QUALITY_TOP_OIL_TEMPERATURE" in manifest.capabilities["C2"].disabled_reason_codes


def test_unpromoted_thermal_model_prevents_c3() -> None:
    """Even with top-oil, ambient, and load driver, unpromoted model blocks C3."""
    obs = {
        "apparent_power": _make_measurement("apparent_power", 50.0, "kVA"),
        "top_oil_temperature": _make_measurement("top_oil_temperature", 60.0, "Cel"),
        "ambient_temperature": _make_measurement("ambient_temperature", 28.0, "Cel"),
    }
    state = _make_twin_state(obs, model_status="UNCALIBRATED")
    manifest = evaluate_capabilities(state, model_version="uncalibrated", is_model_promoted=False)

    assert manifest.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE
    assert manifest.capabilities["C2"].enabled is True
    assert manifest.capabilities["C3"].enabled is False
    assert "MODEL_NOT_PROMOTED" in manifest.capabilities["C3"].disabled_reason_codes
    assert "promoted_thermal_model" in manifest.capabilities["C3"].missing_inputs


def test_promoted_thermal_model_enables_c3() -> None:
    """When model is promoted and all prerequisites exist, C3 is enabled."""
    obs = {
        "apparent_power": _make_measurement("apparent_power", 50.0, "kVA"),
        "top_oil_temperature": _make_measurement("top_oil_temperature", 60.0, "Cel"),
        "ambient_temperature": _make_measurement("ambient_temperature", 28.0, "Cel"),
    }
    state = _make_twin_state(obs, model_status="PROMOTED")
    manifest = evaluate_capabilities(state, model_version="1.0.0", is_model_promoted=True)

    assert manifest.highest_tier == CapabilityTier.C3_THERMAL_PREDICTIVE
    assert manifest.capabilities["C3"].enabled is True
    assert manifest.capabilities["C3"].model_status == "PROMOTED"
    assert manifest.capabilities["C4"].enabled is False  # Missing verified insulation class


def test_missing_ambient_prevents_c3() -> None:
    """Missing ambient temperature degrades C3 to C2 even with promoted model."""
    obs = {
        "apparent_power": _make_measurement("apparent_power", 50.0, "kVA"),
        "top_oil_temperature": _make_measurement("top_oil_temperature", 60.0, "Cel"),
        # Ambient temperature missing
    }
    state = _make_twin_state(obs, model_status="PROMOTED")
    manifest = evaluate_capabilities(state, model_version="1.0.0", is_model_promoted=True)

    assert manifest.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE
    assert manifest.capabilities["C3"].enabled is False
    assert "MISSING_AMBIENT_TEMPERATURE" in manifest.capabilities["C3"].disabled_reason_codes


def test_c4_requires_verified_insulation_and_hotspot() -> None:
    """C4 requires C3 + verified insulation class + hot-spot support."""
    obs = {
        "apparent_power": _make_measurement("apparent_power", 50.0, "kVA"),
        "top_oil_temperature": _make_measurement("top_oil_temperature", 60.0, "Cel"),
        "ambient_temperature": _make_measurement("ambient_temperature", 28.0, "Cel"),
    }
    state = _make_twin_state(obs, model_status="PROMOTED", is_ageing_enabled=True)

    # 1. Unverified profile -> C4 disabled
    unverified_profile = AssetProfile(
        asset_id="DT-001",
        insulation_paper_class=InsulationClass.THERMALLY_UPGRADED,
        profile_status=ProfileVerificationStatus.UNVERIFIED,
    )
    manifest1 = evaluate_capabilities(
        state,
        profile=unverified_profile,
        model_version="1.0.0",
        is_model_promoted=True,
        hotspot_supported=True,
    )
    assert manifest1.highest_tier == CapabilityTier.C3_THERMAL_PREDICTIVE
    assert manifest1.capabilities["C4"].enabled is False
    assert "MISSING_VERIFIED_INSULATION_CLASS" in manifest1.capabilities["C4"].disabled_reason_codes

    # 2. Verified profile and hotspot support -> C4 enabled
    verified_profile = AssetProfile(
        asset_id="DT-001",
        insulation_paper_class=InsulationClass.THERMALLY_UPGRADED,
        profile_status=ProfileVerificationStatus.VERIFIED,
        fields={
            "insulation_paper_class": ProfileField(
                value="THERMALLY_UPGRADED",
                source_document="Nameplate_Report.pdf",
                status=ProfileVerificationStatus.VERIFIED,
            )
        },
    )
    manifest2 = evaluate_capabilities(
        state,
        profile=verified_profile,
        model_version="1.0.0",
        is_model_promoted=True,
        hotspot_supported=True,
    )
    assert manifest2.highest_tier == CapabilityTier.C4_THERMAL_EXPOSURE
    assert manifest2.capabilities["C4"].enabled is True
    assert manifest2.capabilities["C4"].evidence_grade == "A"


def test_deterministic_evaluation() -> None:
    """Repeated evaluation on the same state produces identical manifests."""
    obs = {
        "active_power": _make_measurement("active_power", 40.0, "kW"),
        "reactive_power": _make_measurement("reactive_power", 10.0, "kvar"),
        "top_oil_temperature": _make_measurement("top_oil_temperature", 55.0, "Cel"),
    }
    state = _make_twin_state(obs)
    evaluator = CapabilityEvaluator()

    m1 = evaluator.evaluate(state)
    m2 = evaluator.evaluate(state)

    assert m1.model_dump() == m2.model_dump()


def test_tripura_adapter_end_to_end_capability_integration() -> None:
    """Verify dynamic capability evaluation on live Tripura adapter stream."""
    adapter = TripuraCSVAdapter()
    reducer = TwinReducer()
    evaluator = CapabilityEvaluator()

    # Create synthetic raw rows mimicking Tripura Overview + TotalPower + CurrentVoltage
    records = [
        {"DeviceTimeStamp": "2026-10-01T00:00", "OTI": "58.0", "ATI": "25.0", "WTI": "0"},
        {"DeviceTimeStamp": "2026-10-01T00:00", "KW": "45.2", "KVAR": "15.1", "KVA": "47.6"},
        {"DeviceTimeStamp": "2026-10-01T00:00", "IL1": "62.0", "IL2": "63.0", "IL3": "61.5", "VL1": "230.0", "VL2": "230.5", "VL3": "229.8"},
    ]

    events = [adapter.transform_record(r, asset_id="TRIPURA-DT-01") for r in records]
    state: TwinState | None = None
    for ev in events:
        state = reducer.reduce(state, ev)

    assert state is not None
    manifest = evaluator.evaluate(state)

    # In unpromoted state, Tripura stream attains C2 (Descriptive Thermal)
    assert manifest.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE
    assert manifest.capabilities["C0"].enabled is True
    assert manifest.capabilities["C1"].enabled is True
    assert manifest.capabilities["C2"].enabled is True
    assert manifest.capabilities["current_imbalance"].enabled is True
    assert manifest.capabilities["voltage_imbalance"].enabled is True
    assert manifest.capabilities["C3"].enabled is False  # Model unpromoted
    assert "MODEL_NOT_PROMOTED" in manifest.capabilities["C3"].disabled_reason_codes
