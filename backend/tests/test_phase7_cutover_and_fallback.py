"""Phase 7 Cutover, Candidate DT-01 Integration, and Rollback Verification Tests.

Verifies:
1. Deterministic asset profile resolution for both cpri_v3_0_2 and gridpulse_synthetic_v1 assets.
2. Safe model artifact resolution: DT-01 promoted with verified parameters; DT-02..DT-04 unpromoted.
3. No silent fallback to CPRI or Tripura for missing candidate artifacts.
4. Dataset replay loading: CAL partition isolation without cross-dataset mixing.
5. Dynamic construction-aware capability manifest (oil level vs tank pressure vs short-circuit).
6. Complete state isolation and bidirectional rollback from DT-01 to CPRI baseline.
7. REST API catalog and evaluation matrix endpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.core.registry import (
    CPRI_SYNTHETIC_ASSET_RATINGS,
    GRIDPULSE_CANDIDATE_ASSETS,
    resolve_asset_profile,
    resolve_model_artifact,
)
from app.adapters.gridpulse_synthetic import SYNTHETIC_ASSET_PROFILES
from app.models.capability import CapabilityTier
from app.models.thermal_artifact import QualificationStatus
from app.core.storage import StorageEngine
from app.engine.replay import ReplayEngine
from app.api.routers.replay import ensure_dataset_loaded
from app.engine.capability import CapabilityEvaluator
from app.models.twin_state import TwinState
from datetime import datetime, timezone
from app.main import create_app


def test_asset_profile_resolution_both_datasets():
    """Verify that both CPRI and GridPulse synthetic candidate profiles resolve accurately."""
    # CPRI asset
    p_cpri = resolve_asset_profile(dataset_id="cpri_v3_0_2", asset_id="TX_1000_COMM")
    assert p_cpri.asset_id == "TX_1000_COMM"
    assert p_cpri.rated_kva == 1000.0
    assert p_cpri.expected_cadence_s == 1800
    assert p_cpri.cooling_class == "ONAN"

    # DT-01 (Promoted Conservator)
    p_dt01 = resolve_asset_profile(dataset_id="gridpulse_synthetic_v1", asset_id="DT-01")
    assert p_dt01.asset_id == "DT-01"
    assert p_dt01.rated_kva == 250.0
    assert p_dt01.tank_type == "CONSERVATOR"
    assert p_dt01.has_oil_level_gauge is True
    assert p_dt01.has_pressure_sensor is False
    assert p_dt01.expected_cadence_s == 1800

    # DT-03 (Unpromoted Sealed Corrugated)
    p_dt03 = resolve_asset_profile(dataset_id="gridpulse_synthetic_v1", asset_id="DT-03")
    assert p_dt03.asset_id == "DT-03"
    assert p_dt03.rated_kva == 250.0
    assert p_dt03.tank_type == "SEALED_CORRUGATED"
    assert p_dt03.has_oil_level_gauge is False
    assert p_dt03.has_pressure_sensor is True


def test_model_artifact_resolution_and_promotion_gates():
    """Verify DT-01 resolves verified candidate parameters; DT-02..04 stay gated; CPRI resolves baseline."""
    # CPRI Baseline
    m_cpri = resolve_model_artifact(dataset_id="cpri_v3_0_2", asset_id="TX_1000_COMM")
    assert m_cpri.asset_id == "TX_1000_COMM"
    assert m_cpri.dataset_id in ("cpri_v3_0_2", "cpri_v3")
    assert m_cpri.promotion.status == "PROMOTED"
    assert m_cpri.parameters is not None
    assert abs(m_cpri.parameters.beta_0 - 7.8025) < 0.05
    assert abs(m_cpri.parameters.beta_1 - 42.0074) < 0.05
    assert abs(m_cpri.parameters.tau_hours - 4.2132) < 0.05

    # Candidate DT-01 (Promoted)
    m_dt01 = resolve_model_artifact(dataset_id="gridpulse_synthetic_v1", asset_id="DT-01")
    assert m_dt01.asset_id == "DT-01"
    assert m_dt01.dataset_id == "gridpulse_synthetic_v1"
    assert m_dt01.promotion.status == "PROMOTED"
    assert m_dt01.parameters is not None
    assert abs(m_dt01.parameters.beta_0 - 11.0978) < 0.05
    assert abs(m_dt01.parameters.beta_1 - 19.5021) < 0.05
    assert abs(m_dt01.parameters.tau_hours - 2.7090) < 0.05
    assert m_dt01.qualification.forecast_qualification == QualificationStatus.QUALIFIED
    assert m_dt01.qualification.residual_anomaly_qualification == QualificationStatus.QUALIFIED

    # Candidate DT-02 (Unpromoted per Phase 6 coverage gate)
    m_dt02 = resolve_model_artifact(dataset_id="gridpulse_synthetic_v1", asset_id="DT-02")
    assert m_dt02.asset_id == "DT-02"
    assert m_dt02.promotion.status == "NOT_PROMOTED"
    assert m_dt02.qualification.forecast_qualification == QualificationStatus.PENDING_VALIDATION

    # Candidate DT-03 (Unpromoted)
    m_dt03 = resolve_model_artifact(dataset_id="gridpulse_synthetic_v1", asset_id="DT-03")
    assert m_dt03.promotion.status == "NOT_PROMOTED"

    # Candidate DT-04 (Unpromoted)
    m_dt04 = resolve_model_artifact(dataset_id="gridpulse_synthetic_v1", asset_id="DT-04")
    assert m_dt04.promotion.status == "NOT_PROMOTED"


def test_no_silent_fallback_for_unknown_or_missing_candidate():
    """Verify that an unknown candidate asset never silently receives CPRI or Tripura constants."""
    m_unknown = resolve_model_artifact(dataset_id="gridpulse_synthetic_v1", asset_id="DT-99")
    assert m_unknown.dataset_id == "gridpulse_synthetic_v1"
    assert m_unknown.asset_id == "DT-99"
    assert m_unknown.parameters is None
    assert m_unknown.model_version == "uncalibrated"


def test_construction_aware_capability_evaluation():
    """Verify construction-aware capabilities on DT-01 (conservator) and DT-03 (sealed)."""
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    base_state = TwinState(
        asset_id="DT-01",
        state_time_utc=now,
        last_processed_event_id="test-1",
        event_time_watermark_utc=now,
        state_sequence=1,
        state_hash="dummy",
    )

    # DT-01: Conservator tank -> pressure sensor is NOT fitted
    p_dt01 = resolve_asset_profile(asset_id="DT-01")
    eval_dt01 = CapabilityEvaluator(profile=p_dt01, is_model_promoted=True)
    manifest_dt01 = eval_dt01.evaluate(base_state)
    pressure_cap = manifest_dt01.capabilities.get("tank_pressure_monitoring")
    assert pressure_cap is not None
    assert pressure_cap.enabled is False
    assert "NO_PRESSURE_SENSOR_FITTED" in pressure_cap.disabled_reason_codes

    # DT-03: Sealed corrugated tank -> oil level gauge is NOT fitted
    base_state_dt03 = base_state.model_copy(update={"asset_id": "DT-03"})
    p_dt03 = resolve_asset_profile(asset_id="DT-03")
    eval_dt03 = CapabilityEvaluator(profile=p_dt03, is_model_promoted=False)
    manifest_dt03 = eval_dt03.evaluate(base_state_dt03)
    oil_cap = manifest_dt03.capabilities.get("oil_level_monitoring")
    assert oil_cap is not None
    assert oil_cap.enabled is False
    assert "NO_OIL_GAUGE_FITTED" in oil_cap.disabled_reason_codes


def test_replay_loading_and_dataset_isolation():
    """Verify CAL partition replay loading for both datasets without cross-contamination."""
    storage = StorageEngine(db_path=":memory:")
    replay = ReplayEngine(storage=storage, asset_id="DT-01")

    # Ingest DT-01 candidate CAL partition
    count_dt01 = ensure_dataset_loaded(storage, replay, asset_id="DT-01")
    assert count_dt01 == 1728
    assert len(replay._events) == 1728
    assert all(e.asset_id == "DT-01" for e in replay._events)

    # Ingest CPRI baseline CAL partition
    replay_cpri = ReplayEngine(storage=storage, asset_id="TX_1000_COMM")
    count_cpri = ensure_dataset_loaded(storage, replay_cpri, asset_id="TX_1000_COMM")
    assert count_cpri > 0
    assert all(e.asset_id == "TX_1000_COMM" for e in replay_cpri._events)

    # Verify switching back to DT-01 retains DT-01 events strictly
    replay.load_from_storage()
    assert len(replay._events) == 1728
    assert all(e.asset_id == "DT-01" for e in replay._events)


def test_api_catalog_and_evaluation_endpoints():
    """Verify REST API returns inventory of both datasets and evaluation matrices."""
    app = create_app()
    with TestClient(app) as client:
        # Asset Catalog
        res_cat = client.get("/v1/assets")
        assert res_cat.status_code == 200
        cat = res_cat.json()
        assert "datasets" in cat
        dataset_ids = [d["dataset_id"] for d in cat["datasets"]]
        assert "cpri_v3_0_2" in dataset_ids
        assert "gridpulse_synthetic_v1" in dataset_ids

        # Candidate Evaluation Matrix
        res_cand = client.get("/v1/models/candidate-evaluation")
        assert res_cand.status_code == 200
        cand = res_cand.json()
        assert cand["dataset_id"] == "gridpulse_synthetic_v1"
        asset_ids = [a["asset_id"] for a in cand["assets"]]
        assert "DT-01" in asset_ids
        dt01_row = next(a for a in cand["assets"] if a["asset_id"] == "DT-01")
        assert dt01_row["promotion_status"] == "PROMOTED"
        assert dt01_row["gates"]["mae_improvement"] is True
        assert dt01_row["gates"]["signed_bias"] is True

        dt02_row = next(a for a in cand["assets"] if a["asset_id"] == "DT-02")
        assert dt02_row["promotion_status"] == "NOT_PROMOTED"

        # CPRI Evaluation Matrix preserved
        res_cpri = client.get("/v1/models/cpri-evaluation")
        assert res_cpri.status_code == 200
        cpri = res_cpri.json()
        assert cpri["dataset_id"] == "cpri_v3_0_2"
        cpri_ids = [a["asset_id"] for a in cpri["assets"]]
        assert "TX_1000_COMM" in cpri_ids
