# Critical Decisions & Deferred Engineering Checks

## Purpose

This document records known engineering issues, unresolved decisions,
validation requirements, and phase-specific constraints discovered during
implementation and review.

It is a control document for implementation.

A critical decision marked `PENDING_TEAM_DECISION` MUST NOT be decided or
implemented by Antigravity without explicit team instruction.

When the relevant implementation phase is reached, Antigravity must:

1. identify the pending decision,
2. explain the decision and its consequences,
3. present viable options and trade-offs,
4. stop,
5. wait for explicit team instruction,
6. implement only the selected decision.

This document must be consulted before implementing any phase that contains
a corresponding pending decision.

## Statuses

- `PENDING_TEAM_DECISION` — team discussion/decision required before implementation.
- `DECIDED_PENDING_IMPLEMENTATION` — team has decided; implementation remains.
- `IMPLEMENTED` — decision implemented and verified.
- `VALIDATION_REQUIRED` — no architectural decision is currently required,
  but empirical validation is mandatory.
- `DEFERRED` — intentionally postponed by the team.

---

# Phase 2.2 — Storage & Temporal Queries

## Historical event-time / ingestion-time semantics

Status: IMPLEMENTED

Historical source timestamps remain strictly distinguishable from system
ingestion/replay timestamps. Nullable `received_time_utc` in `CanonicalEvent`
and separate `ingested_at_utc` in DuckDB table `canonical_events` preserve this
provenance without fabricating timestamps.

---

## Conflicting duplicate preservation and analytical eligibility

Status: DECIDED_PENDING_IMPLEMENTATION

Conflicting duplicate observations must remain identifiable.

A deterministic `keep='first'` rectangular representation must never be
interpreted as evidence that the first observation is physically correct.

Unresolved conflicting observations must not silently become eligible model
fit/calibration/evaluation truth.

The exact storage representation, conflict-group structure, and analytical
eligibility mechanism must be finalized during the relevant implementation
work if the current contract does not fully determine them.

---

## Union-of-events vs complete-case analytical views

Status: IMPLEMENTED

Team Decision (Locked):
- [Development] Use UNION-OF-EVENTS for canonical storage in DuckDB and Parquet.
  Do NOT globally discard timestamps merely because some signals are missing.
- [Development] Later, individual model calibration/training pipelines apply
  MODEL-SPECIFIC COMPLETE-CASE FILTERING: a model may require all of its own inputs
  to be present and valid (via `get_complete_case_matrix`), but unrelated missing signals
  must not discard the observation from storage.
- [Runtime] Missing runtime signals and fallback behavior are NOT part of Phase 2.2.
  Runtime fallback logic is strictly isolated to Phase 3/4.

---

# Phase 2.3 — Watermarking & Late Events

## Late-event supersession semantics

Status: IMPLEMENTED

Team Decision (Locked):
- Option A: Store & Flag Late.
- Watermark configured to 10 minutes of event-time lateness.
- Events with `event_time_utc >= watermark` enter the reordering buffer and are
  emitted in deterministic order (`event_time_utc ASC, event_id ASC`).
- Events with `event_time_utc < watermark` are stored in DuckDB and flagged with
  `OUT_OF_ORDER` and `LATE` quality flags with an audit notification.
- Runtime `TwinState` is NOT rewound or rolled back. Original event timestamps
  and source provenance remain strictly preserved.

---

# Phase 2.4 — Replay

## Replay treatment of revised/late observations

Status: IMPLEMENTED

Replay Semantics (Locked):
- Baseline replay queries stored canonical events strictly ordered by
  `(event_time_utc ASC, event_id ASC)` to feed downstream ingestion in monotonic physical time.
- Replay is strictly read-only with respect to historical datasets and does not train, calibrate,
  or modify any model.
- Default demonstration period is configured to the held-out Tripura TEST partition.
- A controlled test/chaos mode is provided for deliberately emitting out-of-order synthetic events
  to exercise the runtime watermarking and reordering buffer without mutating stored data.

---

# Phase 3.1 — Electrical Physics

## Signed power and power-factor invariants

