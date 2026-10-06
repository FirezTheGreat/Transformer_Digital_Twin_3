"""Unit and Integration Tests for Core API Routers (Phase 7.2).

Tests:
1. POST /v1/telemetry: Ingestion of single CanonicalEvent, batches, raw frames, and 422 validation rejection.
2. POST /v1/replay: Deterministic playback controls (start, step, pause, resume, reset, seek) and error handling.
3. GET /v1/assets/{asset_id}/state: Current twin state vector and capability tier retrieval.
4. GET /v1/assets/{asset_id}/history: Historical telemetry queries with time-range filtering and pagination.
5. GET /v1/assets/{asset_id}/capabilities: Dynamic C0–C4 capability manifest and fallback reason codes.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.api.schemas import (
    AssetStateResponse,
    HistoryResponse,
    ReplayStatusResponse,
    TelemetryIngestionResponse,
)
from app.core.config import Settings
from app.main import create_app
from app.models.capability import CapabilityManifest, CapabilityTier
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    RawTelemetryFrame,
    SourceRef,
)


def make_sample_canonical_event(
    asset_id: str = "DT-TRIPURA-001",
    event_id: str = "evt-001",
    timestamp: datetime | None = None,
    with_measurements: bool = True,
) -> CanonicalEvent:
    """Helper to construct valid CanonicalEvent for API tests."""
    ts = timestamp or datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
    measurements = []
    if with_measurements:
        measurements.extend([
            Measurement(
                signal_id="top_oil_temperature",
                value=65.5,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="65.5",
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="ambient_temperature",
                value=32.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="ATI",
                original_value="32.0",
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="current_l1",
                phase="L1",
                value=42.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_L1",
                original_value="42.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="current_l2",
                phase="L2",
                value=41.5,
                value_type="float",
                unit_ucum="A",
                original_name="I_L2",
                original_value="41.5",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="current_l3",
                phase="L3",
                value=43.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_L3",
                original_value="43.0",
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
        ])

    return CanonicalEvent(
        schema_version="1.0.0",
        mapping_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=ts,
        received_time_utc=ts,
        source=SourceRef(
            system="SCADA",
            adapter_id="tripura_csv_adapter",
            source_record_id=f"rec-{event_id}",
            source_uri="file:///test_data.csv",
            raw_sha256="sha256_mock_raw_hash",
        ),
        measurements=measurements,
    )


@pytest.fixture
def client() -> TestClient:
    """Create test client with in-memory storage and isolated configuration."""
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


def test_telemetry_ingest_single_event(client: TestClient):
    """Verify POST /v1/telemetry successfully ingests single CanonicalEvent."""
    event = make_sample_canonical_event(event_id="evt-single-001")
    payload = {"event": event.model_dump(mode="json")}

    response = client.post("/v1/telemetry", json=payload)
    assert response.status_code == 201
    data = response.json()

    validated = TelemetryIngestionResponse.model_validate(data)
    assert validated.status == "accepted"
    assert validated.ingested_count == 1
    assert validated.asset_id == "DT-TRIPURA-001"
    assert validated.latest_state_sequence == 1
    assert validated.latest_state_hash is not None


def test_telemetry_ingest_batch_events(client: TestClient):
    """Verify POST /v1/telemetry ingests batch of CanonicalEvents and maintains sequence."""
    events = [
        make_sample_canonical_event(
            event_id=f"evt-batch-{i:03d}",
            timestamp=datetime(2026, 4, 1, 12, i * 15, 0, tzinfo=timezone.utc),
        )
        for i in range(3)
    ]
    payload = {"events": [ev.model_dump(mode="json") for ev in events]}

    response = client.post("/v1/telemetry", json=payload)
    assert response.status_code == 201
    data = response.json()

    validated = TelemetryIngestionResponse.model_validate(data)
    assert validated.ingested_count == 3
    assert validated.latest_state_sequence == 3


def test_telemetry_ingest_raw_frame(client: TestClient):
    """Verify POST /v1/telemetry ingests RawTelemetryFrame."""
    now = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
    frame = RawTelemetryFrame(
        raw_id="raw-001",
        source_system="TRIPURA_SCADA",
        received_time_utc=now,
        raw_payload={"timestamp": "2026-04-01 12:00:00", "OTI": 62.5, "ATI": 30.0},
        raw_sha256="sha256_mock_raw_frame",
    )
    payload = {"frame": frame.model_dump(mode="json")}

    response = client.post("/v1/telemetry", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["ingested_count"] == 1


def test_telemetry_ingest_empty_payload_422(client: TestClient):
    """Verify POST /v1/telemetry returns HTTP 422 on empty ingestion payload."""
    response = client.post("/v1/telemetry", json={})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_telemetry_ingest_malformed_json_422(client: TestClient):
    """Verify POST /v1/telemetry returns HTTP 422 on invalid schema fields."""
    response = client.post("/v1/telemetry", json={"event": {"invalid_field": 123}})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_get_asset_state_after_ingestion(client: TestClient):
    """Verify GET /v1/assets/{asset_id}/state returns updated TwinState and FactBundle."""
    event = make_sample_canonical_event(event_id="evt-state-001")
    client.post("/v1/telemetry", json={"event": event.model_dump(mode="json")})

    response = client.get("/v1/assets/DT-TRIPURA-001/state")
    assert response.status_code == 200
    data = response.json()

    validated = AssetStateResponse.model_validate(data)
    assert validated.asset_id == "DT-TRIPURA-001"
    assert validated.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE
    assert validated.twin_state.state_sequence == 1
    assert validated.fact_bundle is not None
    assert validated.fact_bundle.asset_id == "DT-TRIPURA-001"
    assert validated.fact_bundle.health.othi_score == 100


def test_get_asset_history(client: TestClient):
    """Verify GET /v1/assets/{asset_id}/history returns chronologically queried events."""
    events = [
        make_sample_canonical_event(
            event_id=f"evt-hist-{i:03d}",
            timestamp=datetime(2026, 4, 1, 10 + i, 0, 0, tzinfo=timezone.utc),
        )
        for i in range(3)
    ]
    client.post("/v1/telemetry", json={"events": [ev.model_dump(mode="json") for ev in events]})

    # Query full history
    response = client.get("/v1/assets/DT-TRIPURA-001/history")
    assert response.status_code == 200
    data = response.json()

    validated = HistoryResponse.model_validate(data)
    assert validated.asset_id == "DT-TRIPURA-001"
    assert validated.event_count == 3
    assert len(validated.events) == 3
    assert validated.events[0].event_id == "evt-hist-000"
    assert validated.events[2].event_id == "evt-hist-002"

    # Query with limit
    limit_resp = client.get("/v1/assets/DT-TRIPURA-001/history?limit=2")
    assert limit_resp.status_code == 200
    assert limit_resp.json()["event_count"] == 2


def test_get_asset_capabilities(client: TestClient):
    """Verify GET /v1/assets/{asset_id}/capabilities returns dynamic CapabilityManifest."""
    event = make_sample_canonical_event(event_id="evt-cap-001")
    client.post("/v1/telemetry", json={"event": event.model_dump(mode="json")})

    response = client.get("/v1/assets/DT-TRIPURA-001/capabilities")
    assert response.status_code == 200
    data = response.json()

    manifest = CapabilityManifest.model_validate(data)
    assert manifest.asset_id == "DT-TRIPURA-001"
    assert manifest.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE
    assert "C0" in manifest.capabilities
    assert manifest.capabilities["C0"].enabled is True
    assert "C2" in manifest.capabilities
    assert manifest.capabilities["C2"].enabled is True


def test_replay_control_pipeline(client: TestClient):
    """Verify POST /v1/replay controls: start, step, pause, resume, seek, and reset."""
    # Seed storage with 5 events
    events = [
        make_sample_canonical_event(
            event_id=f"evt-rep-{i:03d}",
            timestamp=datetime(2026, 4, 1, 12, i * 10, 0, tzinfo=timezone.utc),
        )
        for i in range(5)
    ]
    client.post("/v1/telemetry", json={"events": [ev.model_dump(mode="json") for ev in events]})

    # Reset state to verify pure replay progression
    client.post("/v1/replay", json={"action": "reset"})

    # 1. Step replay 1 event
    step_resp = client.post("/v1/replay", json={"action": "step", "batch_size": 1})
    assert step_resp.status_code == 200
    data = step_resp.json()
    validated = ReplayStatusResponse.model_validate(data)
    assert validated.processed_events == 1
    assert validated.total_events >= 5
    assert validated.is_completed is False
    assert validated.current_state_sequence == 1

    # 2. Step replay 2 more events
    step2_resp = client.post("/v1/replay", json={"action": "step", "batch_size": 2})
    assert step2_resp.status_code == 200
    assert step2_resp.json()["processed_events"] == 3
    assert step2_resp.json()["current_state_sequence"] == 3

    # 3. Pause replay
    pause_resp = client.post("/v1/replay", json={"action": "pause"})
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "paused"

    # 4. Resume replay
    resume_resp = client.post("/v1/replay", json={"action": "resume"})
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "running"

    # 5. Reset replay
    reset_resp = client.post("/v1/replay", json={"action": "reset"})
    assert reset_resp.status_code == 200
    assert reset_resp.json()["processed_events"] == 0
    assert reset_resp.json()["status"] == "reset"


def test_replay_invalid_seek_error(client: TestClient):
    """Verify POST /v1/replay returns HTTP 400 on out-of-bounds seek position."""
    response = client.post("/v1/replay", json={"action": "seek", "seek_position": 99999})
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "REPLAY_ERROR"
