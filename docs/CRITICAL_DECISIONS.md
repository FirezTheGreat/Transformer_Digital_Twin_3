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

Status: DECIDED_LOCKED

Team Decision (Locked):
- The thermal model may use either apparent power `S` or RMS-equivalent phase current `I_eq` as its load driver.
- This selection must be made strictly on **FIT-only data** using a predeclared rolling-origin predictive metric (not in-sample fit error).
- Criteria include predictive performance and stability across chronological FIT folds.
- Once selected: frozen before CAL; CAL cannot switch driver; TEST is not used for driver selection or model fitting.
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
4. **Promotion Criteria & Current Model Status:**
   - $\ge 5\%$ aggregate 2-hour trajectory MAE improvement vs 8-step persistence (Passed: $+18.59\%$).
   - Trajectory signed bias $|\text{bias}_{\text{greybox}}| \le |\text{bias}_{\text{persistence}}| + 0.10\,^\circ\text{C}$ (Failed: $+0.25\,^\circ\text{C}$ vs $+0.05\,^\circ\text{C}$).
   - Empirical 90% conformal path coverage within $[80\%, 98\%]$ (Passed: $97.33\%$).
   - Calibrated parameters: $\beta_0 = 1.0880\,^\circ\text{C}, \beta_1 = 2.8979\,^\circ\text{C}, \tau = 0.5000\,\text{h}$, driver `rms_current_a`.
   - Current status: `NOT_PROMOTED` (boundary $\tau = 0.5\,\text{h}$ and trajectory bias failure; `C3` predictive capability cleanly gated/disabled).

---

## Frozen Evaluation Discipline & Dataset Provenance Rules

Status: DECIDED_LOCKED

Team Decision (Locked):
- **Tripura Dataset Role & Historical Provenance:**
  - Tripura telemetry (`tripura_dt_01`) is the development, calibration, and unit-testing dataset for the project, not the final hackathon competition holdout.
  - During early Phase 4 development, the Tripura TEST partition was inspected while the evaluation methodology was being refined (specifically, an earlier 1-step diagnostic was evaluated before the 2-hour / 8-step forward trajectory was formalized).
  - Therefore, the Tripura TEST partition is accurately documented as a development/test evaluation partition, NOT a scientifically pristine, never-before-seen lockbox.
  - The implementation strictly adheres to the frozen one-way sequence:
    $$\text{FIT (fit/model)} \longrightarrow \text{CAL (calibration/uncertainty)} \longrightarrow \text{FREEZE} \longrightarrow \text{TEST (evaluate)}$$
  - No model parameters, load drivers, or loss scales are fitted on TEST.
- **Future-Proofing Rules for Future / Hackathon Holdout Datasets:**
  1. *Freeze before TEST:* All methodology, models, drivers, bounds, horizons, metrics, thresholds, uncertainty algorithms, and promotion rules must be frozen before evaluating on holdout TEST data.
  2. *No tuning against TEST:* Never use TEST performance to select or change model families, load drivers, parameters, bounds, horizons, metrics, thresholds, uncertainty intervals, exclusions, or promotion criteria.
  3. *Accept model weaknesses:* If TEST reveals a genuine model weakness, accept the result and allow capability gating / fallback to activate honestly, rather than tuning against TEST.
  4. *Software defect remediation:* If a verified software defect invalidates TEST (e.g. CLI crash, logging bug, indexing error, reporting typo), document the invalid run, fix the defect with the minimal code change, and rerun the *exact same* frozen methodology; do NOT redesign based on TEST results.
  5. *Burned TEST policy:* If TEST results are used to redesign or tune the methodology, that TEST partition is considered burned and an unseen holdout dataset is required for final scientific evaluation.
- **Deterministic Replay Authorization:**
  - Deterministic replay of held-out / TEST partition telemetry is explicitly permitted for live runtime simulation and interactive UI demonstration because replay ingests telemetry through the runtime state engine and does not retrain, calibrate, or modify model parameters or thresholds.

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

## Capability-specific thermal qualification architecture

Status: IMPLEMENTED