Status: VALIDATION_REQUIRED

Physical checks must respect signed active/reactive power and the dataset's
actual PF conventions.

Do not use incorrect universal invariants such as:
- S >= P
- S >= Q
- 0 <= PF <= 1

without accounting for signed values and source conventions.

Use magnitude-based checks where physically appropriate.

---

## Thermal inequalities

Status: VALIDATION_REQUIRED

Thermal relationships such as:

`T_HS >= T_o >= T_a`

must not be encoded as universal physical invariants without accounting for
sensor semantics, model scope, and measurement quality.

Use them as plausibility checks where appropriate.

---

# Phase 4.1 — Thermal Model & Load Driver Selection

## Thermal load-driver selection on FIT-only data

Status: DECIDED_PENDING_IMPLEMENTATION

Team Decision (Locked):
- The thermal model may use either apparent power `S` or RMS-equivalent phase current `I_eq` as its load driver.
- This selection must be made strictly on **FIT-only data** using a predeclared rolling-origin predictive metric (not in-sample fit error).
- Criteria include predictive performance and stability across chronological FIT folds.
- Once selected: frozen before CAL; CAL cannot switch driver; TEST is not used; TEST remains untouched lockbox.
- Selected driver documented with evidence and provenance.

---

# Phase 4.2 — Thermal Calibration & Validation

## Thermal model identifiability & methodology parameters

Status: DECIDED_PENDING_IMPLEMENTATION

Team Decisions (Locked):
1. **Rolling-Origin Model/Driver Validation:**
   - Evaluated strictly on **FIT partition** using expanding-window chronological evaluation with **$K=5$ folds**.
   - CAL and TEST partitions are strictly sealed and excluded from fold selection.
2. **Huber Loss Scale Estimation:**
   - Standard statistical tuning constant $c = 1.345$.
   - Scale $\sigma_{\text{fit}} = 1.4826 \cdot \text{MAD}(\text{residuals}_{\text{fit}})$ estimated deterministically on the FIT partition.
   - Huber threshold computed as $\delta = 1.345 \cdot \sigma_{\text{fit}}$ on FIT. CAL/TEST are never used to compute $\delta$.
3. **Thermal Time-Constant Bounds & Search Space:**
   - Unified parameter domain: $\tau \in [0.5, 24.0]\,\text{hours}$.
   - Deterministic logarithmic grid initialization and Stage 2 local refinement remain strictly inside $[0.5, 24.0]\,\text{hours}$.
   - A fitted parameter solution on/at the domain boundaries ($\tau \le 0.51\,\text{h}$ or $\tau \ge 23.9\,\text{h}$) is flagged as an identifiability failure/warning condition.
4. **Tau Stability Across Folds:**
   - Parameter stability gate: $CV(\tau) \le 0.60$ across rolling folds.
   - Clearly categorized as a project-specific engineering threshold.
5. **Conformal Uncertainty Scale Floor:**
   - Minimum horizon scale floor $s_h \ge 0.50\,^\circ\text{C}$.
   - Documented as a measurement-resolution safeguard associated with the observed $\sim 1\,^\circ\text{C}$ integer thermal telemetry quantization (not a physical sensor model or asymptotic validity guarantee).

Before promotion, evaluate:
- parameter stability,
- chronological stability,
- continuous-segment stability,
- conditional error by operating region,
- residual bias,
- residual autocorrelation,
- exact-horizon performance,
- uncertainty coverage,
- extrapolation behavior.

Model promotion must not be assumed merely because sufficient data volume exists.

---

## Thermal evaluation-horizon & promotion methodology correction

Status: DECIDED_LOCKED

Team Decision (Locked):
1. **Primary TEST Evaluation Horizon (2-Hour Multi-Step Trajectory):**
   - The primary holdout promotion comparison is the **2-hour / 8-step conditional forward trajectory projection** ($h = 1 \dots 8 \times 15\,\text{min}$ steps).
   - Forecast origin initialized from actual observed top-oil temperature ($T_{o,0} = T_{o,\text{obs}}$).
   - 8-step forward rollout without receiving future observed top-oil feedback during the rollout.
   - Scenario inputs follow constant forward hold matching Digital Twin scenario projection semantics.
   - Persistence baseline evaluated over the exact same 8-step rollout from the same origin ($\hat{T}_{o,t+h} = T_{o,t}$).
