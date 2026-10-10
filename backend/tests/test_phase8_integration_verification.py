"""Focused verification tests for Phase 8 integration fixes across replay lifecycle,
dataset/asset switching, fault injection propagation, and checkpoint reporting.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_replay_lifecycle_and_switching(client: TestClient):
    """Test Workstream 1: Replay lifecycle and dataset/asset switching sequence."""
    # 1. Reset and load CPRI Baseline
    resp = client.post("/v1/replay", json={"action": "reset", "asset_id": "TX_1000_COMM"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("reset", "idle")
    assert data["processed_events"] == 0
    assert not data["is_completed"]

    # 2. Step one frame on CPRI
    step_resp = client.post("/v1/replay", json={"action": "step", "asset_id": "TX_1000_COMM", "batch_size": 1})
    assert step_resp.status_code == 200
    step_data = step_resp.json()
    assert step_data["processed_events"] == 1
    assert step_data["current_time_utc"] is not None
    cpri_watermark = step_data["current_time_utc"]

    # Verify state endpoint returns TX_1000_COMM
    state_resp = client.get("/v1/assets/TX_1000_COMM/state")
    assert state_resp.status_code == 200
    state_data = state_resp.json()
    assert state_data["asset_id"] == "TX_1000_COMM"

    # 3. Switch to GridPulse Candidate (DT-01)
    switch_resp = client.post("/v1/replay", json={"action": "reset", "asset_id": "DT-01"})
    assert switch_resp.status_code == 200
    switch_data = switch_resp.json()
    assert switch_data["processed_events"] == 0
    assert not switch_data["is_completed"]

    # Verify state isolation: state for DT-01 should be fresh, not carry TX_1000_COMM
    dt_state_resp = client.get("/v1/assets/DT-01/state")
    assert dt_state_resp.status_code == 200
    dt_state = dt_state_resp.json()
    assert dt_state["asset_id"] == "DT-01"

    # 4. Step frame on DT-01
    dt_step_resp = client.post("/v1/replay", json={"action": "step", "asset_id": "DT-01", "batch_size": 1})
    assert dt_step_resp.status_code == 200
    dt_step_data = dt_step_resp.json()
    assert dt_step_data["processed_events"] == 1
    assert dt_step_data["current_time_utc"] != cpri_watermark


def test_fault_injection_and_telemetry_propagation(client: TestClient):
    """Test Workstream 2: Fault injection pipeline and telemetry consistency."""
    # Ensure DT-01 is loaded
    client.post("/v1/replay", json={"action": "reset", "asset_id": "DT-01"})
    client.post("/v1/replay", json={"action": "step", "asset_id": "DT-01", "batch_size": 1})

    # Ingest trip event conforming strictly to CanonicalEvent & Measurement contracts
    trip_event = {
        "schema_version": "1.0.0",
        "event_id": "evt-verify-trip-001",
        "asset_id": "DT-01",
        "event_time_utc": "2026-01-01T12:00:00Z",
        "source": {
            "system": "protection_relay",
            "adapter_id": "trip_adapter",
            "source_record_id": "rec_trip_1",
            "source_uri": "fixtures/test.json",
            "raw_sha256": "4444555566667777888899990000111122223333444455556666777788889999",
        },
        "measurements": [
            {
                "signal_id": "oil_temp_trip_flag",
                "value": True,
                "value_type": "bool",
                "unit_ucum": "1",
                "original_name": "OTI_T",
                "original_value": "1",
                "original_unit": "flag",
                "quality": {"severity": "BAD", "flags": ["DIRECT_TRIP"]},
            },
            {
                "signal_id": "current_i1",
                "value": 0.0,
                "value_type": "float",
                "unit_ucum": "A",
                "original_name": "I_R",
                "original_value": "0.0",
                "original_unit": "A",
                "quality": {"severity": "GOOD", "flags": []},
            },
            {
                "signal_id": "current_i2",
                "value": 0.0,
                "value_type": "float",
                "unit_ucum": "A",
                "original_name": "I_Y",
                "original_value": "0.0",
                "original_unit": "A",
                "quality": {"severity": "GOOD", "flags": []},
            },
            {
                "signal_id": "current_i3",
                "value": 0.0,
                "value_type": "float",
                "unit_ucum": "A",
                "original_name": "I_B",
                "original_value": "0.0",
                "original_unit": "A",
                "quality": {"severity": "GOOD", "flags": []},
            },
            {
                "signal_id": "lv_breaker_closed",
                "value": False,
                "value_type": "bool",
                "unit_ucum": "1",
                "original_name": "52A",
                "original_value": "0",
                "original_unit": "binary",
                "quality": {"severity": "GOOD", "flags": ["BREAKER_TRIPPED"]},
            },
        ],
        "event_quality_flags": ["PROTECTION_TRIP_ACTIVE"],
        "mapping_version": "1.0.0",
    }

    ingest_resp = client.post("/v1/telemetry", json={"asset_id": "DT-01", "events": [trip_event]})
    assert ingest_resp.status_code in (200, 201)

    # Check that OTHI is 0 (Critical) due to decisive direct trip
    state_resp = client.get("/v1/assets/DT-01/state")
    assert state_resp.status_code == 200
    state_data = state_resp.json()
    health = state_data["fact_bundle"]["health"]
    assert health["othi_score"] == 0
    assert health["status"] == "CRITICAL"


def test_reports_and_checkpoints(client: TestClient):
    """Test Workstream 3 & 4: Checkpoint persistence and export endpoints."""
    # Create on-demand checkpoint
    chk_resp = client.post("/v1/reports/checkpoints?asset_id=DT-01")
    assert chk_resp.status_code == 201
    chk_data = chk_resp.json()
    cid = chk_data["checkpoint_id"]
    assert cid.startswith("chk_DT-01")

    # Verify JSON export for checkpoint
    json_resp = client.get(f"/v1/reports/summary.json?asset_id=DT-01&checkpoint_id={cid}")
    assert json_resp.status_code == 200
    assert json_resp.headers["content-type"].startswith("application/json")

    # Verify CSV export for checkpoint
    csv_resp = client.get(f"/v1/reports/summary.csv?asset_id=DT-01&checkpoint_id={cid}")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]

    # Verify PDF export for checkpoint
    pdf_resp = client.get(f"/v1/reports/summary.pdf?asset_id=DT-01&checkpoint_id={cid}")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert len(pdf_resp.content) > 1000
