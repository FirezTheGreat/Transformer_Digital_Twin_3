# GridPulse — Distribution Transformer Digital Twin

**POWERNext-AI Hackathon 2026 — Track 2: Digital Twin for Intelligent Health Monitoring and Predictive Maintenance of Distribution Transformers**

> **Current Implementation State:** Phases 1–8 Implemented, Evaluated, and Integrated (**PASS**).  
> Both CPRI v3.0.2 Baseline (8 assets) and GridPulse Synthetic v1.0.0 Candidate (`DT-01` Promoted; `DT-02`..`04` Gated) are operational with dynamic switching and reliable fallback.  
> **Authoritative Roadmaps & References:**
> - Master Execution Plan: [`GRIDPULSE_MASTER_EXECUTION_PLAN.md`](file:///c:/1st%20year%20learning%20programs/CPRI/Transformer_Digital_Twin/GRIDPULSE_MASTER_EXECUTION_PLAN.md)
> - Extra Domains & Candidate Scope: [`GRIDPULSE_DATASET_SYN_ADAPTATION_AND_EXTRA_DOMAIN_SCOPE.md`](file:///c:/1st%20year%20learning%20programs/CPRI/Transformer_Digital_Twin/GRIDPULSE_DATASET_SYN_ADAPTATION_AND_EXTRA_DOMAIN_SCOPE.md)
> - Backend Stabilization Proposals & Fixes: [`BACKEND_STABILIZATION_PROPOSALS.md`](file:///c:/1st%20year%20learning%20programs/CPRI/Transformer_Digital_Twin/BACKEND_STABILIZATION_PROPOSALS.md)
> - Technical References & Bibliography: [`docs/references/TECHNICAL_REFERENCES_AND_CITATIONS.md`](file:///c:/1st%20year%20learning%20programs/CPRI/Transformer_Digital_Twin/docs/references/TECHNICAL_REFERENCES_AND_CITATIONS.md)
> - Execution & Verification Log: [`docs/execution/GRIDPULSE_EXECUTION_LOG.md`](file:///c:/1st%20year%20learning%20programs/CPRI/Transformer_Digital_Twin/docs/execution/GRIDPULSE_EXECUTION_LOG.md)
> - Frozen Architecture Decisions: [`docs/FINAL_ARCHITECTURE_DECISIONS.md`](file:///c:/1st%20year%20learning%20programs/CPRI/Transformer_Digital_Twin/docs/FINAL_ARCHITECTURE_DECISIONS.md)

---

## Project

GridPulse is a physics-grounded, stateful real-time condition monitoring and predictive maintenance digital twin engineered specifically for medium- and low-voltage distribution assets. Unlike black-box machine learning approaches that overclaim remaining useful life without physical validation, GridPulse combines deterministic physical principles with robust statistical anomaly detection, conformal uncertainty estimation, and construction-aware operational capability gating.

The core twin tracks transformer telemetry in continuous time using a first-order grey-box thermal differential equation (IEC 60076-7 / IEEE C57.91) coupled with multi-domain electrical, oil-level, tank pressure, and protection analysis. It processes active/reactive power, line currents, line-to-neutral voltages, winding temperatures, ambient conditions, conservator oil level, sealed-tank gauge pressure, and protection trip contacts to maintain a strictly synchronized, replayable state vector. Every state update produces a cryptographically hashed FactBundle ensuring complete auditability and provenance.

Operational health is evaluated across five independent diagnostic domains: Thermal, Electrical, Insulation, Mechanical, and Oil/Protection Status. The system computes a bounded Operational Transformer Health Index (OTHI) on a 0–100 scale, dynamically gating domain weights based on telemetry freshness, asset construction (conservator vs sealed corrugated tank), and sensor reliability.

Deterministic maintenance policies map corroborative evidence into prioritized, explainable operational advisories (P0 Immediate to P3 Routine). The platform exposes a fully documented REST API, an interactive 3D/telemetry frontend dashboard, and automated export mechanisms for structured JSON, tabular CSV, and engineering-grade audit PDF reports.

---

## Architecture & Pipeline

The end-to-end processing pipeline operates deterministically from raw telemetry ingestion to formal compliance reporting:

```text
Source (SCADA / IoT Telemetry / CSV / Parquet)
   ↓
Canonical Telemetry (Pydantic schema validation & explicit UCUM unit normalization)
   ↓
Validation (Deduplication, timestamp monotonicity, rate-of-change & stuck-gauge plausibility)
   ↓
Features (Symmetrical components, THD, unbalance ratios, prospective I_sc, rolling slopes)
   ↓
Stateful Twin (Deterministic state reducer F(State_{t-1}, Event_t) -> State_t)
   ↓
Thermal / Electrical / Pressure Analysis (Grey-box ODE, conformal bounds, tank limits)
   ↓
Anomaly / Evidence (Multi-domain CUSUM/Z-score detectors, evidence episodes)
   ↓
Capability Gating (Construction-aware enabling of oil vs pressure vs thermal tiers)
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
The backend dynamically supports both datasets and all 12 assets with interactive switching in the UI ReplayBar:
- **CPRI Synthetic Benchmark v3.0.2 (Baseline):** 8 assets (`TX_1000_COMM` PROMOTED with $\beta_0=7.8025^\circ\text{C}, \beta_1=42.0074^\circ\text{C}, \tau=4.2132\text{ h}$; 7 assets run in descriptive/shadow mode).
- **GridPulse Synthetic v1.0.0 (Candidate):** 4 assets (`DT-01` PROMOTED with $\beta_0=11.0978^\circ\text{C}, \beta_1=19.5021^\circ\text{C}, \tau=2.7090\text{ h}$; `DT-02` through `DT-04` run in descriptive mode).
See `GET /v1/assets`, `GET /v1/models/cpri-evaluation`, and `GET /v1/models/candidate-evaluation`. The legacy Tripura asset remains accessible via `DEFAULT_ASSET_ID=DT-TRIPURA-001`.

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
| `/v1/assets` | `GET` | Multi-dataset catalog (available datasets, ratings, tank types, active asset) |
| `/v1/telemetry/frame` | `POST` | Ingest raw SCADA frame and advance state |
| `/v1/telemetry/canonical` | `POST` | Ingest canonical telemetry event |
| `/v1/replay` | `GET` | Current deterministic chronological replay status and position |
| `/v1/replay` | `POST` | Control replay playback (`start`, `pause`, `resume`, `step`, `reset`, `seek`, `asset_id`, `dataset_id`) |
| `/v1/assets/{asset_id}/state` | `GET` | Current digital twin state vector, telemetry, and FactBundle |
| `/v1/assets/{asset_id}/history` | `GET` | Temporal query of historical state trajectory |
| `/v1/assets/{asset_id}/capabilities`| `GET` | Active C0–C4 capability tier manifest with disabled reasons |
| `/v1/analytics/othi` | `GET` | Multi-domain OTHI score, sub-indices, and gating status |
| `/v1/analytics/anomalies` | `GET` | Active and historical anomaly evidence episodes |
| `/v1/analytics/maintenance` | `GET` | Prioritized maintenance recommendations (P0–P3) |
| `/v1/analytics/model-card` | `GET` | Grey-box thermal model parameters and qualification tier |
| `/v1/models/cpri-evaluation` | `GET` | CPRI baseline model evaluation matrix and gate outcomes (8 assets) |
| `/v1/models/candidate-evaluation` | `GET` | GridPulse candidate evaluation matrix and gate outcomes (4 assets) |
| `/v1/scenarios/what-if` | `POST` | Bounded 2-hour forward scenario simulation |
| `/v1/feedback/ledger` | `GET` | Immutable operator action and resolution ledger |
| `/v1/feedback/acknowledge` | `POST` | Record human operator feedback (ACK, DISMISS, RESOLVE, OVERRIDE) |
| `/v1/reports/compliance` | `GET` | Structured machine-readable compliance report (JSON/CSV) |
| `/v1/reports/pdf` | `GET` | Formal engineering audit PDF report (WeasyPrint / xhtml2pdf fallback) |

---

## Data & Partitions

The project strictly partitions, isolates, and labels all data sources to ensure research integrity, zero data leakage, and verified rollback:

- **Active CPRI v3.0.2 Production Baseline (`data/processed/`):**
  - Empirical 15-minute SCADA telemetry from 8 distribution transformer assets (`TX_100_RES` through `TX_1000_COMM`).
  - Partitioned chronologically into:
    - `cpri_v3_fit.parquet` (SHA-256: `8e258d78587069636457a505bd03a166098fa503846d98d47c4a433b815190f4`)
    - `cpri_v3_calibration.parquet` (SHA-256: `48d44e9e0e1746d29216741d7d73bb27e293494ab601c435858f067ead699371`)
    - `cpri_v3_test.parquet` (SHA-256: `c57adadd838a1a7fb79b1225cda06333817c34709a9bfcfd9de5e42be7527679`)
  - Evaluated under the strict FIT → CAL → FREEZE → TEST protocol. Only `TX_1000_COMM` passed the signed-bias gate and is `PROMOTED` for forward forecasting; the remaining 7 run in descriptive/shadow mode.

- **Evaluated GridPulse Synthetic Dataset (`data/candidates/gridpulse_synthetic_v1/`):**
  - Extracted from `gridpulse_synthetic_v1.zip` (SHA-256: `4601e56663158a129acb777b2725cf1eab0ad17f95527e59be1bf6d39bf6e827`).
  - Contains 4 distribution assets (`DT-01` to `DT-04`, 160–500 kVA, 11kV/433V ONAN) at 30-minute sampling cadence over 180 continuous days (34,560 rows).
  - Supplies expanded domain fields: `oil_level_pct`, `pressure_kpa`, `pressure_relief_operated`, `lv_breaker_trip`, `hv_fuse_blown`.
  - **Promotion Status & Cutover:** `DT-01` passed all Phase 6 holdout TEST gates (MAE improvement +48.57%, coverage 96.36%) and is `PROMOTED` in Phase 7 cutover; `DT-02` through `DT-04` failed the 120-min coverage gate and remain strictly `NOT_PROMOTED`.
  - **Isolation & Fallback:** Both datasets remain operational in parallel. Switching between CPRI and DT-01 is instantaneous, preserves isolated runtime states, and guarantees zero cross-dataset leakage.

- **Historical Development Telemetry (`data/tripura_raw/`):**
  - Historical 33/11kV telemetry used during initial Phase 1 prototype development. Tripura models remain `NOT_PROMOTED`.

---

## Engineering Honesty & Safety Guarantees

GridPulse adheres to strict physical and ethical boundaries:

1. **No RUL Overclaiming:** The system does **not** estimate whole-life Remaining Useful Life (RUL) in hours or years without verified multi-year degradation datasets and dissolved gas analysis (DGA).
2. **No Arbitrary Failure Probability Claims:** Arbitrary statistical failure percentages (e.g. "94.2% chance of failure") are rejected in favor of empirical conformal confidence intervals and multi-domain evidence corroboration.
3. **No Autonomous Switching Control:** The twin operates strictly as a decision-support advisory system; autonomous breaker or tap-changer commands are prohibited.
4. **Insulation Ageing Gating:** Arrhenius/IEEE C57.91 thermal life consumption calculations remain disabled (`C4_THERMAL_INSULATION_LIFETIME = False`) unless verified paper insulation class and calibrated hotspot temperatures exist.
5. **No Waveform Reconstruction:** 30-minute SCADA telemetry cannot reconstruct sub-cycle short-circuit waveforms or peak asymmetry. Symmetrical short-circuit values are reported solely as prospective reference indicators.
6. **No Spontaneous Oil Recovery:** Telemetry oil-level slope does not prove a physical leak; it emits advisory `MNT-OIL-008` triggering physical visual inspection.

---

## Reports

The reporting engine exports deterministic summaries directly from the authoritative `FactBundle`:
- **Structured Compliance Report (`/v1/reports/compliance`):** Complete machine-readable JSON or CSV payload including state vectors, domain sub-indices, active episodes, and cryptographic provenance hash.
- **Formal Audit PDF Export (`/v1/reports/pdf`):** Formal multi-page engineering audit document styled with WeasyPrint (with automated fallback). Contains state vector summaries, OTHI breakdown charts, prioritized maintenance actions, operator feedback records, and cryptographic SHA-256 state provenance hashes.

---

## Testing & Verification Evidence

All capabilities are verified with deterministic automated test suites. Run from the **repository root**:

```bash
# 1. Targeted Phase 7 Cutover & Fallback Suite (6 tests)
pytest backend/tests/test_phase7_cutover_and_fallback.py -v

# 2. Candidate Adaptation & Extra Domains Suite (24 tests)
pytest backend/tests/test_candidate_adaptation_and_extra_domains.py -v

# 3. Stabilization Fixes Suite (9 tests)
pytest backend/tests/test_stabilization_fixes.py -v

# 4. Core API & Analytics Contract Suites (22 tests)
pytest backend/tests/test_api_core.py backend/tests/test_api_analytics.py -v

# 5. FactBundle, Contracts Fixtures & Compliance Reports (29 tests)
pytest backend/tests/test_contracts_fixture.py backend/tests/test_fact_bundle.py backend/tests/test_reports.py -v
```

### Verified Test Evidence

| Suite | Scope | Pass Count | Runtime | Status |
|---|---|:---:|:---:|:---:|
| **Targeted Phase 7 & 8 Suites** | Cutover, fallback, extra domains, stabilization, API contracts | **81 / 81** | 46.23s | **PASS** |
| **Phase 7 Cutover & Fallback** | Multi-dataset registry resolution, rollback determinism | **6 / 6** | 29.12s | **PASS** |
| **Extra Domains & Candidate** | Oil-level trend, tank pressure, derived short-circuit stress | **24 / 24** | 1.93s | **PASS** |
| **Backend Stabilization Fixes** | P0–P2 fixes (thermal wiring, trip unlatch, advisory resolution) | **9 / 9** | 1.57s | **PASS** |
| **Frontend Production Build** | TypeScript validation & Vite bundle compilation | **Clean (0 errors)** | 15.65s | **PASS** |
| **Docker Compose Live Integration** | Backend (`:8000`) & Frontend (`:3000`) healthy, live e2e smoke | **All Routes 200** | — | **PASS** |