2. **Secondary Sanity-Check Metric (1-Step Closed-Loop):**
   - 1-step (15-minute) closed-loop prediction initialized from prior actual observation ($T_{o,k-1}$) reported separately as a diagnostic check.
3. **Methodological Correction Rationale:**
   - Comparing a 50-day free-running open-loop simulation against a 1-step 15-minute persistence baseline was flawed and asymmetric.
   - The grey-box ODE attains $+18.59\%$ MAE improvement on the fair 2-hour trajectory evaluation ($1.6527\,^\circ\text{C}$ vs $2.0300\,^\circ\text{C}$), beating persistence across all horizons $h=1 \dots 8$.
4. **Promotion Criteria:**
   - $\ge 5\%$ aggregate 2-hour trajectory MAE improvement vs 8-step persistence.
   - Trajectory signed bias $|\text{bias}_{\text{greybox}}| \le |\text{bias}_{\text{persistence}}| + 0.10\,^\circ\text{C}$.
   - Empirical 90% conformal path coverage within $[80\%, 98\%]$.
   - Calibrated parameters remain unchanged: $\beta_0 = 1.0880\,^\circ\text{C}, \beta_1 = 2.8979\,^\circ\text{C}, \tau = 0.5000\,\text{h}$, driver `rms_current_a`.

---

## One-shot test evaluation discipline

Status: DECIDED_LOCKED

Team Decision (Locked):
- Strict methodological sequence: `FIT → model/design decisions → CAL → calibration/threshold/uncertainty decisions → freeze → TEST`.
- After observing TEST results:
  - Do NOT change model family.
  - Do NOT change load driver.
  - Do NOT change parameter bounds.
  - Do NOT change thresholds.
  - Do NOT cherry-pick intervals.
  - Do NOT modify promotion criteria.
- "One-shot TEST" means **one frozen methodological decision cycle**, not literally one program execution. Deterministic reruns of the exact frozen methodology are allowed.

---

# Phase 4.3 — Thermal Runtime / Residual Handling

## Large residual interpretation (Evidence vs Diagnosis)

Status: DECIDED_PENDING_IMPLEMENTATION

Team Decision (Locked):
- A large thermal residual must NOT automatically be interpreted as model failure.
- Residual evidence and diagnosis must remain separate.
- A large residual may indicate:
  - genuine unusual asset behavior,
  - sensor bias,
  - mapping/unit/data-quality issue,
  - model underfit,
  - changed cooling behavior,
  - operating-regime shift,
  - extrapolation,
  - other data-quality problems.
- The system distinguishes:
  1. **Asset evidence**
  2. **Sensor/data-quality evidence**
  3. **Model-health evidence**
- `MODEL_MISSPECIFICATION_POSSIBLE` is an evidence-qualified **hypothesis**, not a confirmed diagnosis.
- Potential evidence labels: `UNUSUAL_THERMAL_BEHAVIOR`, `POSSIBLE_COOLING_DEGRADATION`, `POSSIBLE_SENSOR_BIAS`, `MODEL_MISSPECIFICATION_POSSIBLE`.
- The system must not claim a residual identifies the actual root cause without supporting evidence.

---

## Thermal model fallback & capability trust state

Status: DECIDED_PENDING_IMPLEMENTATION

Team Decision (Locked):
- Fallback is a **capability/trust state** (`THERMAL_MODEL:FALLBACK`), NOT an anomaly diagnosis.
- Two conceptual levels:
  - **Hard fallback:** missing/invalid thermal inputs, invalid temporal ordering, unsupported operating region, insufficient model applicability, numerical/model failure.
  - **Performance-degradation fallback:** entered when the model demonstrates sustained unsupported/error behavior (e.g. persistent residual bias, uncertainty coverage failure) according to calibrated rules.
