"""Regression tests for the live API runtime wiring (reducer engines, CPRI replay, replay restart)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import build_runtime_reducer
from app.api.routers.replay import ensure_dataset_loaded
from app.adapters.cpri_v3 import ORACLE_COLUMNS
from app.core.config import Settings
from app.core.storage import StorageEngine
from app.engine.replay import ReplayEngine
from app.main import create_app
from app.models.thermal_artifact import QualificationStatus

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CAL_START_UTC = datetime(2024, 12, 31, 18, 30, tzinfo=timezone.utc)  # 2025-01-01 00:00 +05:30
CAL_END_UTC = datetime(2025, 7, 2, 18, 30, tzinfo=timezone.utc)  # 2025-07-03 00:00 +05:30


@pytest.fixture
def at_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(PROJECT_ROOT)


def _load_events(asset_id: str) -> list:
    storage = StorageEngine(db_path=":memory:")
    replay = ReplayEngine(storage=storage, asset_id=asset_id)
    ensure_dataset_loaded(storage, replay, asset_id)
    return replay._events


def test_runtime_reducer_wires_all_engines_with_gated_cpri_qualification(at_repo_root: None) -> None:
    reducer = build_runtime_reducer(Settings(default_asset_id="TX_250_MIX"))
    for engine in ("episode_engine", "anomaly_engine", "othi_engine", "exposure_engine", "maintenance_engine", "thermal_gate", "review_engine"):
        assert getattr(reducer, engine) is not None, engine
    assert reducer.thermal_gate.is_model_promoted is False
    assert reducer.anomaly_engine.qualification.residual_anomaly_qualification == QualificationStatus.NOT_QUALIFIED
    assert reducer.profile.fields["load_reference_kva"].value == 250.0


def test_cpri_replay_uses_cal_partition_only_without_oracle_labels(at_repo_root: None) -> None:
    events = _load_events("TX_250_MIX")
    assert len(events) == 8757
    assert all(CAL_START_UTC <= ev.event_time_utc < CAL_END_UTC for ev in events)
    oracle = set(ORACLE_COLUMNS)
    for ev in events[:500]:
        assert ev.asset_id == "TX_250_MIX"
        for m in ev.measurements:
            assert not m.signal_id.startswith("y_") and m.signal_id not in oracle


def test_declared_rating_is_not_flagged_as_frozen_sensor(at_repo_root: None) -> None:
    events = _load_events("TX_250_MIX")[:50]
    reducer = build_runtime_reducer(Settings(default_asset_id="TX_250_MIX"))
    state = None
    for ev in events:
        state = reducer.reduce(state, ev)
        assert not any("_plaus_stuck_rated_kva_" in e.evidence_id for e in reducer.latest_emitted_evidence)


def test_tripura_runtime_reducer_runs_with_open_phase_episodes(at_repo_root: None) -> None:
    """Review superseding must handle PHASE_OR_NEUTRAL episodes (previously AttributeError)."""
    events = _load_events("DT-TRIPURA-001")[:300]
    reducer = build_runtime_reducer(Settings(default_asset_id="DT-TRIPURA-001"))
    state = None
    for ev in events:
        state = reducer.reduce(state, ev)
    assert state is not None and state.health_bundle is not None


def test_live_app_reports_computed_health_and_restarts_cleanly(at_repo_root: None) -> None:
    app = create_app(settings=Settings(default_asset_id="TX_250_MIX"))
    with TestClient(app) as client:
        assert client.post("/v1/replay", json={"action": "start", "asset_id": "TX_250_MIX"}).status_code == 200
        first_reducer = app.state.app_state.reducer
        assert client.post("/v1/replay", json={"action": "step", "batch_size": 50, "asset_id": "TX_250_MIX"}).status_code == 200

        health = client.get("/v1/assets/TX_250_MIX/health").json()
        details = [d.get("details") or "" for d in health["domains"].values()]
        assert not any("uninitialized" in d for d in details)

        card = client.get("/v1/assets/TX_250_MIX/model-card").json()
        assert card["promotion"]["status"] == "NOT_PROMOTED"
        scenario = client.post("/v1/assets/TX_250_MIX/scenario", json={"load_multiplier": 1.2}).json()
        assert scenario["is_enabled"] is False

        assert client.post("/v1/replay", json={"action": "start", "asset_id": "TX_250_MIX"}).status_code == 200
        assert app.state.app_state.reducer is not first_reducer
