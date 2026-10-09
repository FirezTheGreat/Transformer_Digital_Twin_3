# Distribution Transformer Digital Twin

**POWERNext-AI Hackathon 2026 — Track 2: Digital Twin for Intelligent Health Monitoring and Predictive Maintenance of Distribution Transformers**

---

## Project

The Distribution Transformer Digital Twin is a physics-grounded, stateful real-time condition monitoring and predictive maintenance system engineered specifically for medium- and low-voltage distribution assets. Unlike black-box machine learning approaches that overclaim remaining useful life without physical validation, this system combines deterministic physical principles with robust statistical anomaly detection, conformal uncertainty estimation, and capability-aware operational gating.

The core twin tracks transformer telemetry in continuous time using a first-order grey-box thermal differential equation coupled with multi-domain electrical analysis. It processes active power, reactive power, line currents, line-to-neutral voltages, winding temperatures, and ambient conditions to maintain a strictly synchronized, replayable state vector. Every state update produces a cryptographically hashed FactBundle ensuring complete auditability and provenance.

Operational health is evaluated across five independent diagnostic domains: Thermal, Electrical, Insulation, Mechanical, and Sensor Plausibility. The system computes a bounded Operational Transformer Health Index (OTHI) on a 0–100 scale, dynamically gating domain weights based on telemetry freshness and sensor reliability to prevent corrupted or stale inputs from distorting health assessments.

Deterministic maintenance policies map corroborative evidence into prioritized, explainable operational advisories (P0 Immediate to P3 Routine). The platform exposes a fully documented REST API, an interactive 3D/telemetry frontend dashboard, and automated export mechanisms for structured JSON, tabular CSV, and engineering-grade audit PDF reports.

---

## Architecture

The end-to-end processing pipeline operates deterministically from raw telemetry ingestion to formal compliance reporting:

```text
Source (SCADA / IoT Telemetry / CSV / Parquet)
   ↓
Canonical Telemetry (Pydantic schema validation & unit normalization)
   ↓
Validation (Deduplication, timestamp monotonicity, range & rate-of-change checks)
   ↓
Features (Symmetrical components, THD, unbalance ratios, rolling statistics)
   ↓
Stateful Twin (Deterministic state reducer F(State_{t-1}, Event_t) -> State_t)
   ↓
Thermal / Electrical Analysis (Grey-box ODE, conformal error bounds, phase imbalance)
   ↓
Anomaly / Evidence (Multi-domain CUSUM/Z-score detectors, evidence episodes)
   ↓
OTHI (Gated Multi-Domain Operational Transformer Health Index [0–100])
   ↓
Maintenance (Deterministic rule policy, priority ranking P0–P3, action windows)
   ↓
Reports (Deterministic JSON, CSV, and WeasyPrint PDF audit reports)
```

---

## Quick Start

### 1. Single-Command Deployment (Recommended)

Start the full system (Backend API on `:8000` and Frontend UI on `:3000`) using Docker Compose:

```bash
docker compose up --build
```

Verify backend readiness:

```bash
curl http://localhost:8000/healthz
```