Team Decision (Locked):
1. **Replaced Monolithic Binary Promotion:**
   - Monolithic `PROMOTED / NOT_PROMOTED` is replaced by seven independent capability qualification dimensions in `ThermalModelQualification`:
     1. `parameter_interpretability` (`UNVERIFIED` on Tripura due to $\tau=0.5\,\text{h}$ boundary hit)
     2. `forecast_qualification` (`PENDING_VALIDATION` on Tripura; holdout test score not treated as fresh validation)
     3. `scenario_qualification` (`PENDING_VALIDATION` on Tripura)
     4. `residual_display_qualification` (`DESCRIPTIVE_ONLY` on Tripura)
     5. `residual_anomaly_qualification` (`NOT_QUALIFIED` on Tripura)
     6. `cusum_qualification` (`DISABLED` on Tripura)
     7. `maintenance_inference_qualification` (`DISABLED` on Tripura)
2. **Shadow Descriptive Mode (`DESCRIPTIVE_ONLY`):**
   - When telemetry is valid ($T_o, T_a, \text{Load}$), the first-order grey-box ODE steps continuously and calculates $\hat{T}_{o,\text{free-running}}$ and shadow residuals $r_k = T_{o,\text{obs}} - \hat{T}_{o,\text{free-running}}$ exposed under `TwinState.thermal_latent` with `trust_state = ThermalTrustState.SHADOW_DESCRIPTIVE`.
   - Exposed under Capability Manifest as sub-capability `C2:thermal_residual_shadow` with Grade B (descriptive shadow, not diagnostic).
3. **CUSUM & Anomaly Evidence Gating:**
   - When `cusum_qualification = DISABLED`, CUSUM accumulators remain frozen at 0 ($S^+=0, S^-=0$) to guarantee zero false drift alarms.
   - When `residual_anomaly_qualification = NOT_QUALIFIED`, no thermal deviation anomaly evidence is emitted.
4. **Independent CPRI Qualification:**
   - CPRI/future models must qualify each capability dimension independently based on explicit criteria; successful calibration does not automatically qualify all 7 dimensions.
   - Historical promotion reasons and parameter values are strictly preserved in the artifact without rewriting.
5. **Hard Telemetry Overrides:**
   - Missing/corrupted telemetry, physical impossibility ($T_o < T_a - 10\,^\circ\text{C}$), or gaps $> 1.0\,\text{h}$ immediately force `FALLBACK_PERSISTENCE`.

> **Summary Qualification Status (Tripura Artifact):**
> "The current Tripura thermal artifact has predictive evidence but is not physically/parameter-identifiably qualified; therefore descriptive thermal residuals may be exposed, while anomaly/CUSUM/maintenance inference remain disabled and predictive/scenario capabilities remain pending explicit qualification."

---

# Phase 5 — Anomaly Detection

## Stuck-sensor detection

Status: IMPLEMENTED

Decision (Locked):
- Stuck sensor detection checks for $N \ge 8$ consecutive identical readings under changing load ($\Delta \text{load} > 0.05$) or flatline of $M \ge 12$ consecutive identical values on active analog telemetry channels (e.g. OTI, active power, voltage).
- Configured as an engineering default (`threshold_provenance: "CONFIGURED_ENGINEERING_DEFAULT"`), accounting for source integer quantization floors ($s_{\text{floor}} \ge 0.50^\circ\text{C}$).

---

## Evidence-family independence & dependency grouping

Status: DECIDED_LOCKED

Team Decision (Locked):
- Evidence items must not simply be summed across signals without semantic lineage.
- Every `EvidenceItem` must support:
  - `condition_family`: identifies the underlying physical/operational phenomenon.
  - `domain`: one of the 5 canonical OTHI domains (`thermal`, `loading`, `phase_neutral`, `voltage_pf_freq`, `oil_protection`).
  - `root_source_event_ids`: immutable raw/canonical event references.
  - `upstream_evidence_ids`: causal/derivation graph references.
  - `derivation_type`: `DIRECT_OBSERVATION`, `DERIVED_FEATURE`, `MODEL_DERIVED`, `PROTECTION_DISCRETE`, `OPERATOR_ACTION`.
  - `quality_freshness`: timestamp and freshness status.
  - `rule_or_model_version`: version of the emitting engine/rule.
