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


def test_cpri_model_evaluation_matrix_matches_runtime_gates(at_repo_root: None) -> None:
    app = create_app(settings=Settings(default_asset_id="TX_250_MIX"))
    with TestClient(app) as client:
        body = client.get("/v1/models/cpri-evaluation").json()
    rows = {r["asset_id"]: r for r in body["assets"]}
    assert len(rows) == 8
    tx = rows["TX_250_MIX"]
    assert tx["promotion_status"] == "NOT_PROMOTED" and tx["test_partition"] == "CONSUMED"
    assert tx["artifact_sha256"] == "05d7c29f22fcb34e6bc2e596479d0e4c48ff468a0a7993d6bc2b87015f9e160f"
    assert tx["gates"]["signed_bias"] is False and tx["metrics"]["signed_bias_degc"] == 0.2599
    for row in rows.values():
        assert row["capabilities"]["anomaly_detection"]["available"] is True
        # Forecasting / what-if only ever available for a promoted model
        if row["promotion_status"] != "PROMOTED":
            assert row["capabilities"]["forecasting"]["available"] is False
            assert row["capabilities"]["what_if"]["available"] is False


@pytest.mark.parametrize("mode", ["--fit-and-freeze", "--evaluate-test"])
def test_calibration_runner_refuses_to_overwrite_or_reconsume(mode: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("run_calibration_cpri", PROJECT_ROOT / "backend" / "scripts" / "run_calibration_cpri.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    processed = PROJECT_ROOT / "data" / "processed"
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in processed.glob("*tx_250_mix*")}

    monkeypatch.setattr(sys, "argv", ["run_calibration_cpri.py", "--asset", "TX_250_MIX", mode])
    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert exc.value.code == 1
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in processed.glob("*tx_250_mix*")} == before


def test_promoted_asset_forecasts_with_its_own_30min_envelope(at_repo_root: None) -> None:
    """A PROMOTED CPRI model unlocks C3/what-if, projecting 4 x 30 min with its own CAL envelope only."""
    import json

    artifact = json.loads((PROJECT_ROOT / "data/processed/calibrated_thermal_model_cpri_tx_1000_comm.json").read_text(encoding="utf-8"))
    own_widths = artifact["conformal_uncertainty"]["horizon_half_widths_degc"]
    app = create_app(settings=Settings(default_asset_id="TX_1000_COMM"))
    with TestClient(app) as client:
        client.post("/v1/replay", json={"action": "start", "asset_id": "TX_1000_COMM"})
        client.post("/v1/replay", json={"action": "seek", "seek_position": 200, "asset_id": "TX_1000_COMM"})
        caps = client.get("/v1/assets/TX_1000_COMM/state").json()["fact_bundle"]["capabilities"]["capabilities"]
        result = client.post("/v1/assets/TX_1000_COMM/scenario", json={"load_multiplier": 1.2}).json()
    assert caps["C3"]["enabled"] is True
    assert result["is_enabled"] is True
    steps = result["trajectory"]
    assert [s["horizon_minutes"] for s in steps] == [30, 60, 90, 120]
    for step, width in zip(steps, own_widths):
        half = (step["conformal_upper_degc"] - step["conformal_lower_degc"]) / 2
        assert half == pytest.approx(width, abs=1e-3)


def test_scenario_without_origin_telemetry_is_refused_not_fabricated(at_repo_root: None) -> None:
    app = create_app(settings=Settings(default_asset_id="TX_1000_COMM"))
    with TestClient(app) as client:
        result = client.post("/v1/assets/TX_1000_COMM/scenario", json={"load_multiplier": 1.2}).json()
    assert result["is_enabled"] is False
    assert "origin telemetry" in result["disabled_reason"]


def test_thermal_gate_receives_load_in_its_fitted_driver_units(at_repo_root: None) -> None:
    from app.engine.reducer import thermal_load_driver_value

    event = _load_events("TX_250_MIX")[0]
    vals = {m.signal_id: float(m.value) for m in event.measurements if isinstance(m.value, (int, float))}
    assert thermal_load_driver_value(event, None, "apparent_power_kva") == vals["apparent_power_total"]
    rms = (sum(vals[f"current_i{n}"] ** 2 for n in (1, 2, 3)) / 3) ** 0.5
    assert thermal_load_driver_value(event, None, "rms_current_a") == pytest.approx(rms)