- Fallback behavior:
  - Use top-oil persistence.
  - Use calibrated/empirical uncertainty where available.
  - Disable causal thermal what-if projection.
  - Disable thermal-model residual CUSUM.
  - Disable thermal-model-dependent recommendations.
- Non-negotiable Invariants:
  - MUST NOT erase existing anomaly evidence.
  - MUST NOT reclassify existing asset evidence.
  - MUST NOT turn `MODEL_MISSPECIFICATION_POSSIBLE` into a confirmed diagnosis.
  - MUST NOT disable unrelated electrical or direct protection monitoring.
  - State must be reversible when inputs/model return to valid conditions.
- Distinction:
  - `MODEL_MISSPECIFICATION_POSSIBLE` → evidence-qualified hypothesis.
  - `THERMAL_MODEL:FALLBACK` → capability/trust state.

---

# Phase 5 — Anomaly Detection

## Stuck-sensor detection

Status: PENDING_TEAM_DECISION

Detection must account for source resolution/quantization.

Decision required:
What constitutes a genuine stuck sensor versus normal quantized behaviour?

Do not invent a threshold solely from convenience.

---

## Evidence-family independence

Status: PENDING_TEAM_DECISION

The team must define which detector/evidence families are sufficiently
independent for escalation and health aggregation.

Do not assume that different signals automatically represent independent
evidence.

---

## CUSUM calibration and disablement

Status: VALIDATION_REQUIRED

CUSUM must be disabled when its calibration/promotion prerequisites fail.

Thresholds and persistence must be validated against calibration data and
controlled synthetic scenarios.

Do not claim real-world sensitivity or false-negative rates without
appropriate labels.

---

# Phase 6.1 — OTHI

## Evidence dependency groups

Status: PENDING_TEAM_DECISION

The OTHI implementation must account for correlated evidence.

The team must decide the dependency/lineage grouping used when multiple
signals describe substantially the same underlying condition.

Do not introduce arbitrary statistical deduplication without team approval.

---

## OTHI secondary coefficient

Status: VALIDATION_REQUIRED

The current 0.2 secondary-penalty coefficient remains provisional.

Validate:
- monotonicity,
- sensitivity,
- correlated-domain behaviour,
- scenario behaviour,
- missing-domain transitions.

Do not silently change the coefficient.

---

## Missing-domain behaviour

Status: PENDING_TEAM_DECISION

The team must decide how OTHI behaves when a previously available domain
becomes unavailable or stale.

The score must not silently improve merely because evidence disappeared.

Present options before implementation.

---

## Health-band hysteresis

Status: PENDING_TEAM_DECISION

Determine whether state/band hysteresis is required to prevent health status
chatter near thresholds.

Do not introduce hysteresis values without team approval.

---

# Phase 6.3 — Maintenance Policy

## Maintenance action-window provenance

Status: PENDING_TEAM_DECISION

Action windows such as immediate, within 30 minutes, 60 minutes, or
within 24 hours must not be presented as validated engineering limits unless
supported by authoritative evidence.

The team must decide which timings are:
- engineering-derived,
- operator-configured,
- demonstration defaults.

Unsourced timings must be explicitly labelled, e.g. `DEMO_DEFAULT`.

---

# API / Plan-wide

## Recommendations endpoint consistency

Status: VALIDATION_REQUIRED

Ensure the implementation plan, API implementation, tests, and documentation
use one canonical recommendations route.

Canonical route currently specified by the implementation plan:

`GET /v1/assets/{asset_id}/recommendations`

Do not introduce a second competing route without explicit team approval.

---

## Test/demo honesty

Status: VALIDATION_REQUIRED

Held-out test replay must be described as evaluated held-out replay.

Do not describe it as production evidence or imply that synthetic injected
faults demonstrate real-world fault-detection accuracy.

Synthetic scenarios remain explicitly synthetic.

---

# General Rule

If implementation encounters a new issue that requires a substantive
engineering decision, do not silently resolve it.

Add it to this document as:

`PENDING_TEAM_DECISION`

with:
- the decision required,
- why it matters,
- viable options,
- trade-offs,
- the phase at which it blocks implementation.

Then stop and report it to the team.