- **Within an evidence family:** retain the strongest qualified severity as the numeric penalty; other observations serve as corroboration/lineage. Transformed versions of the same condition (e.g., $I_{\text{phase}} \to I_{\text{eq}} \to \text{relative load}$, or $P, Q \to S \to \text{relative load}$) must not double-count.
- **Within a domain:** domain severity $s_d \in [0.0, 1.0]$ is the maximum severity across eligible, non-duplicative condition families in that domain. Multiple derived representations of the same condition are never summed.
- **Across domains:** secondary domain contribution is permitted only when the contributing condition family is semantically distinct (e.g., loading stress + observed thermal exceedance = two distinct families; load-derived thermal projection + loading = dependent and not double-counted; protection trip + temperature exceedance = one decisive protection family with temperature as corroboration).
- Offline statistical correlation may be analyzed for research/diagnostics, but MUST NOT silently alter runtime OTHI aggregation.

---

## CUSUM calibration and disablement

Status: IMPLEMENTED

Locked Rule:
- CUSUM $z_k$ drift detection operates under explicit capability qualification (`cusum_qualification`).
- On development/unqualified datasets (such as Tripura where $\tau=0.5\,\text{h}$ hits boundary and parameter interpretability is unverified), `cusum_qualification = DISABLED` and `residual_anomaly_qualification = NOT_QUALIFIED`.
- CUSUM accumulators remain frozen at 0.0 during disabled qualification, preventing false alarms and ensuring zero operational authority.
- Shadow descriptive residuals ($r_k = T_{o,\text{obs}} - \hat{T}_{o,\text{free-running}}$) are exposed descriptively with Grade B and hypothesis `UNQUALIFIED_SHADOW_EVIDENCE`, without influencing OTHI, fallback, or maintenance.

---

# Phase 6.1 — OTHI & Domain Aggregation

## Evidence dependency groups

Status: DECIDED_LOCKED

Team Decision (Locked):
- Evidence grouping follows the Evidence-Family Independence architecture specified above.
- The 5 canonical OTHI domains are strictly preserved:
  1. `thermal`
  2. `loading`
  3. `phase_neutral`
  4. `voltage_pf_freq`
  5. `oil_protection`
- No ungrounded domains (such as mechanical or dielectric/DGA) shall be fabricated from electrical/thermal telemetry.

---

## OTHI secondary coefficient ($0.2$)

Status: DECIDED_LOCKED

Team Decision (Locked):
- Algorithm identifier: `MAX_PLUS_SECONDARY_V1`.
- Secondary coefficient: `secondary_coefficient = 0.20`.
- Formula:
  $$\text{base\_penalty} = \max_{d}(s_d)$$
  $$\text{secondary\_penalty} = 0.20 \times \sum_{d \neq \text{base}} s_d$$
  $$\text{total\_penalty} = \min(1.0, \text{base\_penalty} + \text{secondary\_penalty})$$
  $$\text{OTHI} = \text{round}(100 \times (1.0 - \text{total\_penalty}))$$
- **Policy Status:** This is an explicit **PRODUCT POLICY** parameter, not an IEEE/IEC/CPRI universal constant. It is versioned and documented as such.
- **Mandatory Validation Properties:**
  1. Monotonicity: worsening any domain severity $s_d$ never improves OTHI.
  2. Permutation invariance: domain evaluation order does not alter the score.
  3. Max/tie invariance: ties in maximum severity are resolved symmetrically.
  4. Severe vs moderate: one critical domain ($s_d = 1.0 \implies \text{OTHI} \le 39$) dominates multiple mild deviations.
  5. Duplicate-family invariance: duplicate evidence within a family produces zero additive secondary penalty.
  6. Direct-protection behavior: a valid direct trip drives $\text{base\_penalty} = 1.0 \implies \text{OTHI} = 0$.
  7. Missing-domain anti-uplift: losing a domain never causes an artificial score uplift.
  8. Saturation: $\text{total\_penalty}$ is strictly clamped to $[0.0, 1.0]$, ensuring $\text{OTHI} \in [0, 100]$.
