"""Comprehensive verification script for live Backend APIs."""

import json
import httpx

BASE_URL = "http://127.0.0.1:8000"

def test_api():
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    print("--- 1. Testing /healthz ---")
    r = client.get("/healthz")
    print("GET /healthz status:", r.status_code)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    health = r.json()
    print("Health response:", health["status"], "Default asset:", health["default_asset_id"])
    assert health["status"] in ("ok", "degraded")
    assert health["default_asset_id"] == "TX_1000_COMM"

    print("\n--- 2. Testing /v1/models/cpri-evaluation ---")
    r = client.get("/v1/models/cpri-evaluation")
    print("GET /v1/models/cpri-evaluation status:", r.status_code)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    eval_matrix = r.json()
    assets = {a["asset_id"]: a for a in eval_matrix["assets"]}
    print(f"Total CPRI assets evaluated: {len(assets)}")
    assert len(assets) == 8, f"Expected 8 assets, got {len(assets)}"

    # Check TX_1000_COMM
    tx_1000 = assets["TX_1000_COMM"]
    print("TX_1000_COMM status:", tx_1000["promotion_status"])
    print("TX_1000_COMM gates:", tx_1000["gates"])
    print("TX_1000_COMM capabilities:", json.dumps(tx_1000["capabilities"], indent=2))
    assert tx_1000["promotion_status"] == "PROMOTED"
    assert tx_1000["test_partition"] == "CONSUMED"
    assert tx_1000["capabilities"]["forecasting"]["available"] is True
    assert tx_1000["capabilities"]["what_if"]["available"] is True
    assert tx_1000["gates"]["signed_bias"] is True
    assert tx_1000["gates"]["mae_improvement"] is True

    # Check unpromoted assets
    unpromoted_assets = [aid for aid in assets if aid != "TX_1000_COMM"]
    for aid in unpromoted_assets:
        item = assets[aid]
        assert item["promotion_status"] == "NOT_PROMOTED", f"{aid} should be NOT_PROMOTED, got {item['promotion_status']}"
        assert item["capabilities"]["forecasting"]["available"] is False, f"{aid} forecasting should be disabled"
        assert item["capabilities"]["what_if"]["available"] is False, f"{aid} what_if should be disabled"
        assert item["capabilities"]["telemetry_monitoring"]["available"] is True
        assert item["capabilities"]["anomaly_detection"]["available"] is True
        assert item["capabilities"]["othi_health_index"]["available"] is True
        assert item["capabilities"]["maintenance_advisories"]["available"] is True
    print("All 7 unpromoted assets correctly gated and verified.")

    print("\n--- 3. Testing /v1/replay GET & POST action=step ---")
    r = client.get("/v1/replay")
    print("GET /v1/replay:", r.status_code, r.json())
    assert r.status_code == 200

    r = client.post("/v1/replay", json={"action": "step", "asset_id": "TX_1000_COMM"})
    print("POST /v1/replay step:", r.status_code, r.json())
    assert r.status_code == 200

    print("\n--- 4. Testing /v1/assets/TX_1000_COMM/state ---")
    r = client.get("/v1/assets/TX_1000_COMM/state")
    print("GET /v1/assets/TX_1000_COMM/state:", r.status_code)
    assert r.status_code == 200
    state = r.json()
    print("State time:", state["state_time_utc"], "Highest tier:", state["highest_tier"])

    print("\n--- 5. Testing /v1/assets/TX_1000_COMM/health ---")
    r = client.get("/v1/assets/TX_1000_COMM/health")
    print("GET /v1/assets/TX_1000_COMM/health:", r.status_code)
    assert r.status_code == 200
    health_bundle = r.json()
    print("OTHI score:", health_bundle.get("composite_index"), "Domain breakdown:", list(health_bundle.get("domain_scores", {}).keys()))

    print("\n--- 6. Testing /v1/assets/TX_1000_COMM/recommendations ---")
    r = client.get("/v1/assets/TX_1000_COMM/recommendations")
    print("GET /v1/assets/TX_1000_COMM/recommendations:", r.status_code)
    assert r.status_code == 200

    print("\n--- 7. Testing /v1/assets/TX_1000_COMM/scenario (What-If) ---")
    scen_req = {
        "load_multiplier": 1.25,
        "target_ambient_degc": 35.0,
        "horizon_steps": 4,
    }
    r = client.post("/v1/assets/TX_1000_COMM/scenario", json=scen_req)
    print("POST /v1/assets/TX_1000_COMM/scenario status:", r.status_code)
    assert r.status_code == 200
    scen_res = r.json()
    print("Projection enabled:", scen_res["is_enabled"])
    print("Trajectory step count:", len(scen_res["trajectory"]))
    if scen_res["is_enabled"]:
        horizons = [step["horizon_minutes"] for step in scen_res["trajectory"]]
        print("Horizons:", horizons)
        assert horizons == [30, 60, 90, 120]

    print("\n--- 8. Testing /v1/assets/TX_250_MIX/scenario (Unpromoted Gating) ---")
    r = client.post("/v1/assets/TX_250_MIX/scenario", json=scen_req)
    print("POST /v1/assets/TX_250_MIX/scenario status:", r.status_code)
    assert r.status_code == 200
    scen_unpromoted = r.json()
    print("Unpromoted projection enabled:", scen_unpromoted["is_enabled"])
    print("Disabled reason:", scen_unpromoted["disabled_reason"])
    assert scen_unpromoted["is_enabled"] is False
    assert "scenario capability is not qualified" in scen_unpromoted["disabled_reason"] or "not qualified" in scen_unpromoted["disabled_reason"]

    print("\n--- 9. Testing /v1/reports/summary.json and summary.pdf ---")
    r = client.get("/v1/reports/summary.json?asset_id=TX_1000_COMM")
    print("GET /v1/reports/summary.json status:", r.status_code, "Length:", len(r.content))
    assert r.status_code == 200

    r = client.get("/v1/reports/summary.pdf?asset_id=TX_1000_COMM")
    print("GET /v1/reports/summary.pdf status:", r.status_code, "Length:", len(r.content))
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF"), "Response is not a valid PDF file"
    print("Renderer used:", r.headers.get("X-Report-Renderer"))

    print("\n================ LIVE API CONTRACT TESTS PASSED ================")

if __name__ == "__main__":
    test_api()
