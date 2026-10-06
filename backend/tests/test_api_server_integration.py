"""Phase 7.4 — Complete FastAPI Server Integration & OpenAPI Contract Tests.

Validates:
- Application startup and lifespan initialization
- Health probe endpoints (/healthz and /v1/healthz)
- OpenAPI schema generation and Swagger UI (/docs, /redoc, /openapi.json)
- UI-honesty metadata presence (DEMO_DEFAULT, relative_load_index, SYNTHETIC_SCENARIO)
- Registration and routing for all canonical REST API endpoints
- CORS middleware configuration
- Centralized exception handlers and error JSON envelope consistency
"""

from __future__ import annotations

from typing import Generator
import pytest
from fastapi.testclient import TestClient

from app.api.deps import AppState, build_default_model_artifact
from app.core.config import Settings
from app.core.storage import StorageEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.feedback import OperatorFeedbackLedger
from app.engine.reducer import TwinReducer
from app.engine.replay import ReplayEngine
from app.engine.scenario_simulator import ScenarioSimulator
from app.main import create_app


@pytest.fixture
def mock_storage(tmp_path) -> StorageEngine:
    db_file = tmp_path / "test_api_server.db"
    storage = StorageEngine(db_path=str(db_file))
    yield storage
    storage.close()


@pytest.fixture
def test_app_state(mock_storage: StorageEngine) -> AppState:
    settings = Settings(
        app_name="Digital Twin Server Test",
        app_version="1.0.0",
        environment="test",
        db_path=":memory:",
        default_asset_id="DT-TRIPURA-001",
        cors_origins=["http://localhost:3000", "http://localhost:5173"],
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


def test_healthz_root_endpoint(client: TestClient) -> None:
    """GET /healthz returns 200 OK with system readiness diagnostics."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "ok"
    assert data["app_name"] == "Digital Twin Server Test"
    assert data["version"] == "1.0.0"
    assert data["environment"] == "test"
    assert data["default_asset_id"] == "DT-TRIPURA-001"
    assert data["is_ready"] is True
    assert data["details"]["storage_connected"] is True
    assert data["details"]["reducer_initialized"] is True
    assert data["details"]["capability_evaluator_initialized"] is True


def test_swagger_and_redoc_endpoints(client: TestClient) -> None:
    """Swagger UI (/docs) and ReDoc (/redoc) serve HTTP 200 HTML content."""
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200
    assert "swagger-ui" in docs_resp.text.lower() or "html" in docs_resp.text.lower()

    redoc_resp = client.get("/redoc")
    assert redoc_resp.status_code == 200
    assert "redoc" in redoc_resp.text.lower() or "html" in redoc_resp.text.lower()


def test_openapi_schema_honesty_tags_and_routes(client: TestClient) -> None:
    """OpenAPI schema contains all UI-honesty metadata and all canonical routes."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()

    # 1. Info and description honesty guarantees
    desc = schema["info"]["description"]
    assert "DEMO_DEFAULT" in desc
    assert "relative_load_index" in desc
    assert "SYNTHETIC_SCENARIO" in desc

    # 2. Tag definitions
    tags = {t["name"]: t["description"] for t in schema.get("tags", [])}
    assert "Telemetry" in tags
    assert "relative_load_index" in tags["Telemetry"]
    assert "Analytics & Scenarios" in tags
    assert "DEMO_DEFAULT" in tags["Analytics & Scenarios"]
    assert "SYNTHETIC_SCENARIO" in tags["Analytics & Scenarios"]

    # 3. Canonical Route Registration Verification
    paths = schema["paths"]

    # Telemetry
    assert "/v1/telemetry" in paths
    assert "post" in paths["/v1/telemetry"]

    # Replay
    assert "/v1/replay" in paths
    assert "post" in paths["/v1/replay"]

    # Asset state, history & capabilities
    assert "/v1/assets/{asset_id}/state" in paths
    assert "get" in paths["/v1/assets/{asset_id}/state"]
    assert "/v1/assets/{asset_id}/history" in paths
    assert "get" in paths["/v1/assets/{asset_id}/history"]
    assert "/v1/assets/{asset_id}/capabilities" in paths
    assert "get" in paths["/v1/assets/{asset_id}/capabilities"]

    # Analytics: health, episodes, recommendations, model card & scenario
    assert "/v1/assets/{asset_id}/health" in paths
    assert "get" in paths["/v1/assets/{asset_id}/health"]
    assert "/v1/assets/{asset_id}/episodes" in paths
    assert "get" in paths["/v1/assets/{asset_id}/episodes"]
    assert "/v1/assets/{asset_id}/recommendations" in paths
    assert "get" in paths["/v1/assets/{asset_id}/recommendations"]
    assert "/v1/assets/{asset_id}/model-card" in paths
    assert "get" in paths["/v1/assets/{asset_id}/model-card"]
    assert "/v1/assets/{asset_id}/scenario" in paths
    assert "post" in paths["/v1/assets/{asset_id}/scenario"]

    # Feedback
    assert "/v1/feedback" in paths
    assert "post" in paths["/v1/feedback"]

    # Root Infrastructure Health probe
    assert "/healthz" in paths



def test_cors_middleware_headers(client: TestClient) -> None:
    """CORS middleware emits expected access-control response headers."""
    resp = client.get("/healthz", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_centralized_error_handling_envelopes(client: TestClient) -> None:
    """Standardized JSON error envelope is returned across all failure modes."""
    # 1. 404 Route Not Found
    resp_404 = client.get("/v1/unknown-route")
    assert resp_404.status_code == 404
    body_404 = resp_404.json()
    assert "error" in body_404
    assert body_404["error"]["code"] == "NOT_FOUND"

    # 2. 422 Unprocessable Content on malformed telemetry payload
    resp_422 = client.post("/v1/telemetry", json={"invalid_field": 123})
    assert resp_422.status_code == 422
    body_422 = resp_422.json()
    assert "error" in body_422
    assert "code" in body_422["error"]
    assert "message" in body_422["error"]
    assert "timestamp_utc" in body_422["error"]