- **Fleet Comparability Note:** OTHI scores across assets with differing evidence coverage/tiers are not directly fleet-comparable unless accompanied by their Evidence Grade ($A/B/C/U$) and coverage manifest.

---

## Missing & Stale Domain Behavior (Hybrid Policy & Anti-Uplift Rule)

Status: DECIDED_LOCKED

Team Decision (Locked):
- Freshness thresholds must be derived dynamically from the asset's capability profile and expected cadence ($\Delta t_{\text{cadence}}$), NOT hardcoded to Tripura 15-minute intervals.
- Domain Freshness States:
  1. **CURRENT:** Fresh, valid telemetry within warning cadence threshold ($t_{\text{stale}} \le \max(2 \times \Delta t_{\text{cadence}}, 10\,\text{min})$). Counts toward current OTHI evidence gates.
  2. **WARNING_STALE:** Age exceeds warning threshold but within hard stale threshold ($t_{\text{stale}} \le \max(4 \times \Delta t_{\text{cadence}}, 60\,\text{min})$). Last severity held under `HELD_STALE` state; does NOT count as a fresh current domain for the numeric OTHI evidence gate; Evidence Grade downgraded; last-valid timestamp exposed.
  3. **HARD_STALE:** Age exceeds hard stale threshold. Domain is dropped from current computation.
- **Anti-Uplift Rule:**
  - *Loss of observability must never silently improve health.*
  - When evaluating current OTHI with missing/stale domains, also compute the counterfactual OTHI including the last uncleared abnormal domain state.
  - If missing evidence would make the asset appear healthier than the last-known uncleared abnormal state, withhold the numeric `current_othi` (`null` with reason `"Insufficient fresh evidence; last known condition was degraded"`), and expose `last_valid_othi` alongside the staleness details.
- **Protection & Episode Persistence:**
  - Latched direct protection trips remain active until an explicit, verified reset/clearing event is received.
  - Stale protection telemetry indicates loss of observability, NOT trip clearance.
  - Ongoing anomaly episodes do NOT close merely because telemetry drops out; they transition to `MONITORING_GAP` or retain state until fresh valid evidence confirms recovery.

---

## OTHI Health-Band Hysteresis & Operational Display

Status: DECIDED_LOCKED

Team Decision (Locked):
- No arbitrary numerical deadbands or invented score hysteresis shall be applied to the raw numeric OTHI.
- The underlying score remains the exact deterministic integer $\text{OTHI} \in [0, 100]$.
- Categorical health-band transitions (`NORMAL: 80–100`, `WATCH: 60–79`, `WARNING: 40–59`, `CRITICAL: 0–39`) in operational views are governed by **evidence episode lifecycle and persistence**:
  - Direct valid protection trips cause **immediate** transition to `CRITICAL`.
  - Non-protection worsening requires active qualifying evidence / episode persistence.
  - Recovery to a healthier operational band requires fresh valid evidence satisfying the episode recovery/clearing window ($30\,\text{min}$ recovery, $2\,\text{h}$ closure).
- The system exposes:
  - `raw_othi`: exact instantaneous calculation.
  - `raw_band`: direct band corresponding to `raw_othi`.
  - `operational_band`: persisted band reflecting active episode status.

---

# Phase 6.2 — Thermal Exposure & Standards-Derived Ageing

## Capability-Specific Thermal Exposure (C4) Architecture

Status: DECIDED_LOCKED

Team Decision (Locked):
- **C4 Thermal Exposure is NOT globally blocked by C3 Grey-Box Model Promotion.**
- Thermal exposure capabilities are gated independently:
  1. **Observed Top-Oil Exposure:** Always available whenever verified top-oil telemetry ($T_o$) and timestamps are valid. Integrates actual timestamp intervals ($\Delta t$), reports coverage gaps, time in temperature bands ($T_o > 85^\circ\text{C}, > 95^\circ\text{C}, > 105^\circ\text{C}$), and degree-hours.
  2. **Direct Hot-Spot Exposure & Standards-Derived Ageing:** Enabled when a verified direct hot-spot measurement exists AND an explicit insulation profile is verified—EVEN IF the C3 grey-box top-oil model is unpromoted or in fallback.
  3. **Model-Derived Hot-Spot Exposure:** Enabled ONLY when an applicable, validated thermal model is promoted (`C3_predictive = ENABLED`) with verified transformer parameters.