Access the user interfaces:
- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
- **Interactive OpenAPI Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Check:** [http://localhost:8000/healthz](http://localhost:8000/healthz)

### 2. Local Python Development Setup

```bash
# Install backend dependencies in editable mode with development extras
cd backend
pip install -e ".[dev]"

# Run FastAPI backend server (default asset: CPRI TX_1000_COMM; replays its CAL partition, TEST is never loaded)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Serve another CPRI asset, e.g. one without a qualified model
DEFAULT_ASSET_ID=TX_250_MIX uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Requires Python 3.11+. On Windows without GTK, PDF reports use the `xhtml2pdf` fallback (installed by the `dev` extras).
The backend serves one asset per process; the dashboard follows the backend's `default_asset_id`.
All eight CPRI assets have a frozen grey-box model evaluated once on TEST. Only **TX_1000_COMM is PROMOTED** (forecasting and
what-if enabled); the other seven are NOT_PROMOTED (signed-bias gate) and run in shadow/descriptive mode with forecasting gated.
See `GET /v1/models/cpri-evaluation` and `docs/HACKATHON_RUNBOOK.md` §2b. The legacy Tripura asset remains available via
`DEFAULT_ASSET_ID=DT-TRIPURA-001`.

In a separate terminal for the frontend:

```bash
cd frontend
npm install
npm run dev
```

---

## Demo

Execute the end-to-end 7-stage automated hackathon demonstration script:

### Running via Docker:

```bash
docker compose exec backend python /app/demo_script.py
```

### Running Locally:

```bash
python demo_script.py
```

The script executes 7 deterministic verification stages:
1. **Baseline Telemetry Replay:** Nominal state tracking and storage ingestion.
2. **Sensor Quality Event:** High-gradient current spike detection and plausibility gating.
3. **Sustained Overload Excursion:** 140% loading event, evidence accumulation, and health impact.
4. **Multi-Domain Corroboration:** Cross-domain evidence fusion and OTHI gating.
5. **What-If Scenario Simulation:** Qualification gating on unpromoted thermal models.
6. **Operator Feedback:** Human-in-the-loop acknowledgement recorded in an immutable ledger.
7. **Audit PDF Export:** Deterministic WeasyPrint PDF report generation.

---

## API

The backend exposes canonical REST API routes mounted under `/v1` (with `/healthz` at root):

| Endpoint | Method | Description |
|---|---|---|
| `/healthz` | `GET` | System liveness probe and subsystem readiness diagnostics |
| `/v1/telemetry/frame` | `POST` | Ingest raw SCADA frame and advance state |
| `/v1/telemetry/canonical` | `POST` | Ingest canonical telemetry event |
| `/v1/replay/start` | `POST` | Start historical replay stream |
| `/v1/replay/pause` | `POST` | Pause active replay stream |
| `/v1/replay/resume` | `POST` | Resume paused replay stream |
| `/v1/replay/step` | `POST` | Advance replay stream by a single step |
| `/v1/replay/reset` | `POST` | Reset replay stream and state vector |
| `/v1/assets/{asset_id}/state` | `GET` | Current digital twin state vector and provenance hash |
| `/v1/assets/{asset_id}/history` | `GET` | Temporal query of historical state trajectory |
| `/v1/assets/{asset_id}/capabilities`| `GET` | Active C0–C4 capability tier manifest |
| `/v1/analytics/othi` | `GET` | Multi-domain OTHI score, sub-indices, and gating status |
| `/v1/analytics/anomalies` | `GET` | Active and historical anomaly evidence episodes |
| `/v1/analytics/maintenance` | `GET` | Prioritized maintenance recommendations (P0–P3) |
| `/v1/analytics/model-card` | `GET` | Grey-box thermal model parameters and qualification tier |
| `/v1/scenarios/what-if` | `POST` | Bounded 2-hour forward scenario simulation |
| `/v1/feedback/ledger` | `GET` | Immutable operator action and resolution ledger |
| `/v1/feedback/acknowledge` | `POST` | Record human operator feedback (ACK, DISMISS, OVERRIDE) |
| `/v1/reports/summary.json` | `GET` | Structured machine-readable JSON summary report |
| `/v1/reports/summary.csv` | `GET` | Multi-section tabular CSV summary report |
| `/v1/reports/summary.pdf` | `GET` | Formal engineering audit PDF report (WeasyPrint) |

---

## Data

The project strictly partitions and labels all data sources to ensure transparency:

- **Tripura Dataset (`data/tripura_raw/`, `data/processed/`):** Real-world SCADA telemetry from a 33/11kV distribution substation in Tripura, India. Used exclusively for development, baseline telemetry calibration, and statistical characterization. Nameplate rating (kVA) is unverified in this dataset; therefore, `relative_load_index` is computed against empirical 95th percentile loading ($142.9\text{ kVA}$).
- **CPRI & Synthetic Injection Scenarios (`fixtures/`):** Controlled edge-case fixtures and dynamic scenario injections (`INJ_SENSOR_SPIKE`, `INJ_SUSTAINED_OVERLOAD`, `INJ_PHASE_IMBALANCE`, etc.) used for regression testing and demonstration. Synthetic data is explicitly labeled `SYNTHETIC_SCENARIO` and is never claimed as unverified real-world ground truth.

---

## Engineering Honesty & Safety Guarantees

This Digital Twin adheres to rigorous physical and ethical boundaries:

1. **No RUL Overclaiming:** The system does **not** estimate numeric Remaining Useful Life (RUL) in hours or years without verified multi-year degradation datasets and dissolved gas analysis (DGA).
2. **No Failure Probability Claims:** Arbitrary statistical failure percentages (e.g. "94.2% chance of failure") are rejected in favor of empirical conformal confidence intervals and multi-domain evidence corroboration.
3. **No Autonomous Switching Control:** The twin operates strictly as a decision-support advisory system; autonomous breaker or tap-changer commands are prohibited.
4. **Tripura Thermal Model Status (`NOT_PROMOTED`):** Due to the lack of dedicated ambient temperature sensors in the raw Tripura feed, the thermal grey-box model ($\tau = 2.5\text{ h}$, $\beta_0 = 15.0^\circ\text{C}$, $\beta_1 = 0.0018^\circ\text{C/kVA}^2$) is classified as `DEVELOPMENT_ONLY` / `NOT_PROMOTED`. Forward what-if predictions return explicit qualification warnings.
5. **Unverified Nameplate Data:** In the absence of manufacturer test certificates, apparent power is reported relative to empirical baselines rather than nominal ratings.
6. **Insulation Ageing Gating:** Arrhenius/IEEE C57.91 thermal life consumption calculations remain disabled unless calibrated top-oil and hot-spot temperatures are verified.
7. **Discrete WTI Contacts:** Winding temperature indicator contacts are modeled as discrete alarm/trip flags rather than synthetic continuous analogues.

---

## Reports

The reporting engine exports deterministic summaries directly from the authoritative `FactBundle`:
- **JSON Export (`/v1/reports/summary.json`):** Complete machine-readable payload including state vectors, domain sub-indices, active episodes, and provenance metadata.
- **CSV Export (`/v1/reports/summary.csv`):** Standard multi-section tabular format suitable for spreadsheet import and SCADA historian archiving.
- **PDF Export (`/v1/reports/summary.pdf`):** Formal multi-page engineering audit document styled with WeasyPrint. Contains state vector summaries, OTHI breakdown charts, prioritized maintenance actions, operator feedback records, and cryptographic SHA-256 state provenance hashes.

---

## Testing

Run the full backend test suite covering unit, integration, and end-to-end regression suites:

Run from the **repository root** (several tests resolve `data/` relative to it):

```bash
# Run all backend tests
pytest -c backend/pyproject.toml --rootdir backend backend/tests

# Run static fixture regression suite (Phase 10.1)
pytest -c backend/pyproject.toml --rootdir backend backend/tests/e2e/test_static_fixtures.py

# Run dynamic synthetic injector suite (Phase 10.2)
pytest -c backend/pyproject.toml --rootdir backend backend/tests/e2e/test_dynamic_injections.py

# Run demo script regression test (Phase 10.3)
pytest -c backend/pyproject.toml --rootdir backend backend/tests/e2e/test_demo_script.py
```
