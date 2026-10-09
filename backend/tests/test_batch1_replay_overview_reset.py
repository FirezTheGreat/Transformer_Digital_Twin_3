"""Regression tests for Batch 1: Dynamic Replay Timeline, Rolling History, and Reset Correctness."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.api.schemas import HistoryResponse, ReplayStatusResponse, AssetStateResponse
from app.core.config import Settings
from app.main import create_app
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


def make_sample_canonical_event(
    asset_id: str = "DT-TRIPURA-001",
    event_id: str = "evt-001",
    timestamp: datetime | None = None,
    val: float = 65.5,
) -> CanonicalEvent:
    ts = timestamp or datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
    return CanonicalEvent(
        schema_version="1.0.0",
        mapping_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=ts,
        received_time_utc=ts,
        source=SourceRef(
            system="tripura_csv",
            adapter_id="tripura_csv_adapter",
            source_record_id=f"rec-{event_id}",
            source_uri="file:///test_data.csv",
            raw_sha256="sha256_mock_raw_hash",
        ),
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                value=val,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value=str(val),
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="ambient_temperature",
                value=30.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="ATI",
                original_value="30.0",
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="current_l1",
                phase="L1",
                value=50.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_L1",
                original_value="50.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="voltage_l1",
                phase="L1",
                value=230.0,
                value_type="float",
                unit_ucum="V",
                original_name="V_L1",
                original_value="230.0",
                original_unit="V",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
        ],
    )


@pytest.fixture
def client() -> TestClient:
    test_settings = Settings(
        app_name="Test Transformer Digital Twin API",
        app_version="1.0.0-test",
        api_v1_prefix="/v1",
        environment="test",
        default_asset_id="DT-TRIPURA-001",
        db_path=":memory:",
    )
    app = create_app(settings=test_settings)
    with TestClient(app) as test_client:
        yield test_client


def test_history_window_advances_beyond_50_frames_with_order_asc_param(client: TestClient) -> None:
    """Verify that querying history with order_asc=False returns the latest rolling 50 frames rather than getting stuck on the first 50."""
    t0 = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    events = [
        make_sample_canonical_event(
            event_id=f"evt-{i:03d}",
            timestamp=t0 + timedelta(minutes=15 * i),
            val=50.0 + (i * 0.5),
        )
        for i in range(75)
    ]

    # Ingest all 75 events
    payload = {"events": [e.model_dump(mode="json") for e in events]}
    resp = client.post("/v1/telemetry", json=payload)
    assert resp.status_code == 201

    # 1. Default order_asc=True returns oldest 50 frames (0 to 49)
    resp_asc = client.get(
        "/v1/assets/DT-TRIPURA-001/history",
        params={"limit": 50, "order_asc": True},
    )
    assert resp_asc.status_code == 200
    data_asc = resp_asc.json()
    assert len(data_asc["events"]) == 50
    assert data_asc["events"][0]["event_id"] == "evt-000"
    assert data_asc["events"][-1]["event_id"] == "evt-049"

    # 2. Latest rolling window: order_asc=False returns newest 50 frames (74 down to 25)
    end_time_dt = events[-1].event_time_utc
    resp_desc = client.get(
        "/v1/assets/DT-TRIPURA-001/history",
        params={"limit": 50, "order_asc": False, "end_time": end_time_dt.isoformat()},
    )
    assert resp_desc.status_code == 200
    data_desc = resp_desc.json()
    assert len(data_desc["events"]) == 50
    assert data_desc["events"][0]["event_id"] == "evt-074"
    assert data_desc["events"][-1]["event_id"] == "evt-025"

    # In the frontend, these 50 frames are sorted ascending for the chart X-axis:
    frontend_sorted = sorted(data_desc["events"], key=lambda e: e["event_time_utc"])
    assert frontend_sorted[0]["event_id"] == "evt-025"
    assert frontend_sorted[-1]["event_id"] == "evt-074"


def test_replay_seek_backward_and_forward(client: TestClient) -> None:
    """Verify that seeking backward reconstructs deterministic state and FactBundle without erasing telemetry."""
    t0 = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    events = [
        make_sample_canonical_event(
            event_id=f"evt-{i:03d}",
            timestamp=t0 + timedelta(minutes=15 * i),
            val=50.0 + (i * 2.0),
        )
        for i in range(10)
    ]
    payload = {"events": [e.model_dump(mode="json") for e in events]}
    resp = client.post("/v1/telemetry", json=payload)
    assert resp.status_code == 201

    # Reset replay state so we start cleanly from cursor 0
    client.post("/v1/replay", json={"action": "reset"})

    # Step 5 times
    for _ in range(5):
        resp_step = client.post("/v1/replay", json={"action": "step", "batch_size": 1})
        assert resp_step.status_code == 200

    status = client.get("/v1/replay").json()
    assert status["processed_events"] == 5

    state5_resp = client.get("/v1/assets/DT-TRIPURA-001/state")
    assert state5_resp.status_code == 200
    state5 = state5_resp.json()
    assert state5["twin_state"]["state_sequence"] == 5
    assert state5["twin_state"]["current_observations"]["top_oil_temperature"]["value"] == pytest.approx(50.0 + (4 * 2.0))

    # Seek backward to 3 (stepping backward)
    resp_seek = client.post("/v1/replay", json={"action": "seek", "seek_position": 3})
    assert resp_seek.status_code == 200
    status_seek = client.get("/v1/replay").json()
    assert status_seek["processed_events"] == 3

    state3_resp = client.get("/v1/assets/DT-TRIPURA-001/state")
    assert state3_resp.status_code == 200
    state3 = state3_resp.json()
    assert state3["twin_state"]["state_sequence"] == 3
    assert state3["twin_state"]["current_observations"]["top_oil_temperature"]["value"] == pytest.approx(50.0 + (2 * 2.0))

    # All events are still present in DuckDB history (no data purge on backward navigation)
    hist = client.get("/v1/assets/DT-TRIPURA-001/history", params={"limit": 20}).json()
    assert len(hist["events"]) == 10


def test_replay_reset_clears_transient_state_preserves_database(client: TestClient) -> None:
    """Verify reset clears runtime twin state and facts but does not purge persisted telemetry."""
    t0 = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    events = [
        make_sample_canonical_event(
            event_id=f"evt-{i:03d}",
            timestamp=t0 + timedelta(minutes=15 * i),
            val=50.0 + i,
        )
        for i in range(5)
    ]
    payload = {"events": [e.model_dump(mode="json") for e in events]}
    client.post("/v1/telemetry", json=payload)

    # Step twice
    client.post("/v1/replay", json={"action": "step", "batch_size": 1})
    client.post("/v1/replay", json={"action": "step", "batch_size": 1})

    status = client.get("/v1/replay").json()
    assert status["processed_events"] == 2

    # Issue reset
    resp_reset = client.post("/v1/replay", json={"action": "reset"})
    assert resp_reset.status_code == 200

    # Replay progress is reset
    status_after = client.get("/v1/replay").json()
    assert status_after["processed_events"] == 0
    assert status_after["status"] == "reset"

    # Twin active state sequence is reset to 0 (baseline state with no observations)
    state_after = client.get("/v1/assets/DT-TRIPURA-001/state").json()
    assert state_after["twin_state"]["state_sequence"] == 0
    assert state_after["twin_state"]["current_observations"] == {}

    # DuckDB storage retains all 5 persisted events
    hist_after = client.get("/v1/assets/DT-TRIPURA-001/history", params={"limit": 10}).json()
    assert len(hist_after["events"]) == 5