- **Supported Insulation Profiles (Enum):**
  - `UNKNOWN` (default; standards-derived ageing is gated/suppressed)
  - `CELLULOSIC_NON_THERMALLY_UPGRADED` (reference temp $98^\circ\text{C}$, IEC/IEEE Arrhenius or half-life formulation)
  - `CELLULOSIC_THERMALLY_UPGRADED` (reference temp $110^\circ\text{C}$, Arrhenius formulation)
  - `HIGH_TEMPERATURE_OR_HYBRID` (requires specific manufacturer thermal profile)
  - `OTHER_UNSUPPORTED`
- **WTI Contact Boundary:** Discrete binary WTI trip/alarm contacts MUST NOT be treated as continuous winding hot-spot measurements.
- **No Whole-Life RUL / PoF:** Exposure represents observed cumulative thermal stress and equivalent ageing hours ($L_{\text{eq}}$) over the observed telemetry window only. Total loss of life, remaining insulation life, and numeric RUL remain explicitly unsupported.

---

## Thermal Ageing Standard Edition & Profile Selection

Status: PENDING_TEAM_DECISION

Decision Required:
- Which specific standard edition and thermal profile shall serve as the default standards-derived ageing formula when enabled:
  - Option A: **IEEE Std C57.91-2011 / IEEE Std C57.91-2025** Arrhenius equation:
    $$F_{AA} = \exp\left(\frac{15000}{383} - \frac{15000}{\theta_{\text{HS}} + 273}\right)$$ (for thermally upgraded paper, reference $110^\circ\text{C}$).
  - Option B: **IEC 60076-7:2018** relative ageing rate equation:
    $$V = 2^{(\theta_{\text{HS}} - 98)/6}$$ (for non-upgraded paper) and corresponding modified Arrhenius for upgraded paper.
- **Constraint:** The implementation must record explicit standard identifiers (`standard_id: "IEEE_C57_91_2011"`, `edition: "2011"`, `profile_id: "THERMALLY_UPGRADED_KRAFT"`) in the metadata rather than generic unversioned strings like "IEEE formula".

---

# Phase 6.3 — Maintenance Engine & Action Provenance

## Maintenance Action-Window Provenance & Metadata

Status: DECIDED_LOCKED

Team Decision (Locked):
- Recommendation action windows must have independent, auditable provenance. No temperature or electrical limit standard shall be cited as the source of an operational response window unless the standard explicitly defines that response timing.
- **Provenance Types (Enum):**
  - `APPLICABLE_STANDARD_OR_GUIDE` (e.g. IEEE/IEC guide defining specific inspection protocols)
  - `MANUFACTURER_REQUIREMENT` (nameplate/O&M manual specifications)
  - `PROTECTION_OR_SITE_PROCEDURE` (utility safety/trip procedures)
  - `OPERATOR_POLICY` (utility maintenance schedule policy)
  - `ENGINEERING_POLICY` (internal utility engineering workflow rules)
  - `DEMO_DEFAULT` (default demonstration parameters, clearly labeled)
- **Recommendation Record Metadata Structure:**
  - `rule_id`, `version`, `title`, `priority` (`P0`..`P4`)
  - `action_window` (`IMMEDIATE`, `WITHIN_24H`, `NEXT_AUTHORIZED_MAINTENANCE_WINDOW`, `MONITOR`, `MODEL_REVIEW`)
  - `window_provenance_type` (one of the enum types above)
  - `window_source_reference` (specific document, section, or policy ID)
  - `source_version`, `asset_applicability`, `binding_vs_advisory`
  - `approved_by`, `effective_from`, `review_by`
- **Default Action Windows & Provenance:**
  - `IMMEDIATE`: `PROTECTION_OR_SITE_PROCEDURE` or `ENGINEERING_POLICY` (safety default).
  - `WITHIN_24H`: `OPERATOR_POLICY` or `DEMO_DEFAULT`.
  - `NEXT_AUTHORIZED_MAINTENANCE_WINDOW`: `OPERATOR_POLICY`.
  - `MONITOR`: `ENGINEERING_POLICY`.
  - `MODEL_REVIEW`: `ENGINEERING_POLICY` / internal model governance.