def test_multi_asset_switching_and_isolation(at_repo_root: None) -> None:
    """Switching assets during replay must isolate state, reload events, and rebind nameplate rating."""
    app = create_app(settings=Settings(default_asset_id="TX_1000_COMM"))
    with TestClient(app) as client:
        # Step on TX_1000_COMM
        r1 = client.post("/v1/replay", json={"action": "start", "asset_id": "TX_1000_COMM"})
        assert r1.status_code == 200
        client.post("/v1/replay", json={"action": "step", "batch_size": 5, "asset_id": "TX_1000_COMM"})
        st1 = client.get("/v1/assets/TX_1000_COMM/state").json()
        assert st1["twin_state"]["asset_id"] == "TX_1000_COMM"
        assert st1["twin_state"]["state_sequence"] == 5

        # Switch to TX_250_MIX
        r2 = client.post("/v1/replay", json={"action": "reset", "asset_id": "TX_250_MIX"})
        assert r2.status_code == 200
        # Replay queue must have loaded TX_250_MIX events
        rep_stat = client.get("/v1/replay").json()
        assert rep_stat["total_events"] == 8757
        assert rep_stat["processed_events"] == 0

        # Step 3 events on TX_250_MIX
        client.post("/v1/replay", json={"action": "step", "batch_size": 3, "asset_id": "TX_250_MIX"})
        st2 = client.get("/v1/assets/TX_250_MIX/state").json()
        assert st2["twin_state"]["asset_id"] == "TX_250_MIX"
        assert st2["twin_state"]["state_sequence"] == 3
        # Capabilities on TX_250_MIX (not promoted) must gate forecasting
        assert st2["fact_bundle"]["capabilities"]["capabilities"]["C3"]["enabled"] is False


def test_maintenance_advisories_persist_across_replay_frames(at_repo_root: None) -> None:
    """A generated maintenance advisory must persist across subsequent frames until acknowledged/dismissed."""
    app = create_app(settings=Settings(default_asset_id="TX_1000_COMM"))
    with TestClient(app) as client:
        client.post("/v1/replay", json={"action": "start", "asset_id": "TX_1000_COMM"})
        # Injection is anchored to a running replay (the twin must have processed a frame)
        client.post("/v1/replay", json={"action": "step", "asset_id": "TX_1000_COMM", "batch_size": 1})
        trip_event = {
            "schema_version": "1.0.0",
            "event_id": "test_trip_001",
            "asset_id": "TX_1000_COMM",
            "event_time_utc": "2025-01-01T00:00:00Z",
            "received_time_utc": "2025-01-01T00:00:00Z",
            "source": {
                "system": "SCADA",
                "adapter_id": "test",
                "source_record_id": "trip_rec_1",
                "source_uri": "test://trip",
                "raw_sha256": "0" * 64,
            },
            "measurements": [
                {
                    "signal_id": "breaker_trip",
                    "value": 1,
                    "value_type": "int",
                    "unit_ucum": "1",
                    "original_name": "TRIP",
                    "original_value": "1",
                    "original_unit": "1",
                    "quality": {"severity": "GOOD", "flags": []},
                }
            ],
            "event_quality_flags": ["PROTECTION_TRIP_ACTIVE"],
            "mapping_version": "1.0.0",
        }
        ing_resp = client.post("/v1/telemetry", json={"asset_id": "TX_1000_COMM", "events": [trip_event]})
        assert ing_resp.status_code == 201

        st = client.get("/v1/assets/TX_1000_COMM/state").json()
        recs = st["fact_bundle"]["active_recommendations"]
        assert len(recs) >= 1
        p0_rec = next(r for r in recs if r["rule_id"] == "MNT-PROT-001")
        assert p0_rec["priority"] == "P0"

        # Advance benign replay frames
        client.post("/v1/replay", json={"action": "step", "batch_size": 5, "asset_id": "TX_1000_COMM"})
        st_after = client.get("/v1/assets/TX_1000_COMM/state").json()
        recs_after = st_after["fact_bundle"]["active_recommendations"]
        assert any(r["rule_id"] == "MNT-PROT-001" for r in recs_after)


def test_on_demand_and_periodic_checkpoints(at_repo_root: None) -> None:
    """Checkpoints can be created on-demand and retrieved from /v1/reports/runs."""
    app = create_app(settings=Settings(default_asset_id="TX_1000_COMM"))
    with TestClient(app) as client:
        # Step twin to advance sequence
        client.post("/v1/replay", json={"action": "start", "asset_id": "TX_1000_COMM"})
        client.post("/v1/replay", json={"action": "step", "batch_size": 10, "asset_id": "TX_1000_COMM"})

        # Create on-demand checkpoint
        post_chk = client.post("/v1/reports/checkpoints?asset_id=TX_1000_COMM")
        assert post_chk.status_code == 201
        chk_data = post_chk.json()
        assert "chk_TX_1000_COMM" in chk_data["checkpoint_id"]
        assert chk_data["state_sequence"] == 10

        # Query checkpoints list
        runs = client.get("/v1/reports/runs?asset_id=TX_1000_COMM").json()
        assert len(runs) >= 1
        assert runs[0]["asset_id"] == "TX_1000_COMM"
        assert runs[0]["state_sequence"] == 10

