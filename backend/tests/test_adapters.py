"""Unit tests for Phase 2, Substep 2.1 — Canonical Source Adapters."""

from pathlib import Path
import json
import pytest

from app.adapters.tripura import TripuraCSVAdapter
from app.adapters.cpri_mock import CPRIMockAdapter
from app.models.telemetry import CanonicalEvent, QualitySeverity
from app.core.units import validate_unit


@pytest.fixture
def mapping_file() -> Path:
    p = Path("backend/app/adapters/tripura_map.yaml")
    assert p.exists()
    return p


@pytest.fixture
def cpri_fixture_path() -> Path:
    p = Path("fixtures/cpri_mock_stream.json")
    assert p.exists()
    return p


def test_tripura_adapter_transform_record(mapping_file: Path) -> None:
    adapter = TripuraCSVAdapter(mapping_file=mapping_file)

    sample_raw = {
        "DeviceTimeStamp": "2019-06-27T10:51",
        "VL1": 238.4,
        "VL2": 238.5,
        "VL3": 238.5,
        "IL1": 65.2,
        "IL2": 52.0,
        "IL3": 78.4,
        "INUT": 22.1,
        "OTI": 38.0,
        "ATI": 28.0,
        "WTI": 0.0,
        "OLI": 75.0,
        "KW": 45.2,
        "KVA": 46.1,
        "FRQ": 50.01,
    }

    event = adapter.transform_record(
        raw_record=sample_raw,
        asset_id="TRIPURA_DTR_01",
        source_uri="data/tripura_raw/merged.csv",
        source_record_id="row_101",
    )

    assert isinstance(event, CanonicalEvent)
    assert event.asset_id == "TRIPURA_DTR_01"
    assert event.event_time_utc.isoformat().startswith("2019-06-27T10:51:00")
    assert event.source.system == "tripura_csv"
    assert event.source.adapter_id == "tripura_csv_v1"
    assert event.source.source_record_id == "row_101"
    assert len(event.source.raw_sha256) == 64

    # Check signal mapping and units
    meas_map = {m.signal_id: m for m in event.measurements}
    assert "voltage_v1" in meas_map
    assert meas_map["voltage_v1"].value == 238.4
    assert meas_map["voltage_v1"].unit_ucum == "V"
    assert meas_map["voltage_v1"].phase == "L1"

    assert "neutral_current" in meas_map
    assert meas_map["neutral_current"].value == 22.1
    assert meas_map["neutral_current"].phase == "N"

    assert "top_oil_temperature" in meas_map
    assert meas_map["top_oil_temperature"].value == 38.0
    assert meas_map["top_oil_temperature"].unit_ucum == "Cel"

    # WTI must be discrete alarm contact, not continuous temp
    assert "winding_temp_alarm_contact" in meas_map
    assert meas_map["winding_temp_alarm_contact"].value == 0
    assert meas_map["winding_temp_alarm_contact"].value_type == "int"

    # Validate all measurement units against Pint
    for m in event.measurements:
        if m.unit_ucum not in ("1", "%"):
            assert validate_unit(m.unit_ucum) is True


def test_tripura_adapter_determinism(mapping_file: Path) -> None:
    adapter = TripuraCSVAdapter(mapping_file=mapping_file)
    sample_raw = {
        "DeviceTimeStamp": "2019-07-01T12:00",
        "VL1": 240.0,
        "IL1": 70.0,
        "OTI": 42.0,
        "ATI": 30.0,
    }

    evt1 = adapter.transform_record(sample_raw, "TX_01", "uri1", "1")
    evt2 = adapter.transform_record(sample_raw, "TX_01", "uri1", "1")

    assert evt1.event_id == evt2.event_id
    assert evt1.source.raw_sha256 == evt2.source.raw_sha256
    assert evt1.model_dump_json() == evt2.model_dump_json()


def test_cpri_mock_adapter_transform(cpri_fixture_path: Path) -> None:
    adapter = CPRIMockAdapter()
    events = list(adapter.stream_events(cpri_fixture_path, asset_id="CPRI_MOCK_TX_01"))

    assert len(events) == 3
    for evt in events:
        assert isinstance(evt, CanonicalEvent)
        assert evt.asset_id == "CPRI_MOCK_TX_01"
        assert evt.source.system == "cpri_mock"

        meas_map = {m.signal_id: m for m in evt.measurements}
        assert "voltage_v1" in meas_map
        assert "current_i1" in meas_map
        assert "top_oil_temperature" in meas_map
        assert "ambient_temperature" in meas_map
        assert "active_power_total" in meas_map
        assert "frequency" in meas_map

        assert meas_map["voltage_v1"].unit_ucum == "V"
        assert meas_map["top_oil_temperature"].unit_ucum == "Cel"
        assert meas_map["active_power_total"].unit_ucum == "kW"


def test_adapter_schema_uniformity(mapping_file: Path, cpri_fixture_path: Path) -> None:
    tripura_adapter = TripuraCSVAdapter(mapping_file=mapping_file)
    cpri_adapter = CPRIMockAdapter()

    tripura_raw = {
        "DeviceTimeStamp": "2020-01-01T10:00",
        "VL1": 230.5,
        "IL1": 45.2,
        "OTI": 42.5,
        "ATI": 26.0,
        "KW": 31.2,
    }

    cpri_raw = {
        "timestamp": "2020-01-01T10:00:00Z",
        "v_r": 230.5,
        "i_r": 45.2,
        "top_oil_degc": 42.5,
        "ambient_degc": 26.0,
        "active_kw": 31.2,
    }

    t_evt = tripura_adapter.transform_record(tripura_raw, "TX_UNIFORM")
    c_evt = cpri_adapter.transform_record(cpri_raw, "TX_UNIFORM")

    # Downstream sees identical canonical signal names
    t_signals = {m.signal_id for m in t_evt.measurements}
    c_signals = {m.signal_id for m in c_evt.measurements}

    common_core = {"voltage_v1", "current_i1", "top_oil_temperature", "ambient_temperature", "active_power_total"}
    assert common_core.issubset(t_signals)
    assert common_core.issubset(c_signals)