- Site/operator policies outrank demo defaults upon configuration.

---

## Maintenance Rule Hierarchy & Tripura Suppression Gating

Status: DECIDED_LOCKED

Team Decision (Locked):
- The deterministic P0–P4 rule hierarchy is locked with the following specific trigger, priority, and wording refinements:
  - `MNT-PROT-001` (P0 / `IMMEDIATE`): Triggered by verified protection/trip contact. Wording: *"Follow site-approved trip and isolation procedure. Qualified personnel should verify transformer and protection status before return to service."* (Safety attention, NOT confirmed physical destruction).
  - `MNT-THERM-002` (P1 / `WITHIN_24H`): Model/CUSUM-derived thermal recommendation. **Suppressed on Tripura** because `cusum_qualification = DISABLED` and residual anomaly qualification is unpromoted. Active only on qualified assets.
  - `MNT-FORE-003` (P3 / `MONITOR` or P1 escalation): Upper empirical uncertainty-band crossing alone triggers **P3 Monitor/Review**. Central forecast crossing a verified operational limit escalates to **P1**.
  - `MNT-PHASE-004` (P2 / `NEXT_AUTHORIZED_MAINTENANCE_WINDOW`): Persistent, quality-verified phase imbalance corroborated by neutral current.
  - `MNT-PF-005` (P3 / `MONITOR`): Low power factor. Framed as downstream reactive demand / power factor correction review (P3), NOT intrinsic transformer deterioration.
  - `MNT-SENS-006` (P4 / `MODEL_REVIEW`): Sensor flatline / plausibility fault. Default P4 data/model workstream; escalates only if safety-critical.
  - `MNT-MODEL-007` (P4 / `MODEL_REVIEW`): Model residual or uncertainty coverage drift. Directs model/calibration review.
- **Suppression & Merging Rules:**
  - Bad data suppresses only recommendations dependent on that specific bad signal; NEVER suppress P0 protection advice.
  - Merge compatible recommendations sharing a `merge_key` (e.g. within same condition family), retaining all supporting rule IDs and evidence links, adopting the strictest compatible action window.
  - Incompatible recommendations must not be silently collapsed; emit an escalation requiring qualified human review.

---

# Phase 6.4 — Operator Feedback & Audit Semantics

## Operator Feedback Ledger & Lifecycle Semantics

Status: DECIDED_LOCKED

Team Decision (Locked):
- Feedback is stored in an **append-only immutable audit ledger** (`OperatorFeedbackEvent`).
- **Feedback Action Semantics:**
  - `ACKNOWLEDGE`: Workflow state update only; recommendation remains active with acknowledged flag.
  - `DISMISS`: Dismisses the *specific active recommendation instance*; requires `actor_id`, `reason_code`, `rationale`, and `timestamp_utc`. Does NOT delete or modify underlying historical evidence or telemetry.
  - `INSPECTION_OUTCOME`: Records physical inspection findings as **new SOURCE evidence** entering the twin state.
  - `OVERRIDE`: Advisory override requiring authorized role, explicit rationale, and expiry/review timestamp.
- **Safety Invariants:**
  - P0 Safety / Protection recommendations CANNOT be silently or permanently dismissed without documented resolution.
  - If an underlying abnormal condition recurs or persists past the closure window after dismissal, a NEW recommendation instance is generated.
  - Historical telemetry, derived features, evidence items, and calculated OTHI records are NEVER rewritten by operator feedback.
  - Feedback does NOT automatically trigger online model retraining or threshold modification during the hackathon.

---

# API & Documentation Consistency

## Canonical Recommendations Endpoint Route

Status: DECIDED_LOCKED

Team Decision (Locked):
- The canonical recommendation endpoint is strictly asset-scoped:
  `GET /v1/assets/{asset_id}/recommendations`
- All documentation, implementation files, API routers, and test suites must use this exact route consistently.
- Recommendations cite explicit source and provenance metadata (`window_source_reference`, `provenance_type`), not blind standard citations for non-standard operational decisions.

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
