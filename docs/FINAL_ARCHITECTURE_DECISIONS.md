This document locks the technical architecture for Track 2 of POWERNext AI 2026. **Status: implementation freeze.**

> **Document status:** Implementation freeze after final problem-statement, draft-workbook, and MVP consistency alignment (2026-10-03). It is written for the team that will implement and defend the system. The chosen design maximizes useful capability from the available telemetry while explicitly gating unsupported capabilities and refusing unsupported claims about failure probability, insulation condition, standards compliance, or remaining useful life.

> [!CALLOUT] 🔒
>
> **Architecture status:** locked for implementation. The only unresolved items are external facts that the final CPRI dataset or transformer metadata must supply. They are isolated under **Unavoidable uncertainties**.

> **Demo-data decision:** the final CPRI/hackathon-provided simulated dataset is the target dataset for the final demonstration. The Tripura transformer dataset is the locked development/calibration source. Both enter through the same canonical contract; no dataset-specific analytics logic is allowed outside its adapter.

The system is a stateful, reduced-order operational digital-twin prototype. It maintains synchronized asset state, predicts expected top-oil behavior, detects contextual deviations, simulates bounded operating scenarios, ranks current operating condition, generates advisory maintenance actions, and accepts operator feedback. In the hackathon it runs against chronological replay; the same core accepts live canonical events. It is not an autonomous controller and does not predict transformer failure or true RUL.

## Evidence language used in this design

| Label | Meaning in this document |
| - | - |
| **FACT** | An engineering relationship or directly observed value, with its scope stated. |
| **SOURCE** | A claim supported by an external standard, official publication, or peer-reviewed study. |
| **ASSUMPTION** | A declared condition required to run a method; never silently treated as measured fact. |
| **DERIVED** | A deterministic calculation from identified inputs. |
| **CALIBRATED** | A quantity fitted from a named chronological training or calibration partition. |
| **HYPOTHESIS** | A possible diagnosis or causal explanation that still requires inspection or tests. |

## Source-of-truth hierarchy and freeze rule

When sources conflict, use this order:

1. **Official CPRI problem statement and final hackathon dataset/schema** — authoritative for required outcomes, available fields, and final-demo behavior.
2. **This architecture freeze (`FINAL_ARCHITECTURE_DECISIONS.md`)** — authoritative for our chosen implementation methods, capability gates, interfaces, claims, and exclusions, unless an official CPRI requirement makes a direct conflict unavoidable.
3. **Actual observed signal semantics and verified transformer metadata** — authoritative for units, signal meaning, asset limits, rating, and calibration eligibility within the official dataset schema.
4. **The supplied draft condition-monitoring workbook** — supporting/reference evidence only; it does not override the final dataset or architecture and is not treated as telemetry unless a future source proves otherwise.
5. **External standards, papers, and datasets** — engineering references and optional benchmarks; they do not silently change the frozen architecture or establish compliance.

### Architecture Freeze Rule

After this implementation freeze, implementation agents may change code, tests, mappings, UI details, and configuration **without changing the architectural contract**. A proposed change that alters the twin definition, model family, capability gates, OTHI formula, anomaly stack, maintenance policy, data contract, scope exclusions, or public claims requires explicit human review before implementation.

## A. Final architecture

```text
CSV / REST / replay now; MQTT / OPC UA / Modbus gateways later
    → source adapters and versioned tag maps
    → immutable raw event log
    → canonical telemetry with units, timestamps, quality, and provenance
    → validation, deduplication, event ordering, and capability manifest
    → deterministic electrical and thermal feature derivation
    → stateful twin reducer and checkpoint store
    → expected-behavior model and two-hour conditional scenario projection
    → engineering checks + residual detector + two-sided CUSUM
    → anomaly episode manager
    → Operational Transformer Health Index and evidence grade
    → thermal exposure / conditional ageing gate
    → deterministic maintenance policy engine
    → versioned FactBundle
    → dashboard + 3D view, if built + PDF/CSV/JSON reports + optional constrained narrative
    → operator acknowledgement and inspection outcome back into twin state

Across every stage:
AssetProfile + model/config/rule registry + lineage log + deterministic replay + tests
```

| Component | Purpose | Inputs | Outputs | Chosen method and reason |
| - | - | - | - | - |
| Source adapters | Isolate source-specific names, units, timestamps, and semantics. | CSV rows, REST payloads, or future gateway messages. | `CanonicalEvent` or a quarantined record. | A small adapter interface plus declarative tag maps. It keeps analytics protocol-agnostic and makes the unknown CPRI schema a mapping task rather than a rewrite. |
| Raw event log | Preserve exactly what arrived. | Original record bytes and ingest metadata. | Append-only Parquet records and SHA-256 content hashes. | Required for audit, reprocessing, and dispute resolution. Raw records are never overwritten by cleaning. |
| Canonical telemetry | Give every source the same typed contract. | Adapter output. | Validated event envelope and measurements. | Long-form events with UCUM unit codes, OPC-UA-inspired quality severity, source and receive timestamps, and explicit provenance. Sparse signals and future protocols fit without adding columns to the contract. |
| Quality and ordering | Prevent invalid or ambiguous data from entering engineering logic. | Canonical events. | Accepted, uncertain, or quarantined events; data-quality episodes. | Deterministic validation, idempotent event IDs, conflict retention, event-time ordering, and watermarks. No silent imputation. |
| Capability evaluator | Enable only functions supported by current evidence. | Available signals, freshness, metadata, and model validation status. | `CapabilityManifest`. | Prerequisite gates plus capability flags are safer than assuming one fixed dataset. |
| Feature derivation | Calculate transparent engineering quantities once. | Good or explicitly usable observations plus `AssetProfile`. | Versioned `FeatureFrame`. | Pure functions for load proxy, phase imbalance, neutral ratio, P-Q-S consistency, residual inputs, and freshness. Every output carries lineage. |
| Twin reducer | Maintain the state needed at the next event. | Previous state, current event, profile, and versioned artifact bundle. | New `TwinState`, outputs, and audit record. | A deterministic state transition makes replay, rollback, comparison, and tests possible. |
| Expected behavior | Estimate what top-oil temperature should be under current load and ambient conditions. | Top-oil, ambient, load driver, timestamps. | One-step estimate, residual, and conditional path. | One physically constrained first-order grey-box thermal model. It captures thermal inertia with only three fitted parameters and is feasible with irregular 15-minute data. |
| Evidence engine | Detect invalid data and abnormal operation without confusing novelty with failure. | Observations, derived features, model residuals, configured limits. | Typed evidence items with severity and confidence. | Deterministic checks, robust residual thresholds, and two-sided CUSUM. Isolation Forest and supervised fault classification are excluded from the MVP. |
| Episode manager | Turn noisy evidence into stable incidents. | Evidence stream. | Stateful episodes and timelines. | Duration-based finite-state machine with hysteresis, corroboration, and recovery. It avoids alert flapping and preserves evidence. |
| Condition index | Summarize current operational condition without claiming insulation health. | Independent domain severities and evidence gates. | OTHI 0–100 or `unavailable`, status, driver, and grade. | A transparent nonlinear union of domain severities allows one severe or several moderate issues to matter. Data quality affects confidence, not physical condition. |
| Thermal exposure | Quantify temperature stress when prerequisites are present. | Credible hot-spot estimate, insulation class, and time. | Relative ageing rate, equivalent ageing hours, or a gated unavailable state. | IEC/IEEE-derived equations are used only when hot-spot and insulation class are supportable. Otherwise the system reports observed thermal exposure, not ageing or RUL. |
| Maintenance policy | Convert verified evidence into safe, auditable advice. | Episodes, OTHI domains, forecast crossings, and confidence. | Prioritized recommendations with rule IDs. | Versioned deterministic rules, precedence, suppression, and merge logic. No automatic protection or control. |
| FactBundle | Make all user-facing surfaces agree. | Current outputs and lineage. | Immutable structured facts with evidence references. | Dashboard, reports, 3D view, and optional narrative render the same facts instead of recomputing decisions. |
| Dashboard and 3D | Answer what is happening, what is expected, whether it matters, and what to do. | FactBundle and time-series APIs. | Operator views (Overview, Twin Analysis, Anomaly Timeline, Maintenance, Data / Model Card) and scenario requests. | React, MUI, ECharts, and React Three Fiber (P3 conditional). The 3D model is a component navigator linked to state, not decoration. |
| Reporting | Produce reproducible human and machine evidence. | A selected time range and FactBundles. | PDF, CSV, and JSON. | Deterministic templates and charts, including provenance and model limitations. |
| Feedback loop | Close the advisory twin loop safely. | Acknowledge, dismiss, inspection result, and action outcome. | `OperatorFeedbackEvent`. | Human-mediated bidirectional interaction improves the twin without exposing control endpoints. |

### Locked software stack

| Layer | Selection |
| - | - |
| Analytics/API | Python 3.12, FastAPI, Pydantic v2, NumPy, pandas, SciPy, scikit-learn for metrics/baselines only, and Pint for runtime unit validation. |
| Storage | Immutable Parquet through PyArrow plus DuckDB for local analytical queries; JSON/YAML for versioned profiles and rules. |
| Frontend | TypeScript, React, Vite, MUI, ECharts, Three.js, React Three Fiber, and Drei. |
| Reports | Jinja2 HTML, deterministic Matplotlib SVG charts, and WeasyPrint PDF; direct CSV and JSON exports. |
| Testing | pytest, Hypothesis for schema/property cases, FastAPI contract tests, and Playwright for the critical UI/report flow. |
| Packaging | Docker Compose with one API/worker service and one web service; pinned lockfiles and image digests. |

## B. Final digital twin definition

**Final definition.** The product is a synchronized, stateful digital representation of one transformer that combines current and historical telemetry, a reduced-order thermal model, persistent anomaly state, bounded scenario simulation, and human maintenance feedback to support diagnosis and advisory decisions.

**Maturity terminology.** We do **not assign a formal CIGRE maturity level** to the hackathon prototype. Our defensible description is: a **digital-twin prototype operating in chronological replay**, with conditional thermal-state projection, bounded advisory what-if analysis, and human-mediated feedback. Any comparison with external maturity frameworks is treated as a qualitative self-assessment only; it is not presented as an independently certified level. A one-way live feed is a digital-shadow-style deployment pattern; operator acknowledgement and inspection outcomes add human feedback to the application, but do not constitute a physical closed-loop control path. CIGRE and NIST are used as conceptual references, not as a basis for a formal maturity rating [S2, S3].

The state transition is:

```text
(TwinState_t, Outputs_t, Audit_t) =
    F(TwinState_t-1, CanonicalEvent_t, AssetProfile_v, ArtifactBundle_v)

ArtifactBundle_v =
    {schema, feature code, model, thresholds, rules, adapter map, software build}
```

`F` must be deterministic for the same ordered events and artifact bundle. An event can be replayed from the most recent checkpoint to reproduce the same state and output hashes.

### TwinState contents

| Namespace | Stored state |
| - | - |
| Identity and time | `asset_id`, `state_time_utc`, last processed event ID, event-time watermark, state sequence. |
| Current observations | Last accepted value, source time, receive time, unit, quality, and lineage reference for each signal. |
| Derived electrical state | Current load driver and reference, P-Q-S consistency, voltage and current summaries, phase imbalance, neutral ratio, and availability flags. |
| Thermal latent state | Last modeled top-oil state, time constant state, warm-up/gap status, current expected value, residual scale, and projection cache. |
| Detector state | Positive and negative CUSUM accumulators, persistence timers, cooldown timers, and drift counters. |
| Episode state | Open episode IDs, state, severity, evidence IDs, start/last-seen times, and recovery timers. |
| Condition state | Domain severities, OTHI value or unavailable reason, driving domain, evidence grade, and freshness. |
| Exposure state | Time-above-band accumulators and, only when enabled, equivalent ageing hours. |
| Advisory state | Active recommendation IDs, priority, acknowledgement, expiry, and linked feedback. |
| Version state | Schema, profile, model, calibration, rule, adapter-map, and code versions plus state hash. |

### What does not belong in TwinState

- Raw files, unbounded historical arrays, chart-ready series, PDF content, or LLM prose.

- Transformer metadata or thresholds duplicated from the versioned `AssetProfile` and rule registry.

- Training data, optimizer objects, or model-development notebooks.

- UI selection, camera position, report filters, or transient API state.

- A measurement silently filled with an estimate. Observed, derived, estimated, and assumed values remain different types.

### What the twin models and predicts

The twin models thermal inertia, current electrical operating context, quality/freshness, persistent deviations from expected thermal behavior, incident lifecycle, and operator feedback. It predicts a two-hour **conditional top-oil trajectory**, its empirical uncertainty band, and any crossing of a verified or clearly labeled configured temperature threshold under an explicit load and ambient scenario.

It does **not** claim to model internal electromagnetic fields, oil flow, mechanical deformation, dissolved-gas behavior, paper moisture, insulation degree of polymerization, all failure modes, failure probability, or RUL. A 3D mesh is a view of the state; it is not the physical model.

### Problem-statement scope reconciliation

The official problem statement lists fault prediction and remaining useful life (RUL) among possible analytics-layer functions. This implementation deliberately does **not** produce a numeric RUL, failure probability, or failure prediction. The supplied problem-statement inputs and current development/reference materials do not provide the transformer age/degradation history, insulation-condition variables, or failure/end-of-life labels required to make those outputs defensible. The system instead provides observable-condition assessment, abnormal-condition detection, thermal exposure, and a bounded two-hour conditional thermal projection. This is an explicit scope decision, not an omitted requirement.

## C. Final data contract

### Canonical event envelope

```json
{
  "schema_version": "1.0.0",
  "event_id": "uuid-v5-or-source-stable-id",
  "asset_id": "DT-001",
  "event_time_utc": "2026-10-02T12:15:00Z",
  "received_time_utc": "2026-10-02T12:15:03Z",
  "source": {
    "system": "tripura_csv",
    "adapter_id": "tripura_v1",
    "source_record_id": "row-17207",
    "source_uri": "dataset-relative-reference",
    "raw_sha256": "..."
  },
  "measurements": [
    {
      "signal_id": "top_oil_temperature",
      "phase": null,
      "value": 67.4,
      "value_type": "float",
      "unit_ucum": "Cel",
      "original_name": "OTI",
      "original_value": "67.4",
      "original_unit": "degC_assumed_by_source_map",
      "quality": {
        "severity": "GOOD",
        "flags": [],
        "source_code": null
      }
    }
  ],
  "event_quality_flags": [],
  "mapping_version": "tripura-map-1.0.0"
}
```

Only `schema_version`, `event_id`, `asset_id`, both timestamps, `source`, and at least one recognized measurement are required. A missing signal is absent; JSON `null` is used only where the schema explicitly permits it. A value with `BAD` quality is retained for audit but is never used by engineering calculations.

The source and receive timestamps mirror a proven industrial pattern: OPC UA associates a value with status and source/server timestamps, requires clients to check quality, and treats bad values as unusable [S14]. Units use UCUM codes to make machine exchange unambiguous [S18].

### Draft condition-monitoring workbook role

`Draft Data for Condition Monitoring.xlsx` is a reference/commissioning artefact, not a telemetry training dataset. It contains a single-sheet snapshot of voltage/current measurement checks, a 50 A current-trip test, three 60 °C temperature-trip trials, empty oil-leakage headings, empty GPRS/status communication headings, and an AI aspiration note. It has no timestamps or time-series history.

Implementation rules for this workbook are frozen as follows:

- `Rated` means the workbook's reference/injected reading in these acceptance tests; it is **not** transformer nameplate rating.
- The first measurement table calculates `DIFF` as `Rated - Software`; the trip tables use `Software - Rated`.
- The 60 °C temperature-trip sensor is unspecified and must not be mapped automatically to top-oil, winding, or ambient temperature.
- The workbook can support protection-setting/demo overrides and a measurement-tolerance reference; it cannot support thermal-model training, CUSUM calibration, fault classification, RUL, or statistical OTHI calibration.

These semantics are documentation inputs only. The Tripura time-series dataset remains the development telemetry source.

### Measurement registry

| Group | Canonical signal IDs | Canonical unit/type | Notes |
| - | - | - | - |
| Phase voltage | `voltage_l1_n`, `voltage_l2_n`, `voltage_l3_n`, `voltage_l1_l2`, `voltage_l2_l3`, `voltage_l3_l1` | `V` | The adapter must declare line-neutral versus line-line; never infer it from magnitude alone. |
| Current | `current_l1`, `current_l2`, `current_l3`, `neutral_current` | `A` | RMS semantics must be declared by the source map. |
| Power | `active_power_total`, `reactive_power_total`, `apparent_power_total` | `kW`, `kvar`, `kVA` | Phase variants are permitted with a phase field. |
| Power quality | `power_factor_total`, `frequency` | `1`, `Hz` | PF sign convention must be in the source map. |
| Thermal | `ambient_temperature`, `top_oil_temperature`, `winding_temperature_indicator` | `Cel` | WTI remains an indicator unless its sensing/thermal-image semantics are verified. It is not automatically a measured hot spot. |
| Oil and cooling | `oil_level_percent`, `oil_level_status`, `cooling_state`, `tap_position` | `%`, enum, enum, integer | Numeric oil level is accepted only when scale and semantics are known. |
| Protection/status | `top_oil_temp_alarm`, `top_oil_temp_trip`, `magnetic_oil_gauge_alarm`, `breaker_trip` | boolean | Stored and displayed, but sealed from model features and calibration. |
| Operator feedback | `recommendation_ack`, `inspection_outcome`, `action_outcome` | enum/text code | A separate event class; never masquerades as sensor telemetry. |

The registry is extensible by schema version. Unknown columns are preserved in raw storage and reported by the adapter, not silently discarded or guessed.

### Quality representation

`quality.severity` is one of `GOOD`, `UNCERTAIN`, or `BAD`. `quality.flags` is a set drawn from:

| Flag | Severity and handling |
| - | - |
| `MISSING` | No value; normally represented by absence. Never impute in canonical telemetry. |
| `UNKNOWN_UNIT` or `UNKNOWN_SEMANTICS` | `BAD`; quarantine the measurement until the source map is corrected. |
| `OUT_OF_RANGE` | `BAD` for impossible physical values; `UNCERTAIN` for asset-range exceedance that may be real. |
| `STALE` | `UNCERTAIN`, then unavailable at the hard stale limit. |
| `DUPLICATE_EXACT` | Deduplicate idempotently while retaining the raw record reference. |
| `CONFLICT` | `BAD` unless a configured source-precedence rule resolves it; retain all originals. |
| `CLOCK_ERROR` or `OUT_OF_ORDER` | Quarantine or reorder inside the watermark; late data triggers replay. |
| `GAP_BEFORE` | Current value can be good, but dependent model uncertainty is widened and warm-up may restart. |
| `SOURCE_UNCERTAIN` | Preserve the source's uncertain status and reason. |
| `MANUAL_OVERRIDE` | `UNCERTAIN`; visible to users and excluded from automatic model calibration. |

Staleness is asset-configurable. The default is warning after `max(2 × expected cadence, 10 minutes)` and unavailable after `max(4 × expected cadence, 60 minutes)`. For nominal 15-minute Tripura data this is 30 and 60 minutes.

### Separation of data classes

| Class | Examples | Storage rule |
| - | - | - |
| Observed | OTI, ATI, phase current, alarm bit. | Immutable canonical event with source provenance. |
| Configured | Rated kVA, cooling class, manufacturer limits. | Versioned `AssetProfile`, with source, verification status, and effective dates. |
| Derived | `sqrt(P²+Q²)`, current imbalance, relative load index. | Pure transform output with input IDs and transform version. |
| Estimated | Expected top-oil, projection band, estimated hot spot. | Model output with model/calibration version and evidence grade; never written as observed. |
| Latent | Thermal state, CUSUM accumulator, persistence timer. | TwinState only, checkpointed for replay. |
| Historical | Events, features, snapshots, episodes. | Parquet/DuckDB append-only analytical tables. |
| Decision | OTHI, episode severity, maintenance advice. | Versioned output record with evidence and rule IDs. |

### Locked derived feature definitions

Derived values never overwrite an observed field. They use separate signal IDs and carry all input event/measurement references.

```text
apparent_power_derived = sqrt(active_power_total² + reactive_power_total²)

power_factor_derived = active_power_total / apparent_power_derived
    only when apparent_power_derived is above a configured numerical floor

current_mean = (I_l1 + I_l2 + I_l3) / 3

current_magnitude_imbalance_pct =
    100 * max(|I_phase - current_mean|) / current_mean

voltage_magnitude_imbalance_pct =
    100 * max(|V_phase - voltage_mean|) / voltage_mean
    only for three values with the same line-neutral or line-line basis

neutral_current_ratio = neutral_current / max(I_eq, numerical_floor)

pqs_inconsistency =
    |apparent_power_observed² - active_power² - reactive_power²| /
    max(apparent_power_observed², numerical_floor)

thermal_residual = top_oil_observed - top_oil_expected
```

The voltage metric is deliberately called magnitude imbalance; it is not a negative-sequence voltage-unbalance factor because phase angles are unavailable. Derived apparent power or PF is used only when P and Q share timestamp, aggregation interval, and sign conventions. If topology or conventions are unknown, the feature is unavailable.

### AssetProfile

The profile contains identity, phase topology, nominal frequency, rated voltages and kVA, cooling class, insulation paper class, sensor inventory, expected cadence, manufacturer alarm/trip settings, verified operating limits, thermal parameters if supplied, source precedence, timezone, and maintenance criticality. Every field has `value`, `unit`, `source_document`, `verified_by`, `verified_at`, and `status = VERIFIED | UNVERIFIED | UNKNOWN`.

Rating is never inferred from the maximum observed load. If rating is absent, the system freezes the 95th percentile of the clean training load driver as `load_reference`; the resulting quantity is called **relative load index**, not per-unit load or percent loading.

### CapabilityManifest and tiers

The manifest is recomputed when data or metadata changes. Its locked structure is:

```text
asset_id, evaluated_at, evaluation_window,
highest_tier, available_signal_ids[], verified_metadata_ids[],
expected_cadence, current_freshness,
capabilities {
    capability_id: {
        enabled, evidence_grade, required_inputs[],
        missing_inputs[], disabled_reason_codes[],
        coverage_pct, model_status, extrapolation
    }
}, schema/profile/model versions
```

| Tier | Required evidence | Enabled capability |
| - | - | - |
| C0 Integrity | Timestamped event, asset ID, and at least one recognized signal. | Ingest, replay, quality, provenance, and raw/canonical reporting. |
| C1 Electrical | At least one usable power or current path; phase functions require three phases. | Loading proxy, P-Q-S checks, phase imbalance where possible, status rules, and electrical episodes. |
| C2 Thermal descriptive | Current top-oil or WTI with known units. | Thermal trends, direct limits, hours in bands, and thermal condition domain. No causal forecast is implied. |
| C3 Thermal predictive | Good top-oil, ambient, and load driver; sufficient history; promoted model. | Expected behavior, residual/CUSUM, two-hour conditional projection, threshold crossing, and what-if. |
| C4 Thermal exposure | C3 plus credible hot-spot estimate and verified insulation class. | Relative ageing rate and equivalent ageing hours. Still no RUL. |

Capabilities are also exposed as independent flags because a tier cannot express every sparse combination. Missing phase data disables imbalance only. Missing voltage does not disable a power-based load driver. Missing rating switches from per-unit load to a relative index. Missing ambient, load, or top-oil disables the calibrated thermal model and invokes the documented persistence fallback only when a recent top-oil observation exists. If temperature is absent, the twin remains C1 and useful for electrical state, data quality, alarms, episodes, reports, and feedback; it does not invent temperature.

## D. Final thermal and expected-behavior model

### Selected model

Use one **physically constrained first-order grey-box top-oil model**. First-order transformer top-oil dynamics are consistent with loading-guide models, while published distribution-transformer work shows that the thermal parameters are transformer-specific and that the oil time constant is best calibrated from data [S4, S5, S6]. A higher-order network or black-box model is not justified by the available semantics, time, or labels.

Define the thermal drive:

```text
If verified rated kVA exists:
    u_k = apparent_power_k / rated_kVA

Otherwise:
    u_k = load_driver_k / frozen_training_reference

where load_driver is selected from candidates:
    - Measured apparent power S (or sqrt(P² + Q²))
    - RMS-equivalent phase current I_eq = sqrt((I_l1² + I_l2² + I_l3²) / 3)
```

**Load Driver Selection Protocol (Locked):**
The selection between apparent power `S` and RMS-equivalent current `I_eq` is evaluated strictly on **FIT-only data** using a predeclared rolling-origin predictive metric (not in-sample fit error) assessing predictive accuracy and parameter stability across chronological FIT folds. Once selected on FIT, the winning driver is frozen before CAL. CAL is not permitted to switch the driver, and TEST is never used for driver selection (TEST remains a pristine untouched lockbox). Provenance and selection metrics are recorded in the model metadata.

The state update for irregular interval `Δt_k` hours is:

```text
theta_star_k = ambient_k + beta_0 + beta_1 * u_k²

alpha_k = 1 - exp(-Delta_t_k / tau)

top_oil_hat_k = top_oil_hat_k-1
                + alpha_k * (theta_star_k - top_oil_hat_k-1)
```

`beta_0 ≥ 0` is the fitted load-independent rise, `beta_1 ≥ 0` is the fitted load-related rise at `u = 1`, and `tau > 0` is the effective oil time constant. Squared drive is fixed rather than fitted because copper loss scales approximately with current squared and fitting an additional exponent is poorly identifiable from one operational series. This is a grey-box approximation, not a claim of IEC or IEEE compliance.

### Parameter sources and identifiability

| Quantity | Final source |
| - | - |
| Rating, cooling class, limits, insulation class | Verified AssetProfile only. Unknown remains unknown. |
| Load reference when rating is absent | 95th percentile of good training-only load driver, frozen with calibration version. |
| `beta_0`, `beta_1`, `tau` | Robust asset-specific calibration on FIT partition. |
| Initial thermal state | First good top-oil value after startup or a long gap. |
| Forecast load and ambient | Explicit scenario; default is persistence of the last good inputs. |

The model is promotable only if the fit partition contains at least 500 good points, at least seven calendar days, adequate load variation, no unresolved unit semantics, and at least 30 valid two-hour calibration origins. If the parameter solution sits on a bound, varies materially across rolling folds, or fails the holdout promotion tests, it is marked unidentifiable and the fallback is used.

### Calibration procedure & TEST discipline

1. Seal alarm, trip, and protection columns before feature construction. They are not used for filtering, fitting, thresholds, or model selection.

2. Deduplicate, sort by event time, and retain irregular `Δt`. Do not interpolate across long gaps.

3. Split each asset chronologically into 60% fit, 20% calibration, and 20% untouched test, with a two-hour embargo at both boundaries.

4. On **FIT (60%)**: Select load driver using $K=5$ expanding-window chronological rolling-origin predictive metrics. Fit `beta_0`, `beta_1`, and `tau` with bounded Huber loss ($\delta = 1.345 \cdot \sigma_{\text{fit}}$ where $\sigma_{\text{fit}} = 1.4826 \cdot \text{MAD}(\text{residuals}_{\text{fit}})$) over a deterministic log grid within the unified domain $\tau \in [0.5, 24.0]\,\text{hours}$, nonnegative coefficients ($\beta_0 \ge 0, \beta_1 \ge 0$), and a fixed local refinement inside the same $[0.5, 24.0]\,\text{h}$ bounds. Check parameter identifiability (including fold stability gate $CV(\tau) \le 0.60$ and boundary checks). Freeze model parameters and driver before CAL.

5. On **CAL (20%)**: Calibrate residual scales, CUSUM limits, and empirical block-conformal uncertainty intervals only (with measurement-resolution scale floor $s_h \ge 0.50\,^\circ\text{C}$ reflecting observed $\sim 1\,^\circ\text{C}$ integer quantization). Freeze all decision thresholds and uncertainty bounds before TEST.

6. On **TEST (20%)**: Promote once against the untouched test partition. Record all metrics and the exact data hash.

**TEST Lockbox Rule:**
The sequence `FIT → model decisions → CAL → calibration/threshold decisions → freeze → TEST` is strictly one-way. "One-shot TEST" means **one frozen methodological decision cycle**, not literally one program execution. Deterministic reruns of the exact frozen methodology are permitted. After observing TEST results:
- Do NOT change the model family.
- Do NOT change the load driver.
- Do NOT change parameter bounds or solver grids.
- Do NOT alter anomaly thresholds or CUSUM limits.
- Do NOT cherry-pick demo intervals.
- Do NOT modify the promotion criteria.

Long gaps greater than the hard stale limit terminate a residual sequence. The next good top-oil measurement reinitializes state and starts a warm-up period of `max(4 samples, tau)` before model residuals can escalate.

### Residual interpretation: Evidence vs Diagnosis

A large thermal residual must NOT automatically be interpreted as model failure. Residual evidence and physical diagnosis remain strictly separate. A large residual may indicate:
- Genuine unusual asset behavior (e.g. abnormal loading, external heat source);
- Sensor bias or drifting temperature transducer;
- Mapping, unit, or data-quality issue;
- Model underfit or unmodeled solar/wind effects;
- Changed cooling behavior (e.g. fan failure, radiator blockage);
- Operating-regime shift or load driver extrapolation;
- Other data-quality anomalies.

The system explicitly distinguishes:
1. **Asset evidence** (e.g. `UNUSUAL_THERMAL_BEHAVIOR`, `POSSIBLE_COOLING_DEGRADATION`);
2. **Sensor/data-quality evidence** (e.g. `POSSIBLE_SENSOR_BIAS`, `OUT_OF_RANGE`);
3. **Model-health evidence** (e.g. `MODEL_MISSPECIFICATION_POSSIBLE`).

`MODEL_MISSPECIFICATION_POSSIBLE` is an evidence-qualified **hypothesis**, not a confirmed diagnosis. The system refuses to claim a residual identifies the actual root cause unless corroborating evidence is present.

### Model fallback as a capability trust state

Fallback is a **capability/trust state** (`THERMAL_MODEL:FALLBACK`), NOT an anomaly diagnosis. It reflects whether the digital twin currently trusts its thermal ODE for predictive claims.

The engine implements two conceptual levels:
1. **Hard fallback:** Triggered by missing/invalid thermal inputs ($T_o, T_a$), invalid temporal ordering, unsupported operating regions, numerical ODE overflow/failure, or unpromoted model status.
2. **Performance-degradation fallback:** Entered when the operational model exhibits sustained, calibrated error behavior (e.g. persistent residual bias or uncertainty coverage breakdown) per frozen rules.

**Fallback behavior:**
- Fall back to last-value top-oil persistence with an empirically calibrated horizon-specific error band for expected-versus-observed display.
- Disable causal what-if scenario projection (`POST /v1/assets/{asset_id}/scenario`).
- Disable CUSUM tracking on model residuals.
- Disable thermal-model-dependent maintenance recommendations.

**Non-negotiable Fallback Invariants:**
- MUST NOT erase or overwrite existing anomaly evidence.
- MUST NOT reclassify existing asset evidence.
- MUST NOT turn `MODEL_MISSPECIFICATION_POSSIBLE` into a confirmed root-cause diagnosis.
- MUST NOT disable unrelated electrical monitoring (C1), direct protection rules, or data integrity checks (C0).
- Fallback state is reversible: when valid inputs and normal operating conditions resume, the model returns to active operational state.

### Uncertainty

Use a 90% **block-calibrated empirical path interval** for the eight 15-minute steps in the two-hour projection:

1. At each calibration origin, generate the same conditional forecast used in production: last good load and ambient held constant unless a scenario says otherwise.

2. Calculate absolute residuals for horizons 1 through 8 and a robust scale for each horizon.

3. Form non-overlapping two-hour blocks and use the maximum standardized residual in each block as its conformity score.

4. Take the finite-sample 90th percentile of block scores and expand each horizon by that score times its horizon scale.

5. Report realized marginal and whole-path coverage and mean width on the untouched test set.

Block conformal methods explicitly address serial dependence, but no unconditional 90% guarantee is claimed under regime change [S7]. The UI and reports therefore say **empirical 90% interval; test coverage X%**, not “90% confidence.” Quality problems, extrapolation beyond the calibrated load range, a gap, or a low evidence grade widen the band with a documented multiplier or disable the projection.

### Forecast meaning and horizon

The final forecast is a **two-hour conditional top-oil projection**, not a failure forecast. Two hours equals eight samples in the development data, is long enough for visible thermal inertia, and aligns with an operator action window used in prior transformer monitoring work [S17]. It remains a product choice, not a universal transformer constant.

Outputs are peak projected top-oil, empirical band, earliest threshold crossing or none, time above a threshold within the scenario, and the difference between baseline and user scenario. A threshold crossing is shown only for a verified asset limit or a conspicuously labeled demonstration threshold. The scenario always states its load and ambient assumptions.

### Baselines and promotion

#### Primary Operational Evaluation (2-Hour Multi-Step Trajectory)
The primary evaluation horizon on the untouched TEST lockbox is the **2-hour / 8-step conditional forward trajectory projection** ($h = 1 \dots 8 \times 15\,\text{min}$ steps):
- **Forecast origin:** Initialized from the actual observed top-oil temperature at the forecast origin ($T_{o,0} = T_{o,\text{obs}}$).
- **Forward rollout:** 8 steps forward without receiving future observed top-oil feedback during the rollout.
- **Scenario inputs:** Ambient temperature and load index held constant over the 2-hour window following standard Digital Twin scenario projection semantics.
- **Baseline comparison:** Persistence baseline is evaluated over the exact same 8-step horizon and origin ($\hat{T}_{o,t+h} = T_{o,t}$). Ambient + median rise and static regression baselines are likewise evaluated on the same 8-step trajectory.

#### Secondary Diagnostic (1-Step Closed-Loop Prediction)
As a secondary sanity-check diagnostic, 1-step (15-minute) closed-loop prediction is reported separately:
- Each valid step is initialized from the immediate prior observation ($T_{o,k-1}$).
- Evaluated against 1-step persistence ($\hat{T}_{o,k} = T_{o,k-1}$).

#### Evaluation-Methodology Correction Rationale
Comparing a multi-week/50-day free-running open-loop simulation error against a 15-minute 1-step persistence baseline was methodologically invalid and asymmetric. When evaluated fairly across identical forecasting horizons, the grey-box ODE outperforms persistence across all horizons ($h=1 \dots 8$) and attains an aggregate 2-hour path MAE improvement of **$+18.59\%$** ($1.6527\,^\circ\text{C}$ vs $2.0300\,^\circ\text{C}$).

#### Promotion Criteria
The model is promoted on TEST if:
1. **MAE Improvement:** 2-hour trajectory aggregate MAE improves on 8-step persistence by at least **5%** ($MAE_{\text{greybox}} \le 0.95 \cdot MAE_{\text{persistence}}$).
2. **Bias Criterion:** Absolute signed bias on the 2-hour trajectory is acceptable ($\le |\text{bias}_{\text{persistence}}| + 0.10\,^\circ\text{C}$).
3. **Conformal Coverage:** Test empirical 90% conformal path coverage falls within the expected $[80\%, 98\%]$ band.
4. **Identifiability Criterion:** Fitted parameters do not sit on artificial optimization bounds and satisfy stability across rolling folds.
5. **Scenario Safety:** No safety-critical threshold crossing is missed in labeled scenario tests.

Failure to promote downgrades capability (`C3` predictive capability disabled / fallback invoked); it does not stop the rest of the twin.


## E. AI/ML scope reconciliation

The official problem statement lists AI/ML models as an optional component of the Digital Twin Engine. The draft workbook contains an aspiration to implement AI for decision making. For this implementation freeze, **black-box ML forecasting and supervised fault-classification models are intentionally out of scope**. This is a deliberate scope decision, not an omission: the supplied workbook is not a telemetry training dataset, reliable fault labels are not established, and the first-order grey-box model plus deterministic evidence methods directly support the required monitoring and conditional thermal-prediction behavior with clearer physical interpretation.

ML tooling may still be used for non-model utilities such as metric calculation or benchmark analysis, but no ML model becomes part of the production decision path unless this architecture is explicitly reopened and a new evidence-based promotion decision is approved. The absence of black-box ML must not be described as “AI is unavailable”; the system's intelligence is provided by the calibrated grey-box model, statistical residual detection, engineering checks, stateful reasoning, and deterministic maintenance policy.

## F. Final anomaly engine

### Selected evidence stack

1. **Telemetry integrity:** units, ranges, timestamp behavior, staleness, duplication, conflicts, flatline, and cross-signal consistency.

2. **Direct observed status:** valid alarm/trip/protection bits. These describe observed events and are never called predictions.

3. **Engineering checks:** configured temperature/loading/voltage/frequency/PF limits and phase imbalance.

4. **Contextual thermal residual:** observed top-oil minus grey-box expected top-oil.

5. **Two-sided CUSUM:** persistent small positive or negative standardized residual shifts.

6. **Independent electrical context:** load, imbalance, neutral current, or power inconsistency used for corroboration and explanation.

This order is a trust hierarchy, not a score weighting. A bad sensor cannot create a critical asset-health alarm. A valid direct trip can. CUSUM is retained because it is designed to detect small persistent mean shifts [S8]. Isolation Forest is removed: with few reliable fault labels, mixed operating regimes, and stronger contextual residuals already available, it would add an opaque novelty score without a defensible mapping to condition or action. Supervised fault classification is also excluded.

### Residual and CUSUM

```text
r_k = observed_top_oil_k - expected_top_oil_k

z_k = (r_k - median_calibration_residual) /
      max(1.4826 * MAD_calibration_residual, sensor_resolution_floor)

Cplus_k  = max(0, Cplus_k-1 + z_k - 0.5)
Cminus_k = min(0, Cminus_k-1 + z_k + 0.5)
```

The reference value `k = 0.5` targets a persistent half-standardized-unit shift. The decision limit `h` is not copied from a textbook: a deterministic grid search on the calibration partition selects the smallest `h` that yields at most one false warning episode per seven asset-days while still detecting the injected 2-sigma drift scenario within one hour. If both requirements cannot be met, CUSUM is disabled and the manifest explains why.

Point residual thresholds are also calibrated against the normal calibration distribution and a false-episode budget. Demo defaults may be used before calibration only if labeled `DEMO_DEFAULT`; they can never be presented as manufacturer or standard limits.

### Evidence item

Every detector emits the same structure:

```text
evidence_id, asset_id, event_time, category, detector_id,
observed_value, expected_value, unit, threshold_or_band,
direction, severity, confidence, input_lineage[],
model/config/version IDs, reason_codes[], hypothesis_codes[]
```

`hypothesis_codes` can say `POSSIBLE_COOLING_DEGRADATION` or `POSSIBLE_SENSOR_BIAS`; it must not assert a root cause. Root-cause confirmation requires inspection or offline tests.

### Operator-facing categories

Use eight categories: `DATA_QUALITY`, `SENSOR_PLAUSIBILITY`, `THERMAL_DEVIATION`, `THERMAL_LIMIT`, `LOADING`, `PHASE_OR_NEUTRAL`, `VOLTAGE_PF_FREQUENCY`, and `PROTECTION_OR_OIL_STATUS`. `MODEL_DRIFT` is a maintenance category for the analytical system. Point, persistent, contextual, and collective are detector shapes stored as metadata, not separate menu categories.

### Deterministic fusion and episode state machine

Evidence is fused by rules, not by a pseudo-probability:

- `CRITICAL` immediately for a good-quality direct trip or a verified critical asset limit.

- Model evidence alone can reach `WARNING`, never `CRITICAL`.

- A non-protection critical episode otherwise requires two independent evidence families, for example persistent positive thermal residual plus high loading or valid oil alarm.

- Conflicting or bad measurements create a data-quality episode and suppress model-dependent asset escalation. They do not erase a separately valid trip bit.

- Multiple evidence items derived from the same source measurement count once for corroboration.

The duration-based state machine is:

```text
NORMAL
  → WATCH       qualifying evidence for 30 minutes, or one strong point deviation
  → WARNING     CUSUM trip, verified warning limit, or WATCH evidence for 60 minutes
  → CRITICAL    direct trip/critical limit, or WARNING plus independent corroboration
  → RECOVERING  all entry evidence below exit thresholds for 30 minutes
  → CLOSED      two continuous hours without qualifying evidence
```

A state can jump directly from NORMAL to CRITICAL for direct protection evidence. Entry and exit thresholds are separate; recovery requires clean duration rather than one good point. On a gap, the episode is frozen and marked `MONITORING_GAP`, not falsely closed.

### Alert and notification mechanism

An open `WATCH`, `WARNING`, or `CRITICAL` episode is surfaced immediately in the dashboard Alerts/Incidents panel, with severity, start time, evidence, current state, acknowledgement state, and linked maintenance advice. The hackathon prototype treats this in-dashboard mechanism as the authoritative notification path. Optional external notifications can be added later through an adapter; no external messaging service is required for the core demo.

### Validation with scarce labels

Real alarm/trip columns remain sealed until final evaluation. They may then be used as imperfect external event markers, with the warning that an alarm setting is not ground-truth failure. Validation combines false episodes per asset-day, lead/lag relative to recorded events, time to detect controlled injections, episode fragmentation, and expert review of the evidence trail. Synthetic scenarios test detector behavior but are always labeled synthetic and never used to claim real-fault accuracy.

## G. Final health and condition index

### Name and scope

The UI and reports use **Transformer Health Index (Operational)**, abbreviated **OTHI** for Operational Transformer Health Index. This satisfies the hackathon language while making its scope explicit. OTHI is a **rule-based composite operational index with engineering-configured thresholds; it is not statistically calibrated against health labels**. It is a 0–100 summary of the transformer’s **currently observed operating condition**, not a conventional whole-life asset health index and not an insulation-health score.

That distinction is necessary: established transformer health-index methods commonly use dissolved-gas analysis, oil quality, furan or degree of polymerization, dielectric tests, age, inspection, and component history [S9]. CIGRE recommends consistent scoring by failure mode linked to actions and timing, which supports the domain-and-rule approach used here [S10].

### Domains and severity

| Domain | Evidence included | Evidence excluded |
| - | - | - |
| Thermal | Direct temperature limits, expected-versus-observed residual, persistent thermal episode, projected limit crossing. | Insulation condition or fault probability. |
| Loading | Verified per-unit loading where rating exists; otherwise relative-load excursions clearly labeled as such. | A guessed rating. |
| Phase and neutral | Phase-current imbalance, neutral current, phase availability. | Phase conclusions from total-only data. |
| Voltage, PF, frequency | Verified operating bands and persistent deviations. | Utility-wide power-quality causation. |
| Oil and protection status | Valid oil level/status, temperature alarm/trip, magnetic oil gauge or breaker status. | DGA, oil chemistry, or inferred internal faults. |

Each domain severity `s_d` is in `[0,1]` and is produced by a versioned piecewise-linear rule between its normal, watch, warning, and critical thresholds. Threshold precedence is:

1. Verified protection/sensor settings.

2. Verified manufacturer/nameplate limits.

3. A requirement verified from an applicable standard for this asset and cooling/insulation class.

4. Asset-specific empirical deviation calibrated on normal history.

5. Clearly labeled demo default.

Within a domain, correlated evidence is deduplicated by lineage and the strongest supported severity wins. Across available independent domains:

```text
base_penalty = max(s_d)
secondary_penalty = 0.2 * sum(all s_d except the domain attaining base_penalty)
total_penalty = min(1, base_penalty + secondary_penalty)
OTHI = round(100 * (1 - total_penalty))
```

This is a transparent rule-based engineering aggregation, not a probability calculation and not a statistically calibrated health score. The worst current domain sets the base penalty; additional independent domain penalties contribute at the explicitly configured **0.2 secondary coefficient**. The coefficient is a visible product-policy parameter, not a learned weight and not a hidden statistical calibration.

| OTHI | State |
| - | - |
| 80–100 | Normal |
| 60–79 | Watch |
| 40–59 | Warning |
| 0–39 | Critical |

These are product policy bands, not IEC/IEEE limits. The domain thresholds beneath them carry the engineering source.

### Missing data, quality, and confidence

Missing domains are omitted, never scored as healthy or unhealthy. The UI always shows `available domains / possible domains`, the driving domain, and the evidence grade. A numeric OTHI is emitted only when:

- at least two current domains have medium-or-better evidence; or

- one valid direct protection/critical-limit domain is decisive.

Otherwise the value is `null` with **Insufficient current evidence** and domain-level observations are still shown.

Bad telemetry lowers evidence grade or makes the index unavailable; it does not lower physical health. At the warning stale limit, the last score remains visible with its timestamp and `STALE`. At the hard stale limit, the current numeric score is withheld.

| Grade | Meaning |
| - | - |
| A | Four or more current domains, verified limits/metadata where used, good coverage, and every contributing model promoted on holdout. |
| B | At least two current domains and no critical unknown; some empirical thresholds or relative loading may be used. |
| C | One domain, material metadata gaps, fallback model, extrapolation, or uncertain telemetry. Directional information only; aggregate number normally withheld. |
| U | No usable current evidence, hard stale, unresolved conflict, or pipeline failure. |

The grade is a deterministic evidence classification with reason codes, not a probability that the OTHI is correct.

## H. Final ageing and risk model

### What is included

Include thermal exposure in the MVP and implement a gated ageing calculation. Always available when temperature is good are peak temperature, time in configured bands, degree-hours above a verified threshold, and the two-hour conditional threshold projection. These are useful even when insulation properties are unknown.

With the currently supplied development/reference materials, standards-derived ageing is expected to remain **OFF** unless the final CPRI data or verified transformer metadata supplies credible hot-spot semantics and insulation class. The system still reports observed thermal exposure whenever temperature data are valid.

Standards-derived ageing is enabled only when all of the following are true:

1. A credible winding hot-spot estimate or verified hot-spot-equivalent measurement is present.

2. The insulation paper class is verified as non-thermally-upgraded or thermally-upgraded.

3. The relevant model and units pass validation.

4. No hard data-quality or extrapolation gate is active.

WTI is not automatically accepted as direct hot-spot truth. If its device semantics are verified as a thermal-image hot-spot indicator, it can support a model-estimated hot spot with the source and uncertainty shown. Otherwise it remains `winding_temperature_indicator` and ageing stays unavailable.

### Equations

For verified non-thermally-upgraded paper:

```text
V_k = 2 ^ ((theta_hotspot_k - 98) / 6)
```

For verified thermally-upgraded paper:

```text
V_k = exp(15000 / 383 - 15000 / (theta_hotspot_k + 273))
```

For either supported class:

```text
equivalent_ageing_hours = sum(V_k * Delta_t_k_hours)
average_relative_ageing_rate = equivalent_ageing_hours / elapsed_hours
```

These temperature-only relationships originate in loading-guide practice; IEC 60076-7 explicitly covers the effects of load, ambient temperature, operating temperature, and thermal ageing of mineral-oil-immersed transformers [S4]. Peer-reviewed literature also cautions that moisture and oxygen materially affect insulation ageing, so temperature-derived exposure is not complete life consumption [S11]. We therefore call the outputs **thermal equivalent ageing**, not remaining life.

### RUL decision

**Numeric RUL is unavailable in this project.** A defensible RUL would require at minimum verified asset age and design, insulation class, credible hot-spot history, moisture/oxygen or oil-paper condition evidence, furan/DP or equivalent ageing-state evidence, maintenance/failure history, a validated future duty profile, an end-of-life definition, and prognostic uncertainty. ISO 13381-1:2025 provides current general requirements for prognostics, but access to its exact clauses is paywalled and no compliance is claimed [S12].

The strongest replacement is a tuple of current operating condition, thermal exposure to date within the observed window, two-hour scenario threshold crossing, equivalent ageing hours when enabled, and prioritized inspection/maintenance advice. No failure probability is produced.

## I. Final maintenance engine

### Rule architecture

Rules are versioned YAML loaded at startup and validated against a schema. Each rule contains:

```text
rule_id, version, title, scope, prerequisites, conditions,
minimum_evidence_grade, severity, consequence_class,
priority, persistence, action_window, suppress_if, merge_key,
recommendation_template, rationale_template,
evidence_fields, source_reference, review_by, expiry
```

Priorities are `P0 SAFETY`, `P1 URGENT_INSPECTION`, `P2 PLANNED_ACTION`, `P3 MONITOR`, and `P4 DATA_OR_MODEL`. The engine emits an advisory action, reason, evidence IDs, owner role if configured, `action_window`, and the rule version. `action_window` is a qualitative urgency class such as `IMMEDIATE`, `WITHIN_24H`, `NEXT_AUTHORIZED_MAINTENANCE_WINDOW`, `MONITOR`, or `MODEL_REVIEW`; it is not an invented calendar deadline.

### Example locked rules

| Rule | Trigger | Priority | Action window | Advisory wording |
| - | - | - | - | - |
| `MNT-PROT-001` | Valid oil-temperature trip or breaker trip. | P0 | `IMMEDIATE` | “Follow the site-approved trip and isolation procedure. Qualified personnel should verify transformer and protection status before return to service.” |
| `MNT-THERM-002` | Positive thermal CUSUM warning plus high load or verified cooling alarm. | P1 | `WITHIN_24H` | “Arrange prompt inspection of cooling operation and temperature sensing. Review loading under the approved operating procedure.” |
| `MNT-FORE-003` | Upper empirical band crosses a verified temperature limit within two hours. | P1 | `WITHIN_24H` | “Review permissible load redistribution or reduction with the authorized operator; this is a conditional projection, not a trip command.” |
| `MNT-PHASE-004` | Persistent phase imbalance corroborated by neutral current. | P2 | `NEXT_AUTHORIZED_MAINTENANCE_WINDOW` | “Inspect phase loading, connections, and neutral path during the next authorized maintenance window.” |
| `MNT-PF-005` | Persistent low PF with good P/Q semantics. | P2 | `NEXT_AUTHORIZED_MAINTENANCE_WINDOW` | “Investigate downstream reactive demand and existing compensation settings; do not switch equipment from this application.” |
| `MNT-SENS-006` | Flatline, impossible step, or cross-signal inconsistency. | P2 | `MODEL_REVIEW` | “Inspect the identified sensor and mapping. Model-dependent conclusions are suspended until data quality recovers.” |
| `MNT-MODEL-007` | Residual median or interval coverage drift. | P4 | `MODEL_REVIEW` | “Review calibration and input mapping; continue direct engineering checks while the predictive capability is downgraded.” |

### Conflict resolution

1. P0 safety/protection advice is always shown first and cannot be suppressed by lower-priority rules.

2. Recommendations with the same `merge_key` are combined; the strictest urgency wins and all evidence reasons remain visible.

3. A data-quality rule suppresses only model-dependent recommendations that rely on the bad signal.

4. If actions appear incompatible, the system does not choose an operating action. It emits one escalation: “Qualified operations review required,” with both evidence sets.

5. Acknowledgement hides nothing from the audit trail. It changes status to acknowledged and waits for an outcome.

The product description is **condition-based and predictive maintenance decision support**. “Predictive” refers narrowly to expected-behavior residuals, thermal threshold approach, and conditional thermal projection. It never means failure prediction or numeric RUL.

## J. Final GenAI decision

**Include only as a very limited, optional explanation layer.** The single useful case is converting a validated FactBundle into a concise incident or condition summary. Calculation, thresholds, anomaly detection, OTHI, ageing, severity, and maintenance decisions remain deterministic.

The default and fallback are deterministic templates. If an LLM is enabled:

1. It receives an allowlisted FactBundle, not raw telemetry or hidden documents.

2. It must return structured sentences, each citing one or more `fact_id` values.

3. A validator rejects uncited sentences, numbers or units absent from the facts, forbidden claims such as “will fail,” and unknown entities.

4. Rejected, timed-out, or unavailable output falls back to the deterministic template.

5. LLM text is labeled “generated explanation,” never the authoritative engineering record.

This constrains hallucination but cannot guarantee semantic truth. Free-form operator Q&A, rule creation, RUL generation, and automatic maintenance decisions are explicitly excluded.

## K. Final 3D twin

### Selected implementation

Use **React Three Fiber over Three.js**, with a small optimized glTF model and `@react-three/drei` helpers. React Three Fiber is a React renderer for Three.js and therefore binds naturally to the existing React state and component model [S16]. No second frontend framework is introduced.

The model is a state-linked component navigator, not a physics simulation. It loads progressively; the rest of the dashboard works if WebGL is unavailable. Auto-rotation, decorative particles, and photorealism are excluded.

### Components and TwinState mapping

| 3D group | State mapping | Interaction |
| - | - | - |
| Tank and oil volume | Observed top-oil, expected top-oil, residual, thermal severity. | Select to open expected-versus-observed plot and thermal evidence. |
| Combined core and winding zone | WTI as indicator; estimated hot spot only when enabled; thermal exposure. | Toggle observed, expected, and scenario-at-horizon state. |
| L1, L2, L3 winding/bushing groups | Phase voltage/current and phase severity. | Select a phase to filter charts and evidence. |
| Neutral connection | Neutral current and corroborated imbalance episode. | Open phase/neutral evidence and maintenance advice. |
| Radiator/cooling group | Cooling state if observed; otherwise `UNKNOWN`. | Show cooling signal, thermal hypotheses, and inspection rule. |
| Conservator/oil-gauge group | Oil level/status and magnetic oil-gauge alarm when present. | Open oil/status evidence. |

Visual states are `NORMAL` muted blue/green, `WATCH` amber, `WARNING` orange, `CRITICAL` red, and `UNKNOWN` neutral gray with an explicit unknown badge. Color is never the only channel: selection panels show text, icon, value, unit, source, and timestamp. Estimated values use a dashed outline; observed values use a solid outline. The what-if view ghosts the current state and overlays the two-hour scenario state so users can see what changed.

### Minimum useful 3D scope

- One compressed GLB with named component groups.

- Five or more clickable state-linked component groups from the table above.

- State-driven color/material, unknown state, selection highlight, legend, and keyboard-accessible parallel component list.

- Click-to-filter the same time series, evidence, and recommendation shown elsewhere.

- One baseline-versus-scenario toggle.

The 3D view earns its place only if clicking a component changes the engineering context and if every color can be traced to a TwinState field and evidence ID. Component-level fault diagnosis, CFD, electromagnetic simulation, arbitrary animations, and an exploded CAD viewer are not part of the hackathon. If those criteria cannot be met without risking the core demo, the 3D layer is omitted and the same component/state information remains available in 2D.

## L. Final reporting system

### One facts pipeline

The reporting service consumes the same immutable `FactBundle` used by the dashboard, 3D view, and deterministic explanation templates. Reports never recalculate OTHI, severity, or recommendations. This prevents a dashboard/report disagreement and makes every statement traceable.

### Must-build reports

| Report | Audience and purpose | Contents |
| - | - | - |
| Transformer condition report | Executive first page plus engineer annex for a selectable range. | Current OTHI/status or withheld reason, evidence grade, top driver, active recommendations, trend summary, observed versus expected plot, projection assumptions, episodes, thermal exposure, data coverage, and limitations. |
| Anomaly event report | Operator/engineer record for one episode. | Timeline, first/peak/last evidence, observed/expected/band, state transitions, corroboration, hypotheses clearly labeled, recommendation, acknowledgement/outcome, and provenance. |
| Data and model card | Technical audit and handover. | Signal coverage, units and mappings, quality counts, capability manifest, split dates, baseline/model metrics, interval coverage, drift state, parameter provenance, and known limitations. |

Daily, weekly, and monthly summaries are presets of the condition report rather than separate implementations.

### Formats and generation

- **PDF:** deterministic Jinja2 HTML with Matplotlib SVG charts rendered by WeasyPrint in the container, with a checksum footer.

- **CSV:** selected observed and derived time series with quality and lineage reference columns.

- **JSON:** complete FactBundle, episode records, provenance manifest, and report-generation metadata.

Excel is a should-build convenience only; CSV is the stable tabular export. Users can select a bounded time range and a named asset. Report generation records source-data hash, selected interval, generation time, timezone, schema/config/model/calibration/rule/software versions, report template version, and the current limitations. Every chart distinguishes observed, derived, estimated, and unavailable data.

The executive page answers: current operating condition, what changed, principal evidence, immediate advisory action, confidence, and coverage. The engineer annex provides exact values, bands, episode timeline, quality gaps, model metrics, thresholds with sources, and audit IDs.

GenAI is not used in the signed/default PDF. An optional generated narrative may be downloaded separately or inserted in a clearly labeled appendix only after fact-ID validation. Deterministic content remains complete without it.

## M. Final integration architecture

### Adapter contract

The core engine accepts only `CanonicalEvent`. An adapter must:

1. Declare source identity, mapping version, timezone policy, expected cadence, and supported fields.

2. Preserve the raw record and stable source ID.

3. Map names, phases, types, units, source timestamps, and source quality without guessing.

4. Convert only declared units and retain original value/unit.

5. Emit one deterministic event ID and one canonical event, or a quarantined record with reasons.

6. Be idempotent and pass contract fixtures for missing, duplicate, conflict, bad unit, out-of-order, and schema-change cases.

A minimal Python interface is:

```python
class SourceAdapter(Protocol):
    adapter_id: str
    mapping_version: str

    def inspect(self, source: SourceRef) -> SourceDescriptor: ...
    def iter_raw(self, source: SourceRef) -> Iterator[RawRecord]: ...
    def canonicalize(self, record: RawRecord) -> CanonicalEvent | Quarantine: ...
```

Source-specific logic stays in adapters and declarative maps. Shared signal validation, feature derivation, models, rules, and outputs never inspect source column names.

### What is implemented and what is designed

| Interface | Hackathon status | Architecture |
| - | - | - |
| CSV | Implement | Batch adapter, mapping YAML, preview/validation, chronological replay. |
| REST | Implement | Canonical FastAPI REST interface with 12 endpoints: `POST /v1/telemetry`, `POST /v1/replay`, `GET /v1/assets/{asset_id}/state`, `GET /v1/assets/{asset_id}/history`, `GET /v1/assets/{asset_id}/episodes`, `GET /v1/assets/{asset_id}/recommendations`, `GET /v1/assets/{asset_id}/health`, `GET /v1/assets/{asset_id}/capabilities`, `GET /v1/assets/{asset_id}/model-card`, `POST /v1/assets/{asset_id}/scenario`, `GET /v1/reports/...`, and `POST /v1/feedback`. Authentication can be demo-scoped but the interface is versioned. |
| MQTT | Design, optional should-build adapter | Gateway subscribes to MQTT v5 topics and emits canonical events. MQTT is a lightweight publish/subscribe IoT transport [S15]. |
| OPC UA | Design only | Edge connector subscribes to nodes, preserves source timestamp and StatusCode, applies a tag map, and posts canonical events. OPC UA provides platform-independent industrial information models and secure interoperability [S13, S14]. |
| Modbus | Design only | Edge poller reads configured registers, applies scaling/word order, timestamps at the gateway, and emits canonical events. Modbus is a device/application messaging protocol, not the analytics schema [S19]. |
| SCADA historian | Design only | File, database, or OPC-UA export is mapped by the same adapter contract. No vendor-specific code enters the twin. |

### Batch, live, and replay behavior

- **Historical batch:** validate all records, sort per asset/event time, preserve duplicates/conflicts, then reduce chronologically.

- **Live:** accept canonical events through REST, buffer within a configurable 10-minute event-time watermark, update TwinState, and checkpoint.

- **Replay:** use the same reducer and clock abstraction at 1× or accelerated speed; outputs retain original event time and separate replay time.

- **Late event:** if inside the watermark, reorder before reduction; if later, restore the prior checkpoint and deterministically replay the affected segment.

For production, protocol connectors and a durable message broker sit outside the core; object storage or a historian replaces local Parquet, and a production time-series/relational store replaces single-node DuckDB. The canonical schemas, adapter maps, pure feature functions, model service, rule engine, evidence records, FactBundle, APIs, and frontend can survive productionization. DuckDB, local replay orchestration, demo authentication, and the single-process worker are prototype components.

### Example SCADA mapping

| Source tag | Canonical signal | Conversion | Quality/timestamp behavior |
| - | - | - | - |
| `TR01.OTI_PV` | `top_oil_temperature` | Source °C → `Cel`; no scale change. | Preserve source timestamp and map source quality to GOOD/UNCERTAIN/BAD. |
| `TR01.IA_RMS` | `current_l1` | Source A → `A`; phase L1 declared in map. | Reject if RMS semantics or unit are not documented. |
| `TR01.MOG_ALM` | `magnetic_oil_gauge_alarm` | Source bit → boolean. | Status bit remains observed evidence and is excluded from predictive features. |

## N. Final reliability architecture

Reliability means deterministic behavior, explicit limits, graceful degradation, and an auditable failure path—not perfect prediction.

### Evidence and confidence propagation

Every material output carries an `EvidenceEnvelope`:

```text
output_id, output_type, event_time, value/unit,
evidence_grade, reason_codes,
input_lineage_refs, freshness,
quality_summary, coverage_summary,
parameter_provenance, calibration_range,
extrapolation_flags, model/config/rule/code versions
```

Confidence is propagated by gates, not multiplication of invented probabilities. A dependent output cannot have a better grade than its weakest required input or an unpromoted model. A direct good-quality trip can still be high-confidence even when the thermal model is unavailable. Recommendations inherit the evidence grade of every condition they require and are suppressed below the rule's minimum grade.

### Failure-mode handling

| Failure mode | Detection | Deterministic response |
| - | - | - |
| Schema/type failure | Pydantic validation. | Quarantine record; continue other assets; expose count and reason. |
| Unknown unit/semantic | Mapping validator. | Do not convert or model; require mapping update. |
| Impossible range | Global physical sanity rule. | Mark BAD; preserve raw. |
| Asset operating exceedance | Verified asset threshold. | Keep as usable evidence if sensor quality is good; create condition evidence rather than deleting it. |
| Exact duplicate | Stable event ID/raw hash. | Process once; retain duplicate audit link. |
| Conflicting duplicate | Same asset/signal/source time, different values. | Mark conflict and quarantine unless explicit source precedence resolves it. |
| Out-of-order/late event | Event-time watermark. | Reorder or replay from checkpoint. |
| Short gap | Cadence monitor. | Continue latent state, widen uncertainty, mark gap. No observed value is filled. |
| Long gap/stale state | Hard stale timer. | Stop residual/CUSUM escalation, withhold current OTHI, reinitialize thermal state on recovery. |
| Model exception/nonfinite output | Runtime guard. | Disable model, emit `MODEL_FAILURE`, use persistence if possible, retain direct checks. |
| Calibration failure/drift | Promotion and rolling residual/coverage monitors. | Downgrade C3, stop model-dependent advice, request recalibration review. |
| Rule conflict | Priority and merge engine. | Safety first; otherwise escalate to qualified human review. |
| Report/LLM failure | Generation checksum/validator. | FactBundle and dashboard remain available; deterministic report retry or template fallback. |

### Reproducibility and auditability

- Pin Python/Node dependencies and build a versioned Docker image.

- Store source-data SHA-256 hashes, adapter-map hash, split boundaries, random seeds, package lockfiles, Git commit, and container digest.

- Version schemas, AssetProfiles, parameters, conformal calibration, thresholds, rules, FactBundle, and report templates.

- Use UTC internally and include display timezone explicitly.

- Use deterministic sorting and tie-breaking; avoid unordered reductions.

- Checkpoint TwinState with state sequence and hash; periodically replay from raw data and compare hashes.

- Keep every accepted, uncertain, rejected, and superseded record; never edit history in place.

- Append operator acknowledgements and outcomes as events.

### Drift monitoring

On each rolling seven-day window with enough points, compare residual median, MAD, load/ambient range, and empirical interval coverage with calibration. Trigger `MODEL_DRIFT` when median standardized residual exceeds 0.5 for three consecutive windows, interval coverage lies outside 80–97% for three windows, or more than 10% of model inputs are outside the calibrated range. These are initial product thresholds and must be shown as such; recalibration requires a new model version and promotion test.

## O. Final validation plan

### Chronological design

Per asset, after raw/canonical quality handling but before any learned statistic:

```text
first 60%  → model fit only
next 20%   → uncertainty, residual thresholds, CUSUM, policy calibration
last 20%   → untouched final test
```

Insert a two-hour embargo at both boundaries. Fit normalization references only on the first partition. The hackathon prototype models one transformer asset. (If a multi-asset dataset is ever supplied in a future extension, each asset must be split chronologically; never let future records or another asset's identity-specific parameters leak backward).

Alarm/trip/protection columns are physically removed from model matrices and calibration code paths. A test asserts that their names and descendants are absent. They are unlocked only after outputs are frozen for post-hoc comparison.

### Metrics

| Layer | Metrics |
| - | - |
| Data quality | Detection rate for seeded schema/unit/range/duplicate/conflict/gap cases; false quarantine rate on good fixtures. |
| Thermal point prediction | MAE, RMSE, median absolute error, mean bias, and error by load/ambient region at 15, 30, 60, and 120 minutes. |
| Uncertainty | Marginal and whole-path coverage, mean interval width, and coverage under in-range versus extrapolated inputs. |
| Anomaly/episodes | False watch/warning episodes per asset-day, time to detect, episode fragmentation, recovery time, and corroboration correctness. |
| OTHI/rules | Golden-case score/status/driver, missing-domain behavior, priority/merge/suppression correctness. |
| End to end | Deterministic output hash, API contract, report values versus API values, provenance completeness, and replay equivalence. |

### Legitimate controlled injections

The mandatory dynamic scenario injector is strictly limited to the five locked hackathon scenarios, applied only to a copy of held-out or synthetic scenario data and labeled `SYNTHETIC_SCENARIO`:

1. **Sensor spike**
2. **Stuck sensor**
3. **Persistent sensor bias/drift** (2-sigma drift for CUSUM validation)
4. **Sustained load step** (within and beyond calibrated range)
5. **Phase imbalance** (where required signals exist, tested with and without neutral corroboration)

Data-integrity conditions (scale/unit errors, timestamp shifts, gaps, duplicates, conflicting records) and direct alarm/trip/status activations remain dedicated deterministic validation fixtures rather than being forced into the dynamic scenario injector.

Dynamic cooling-degradation simulation and positive residual ramps are out of scope for the mandatory hackathon injector and reserved strictly as optional/future extensions.

These scenarios validate logic and sensitivity. They do not establish real-fault precision, recall, probability, or lead time.

### Test layers

- **Unit tests:** schema, unit conversion, every derived equation, irregular `Δt`, stale timers, quality gates, CUSUM, episode transitions, OTHI aggregation, ageing equations, rule precedence, and fact validation.

- **Contract tests:** each adapter mapping, REST request/response schemas, report schema, and frontend FactBundle types.

- **Integration tests:** raw row → canonical event → features → TwinState → evidence → episode → OTHI → advice → FactBundle.

- **Scenario tests:** all injections above plus missing-signal capability downgrades.

- **End-to-end tests:** fixture CSV replay through API and UI, expected chart/report values, feedback event round-trip, restart from checkpoint, and deterministic full replay.

### Minimum acceptance criteria

The system is “working” only when all of the following pass:

1. All required fields, units, and quality outcomes validate; no bad/unknown-unit value reaches a model.

2. Identical ordered input and artifact bundle produce identical state and output hashes.

3. Alarm/trip leakage tests pass and model feature manifests contain no protected status fields.

4. The primary thermal model meets its promotion tests; otherwise the capability manifest correctly falls back without false predictive claims.

5. The reported empirical 90% interval coverage and width match the untouched test computation exactly.

6. Every hard-limit and direct-trip golden scenario produces the intended severity and safe wording; no model-only evidence creates CRITICAL.

7. Every missing-field scenario enables only the documented capabilities and never fabricates a value.

8. CUSUM meets its calibration false-episode budget and detects the specified injected persistent shift within four nominal samples; otherwise it is disabled.

9. OTHI is withheld for weak/stale evidence, bad data does not lower physical condition, and the driving domain is always shown when a score exists.

10. Every recommendation and report claim resolves to source events, transforms, model/config/rule versions, and timestamps.

11. CSV replay, REST canonical ingest, checkpoint restart, and late-event replay pass end to end.

12. Dashboard, 3D component panel (if built), JSON export, and PDF show the same values for the same FactBundle.

## P. Final implementation scope

As established by `MVP.md` §25, the MVP implementation priority hierarchy is authoritative for sequencing under time constraints. The architecture defines the technical design for these capabilities while adhering strictly to the MVP priorities.

**Required deliverables:** working Digital Twin prototype, interactive dashboard, technical documentation (architecture, methodology, assumptions, user guide), complete source with execution instructions, and a short presentation plus live/recorded demo.

### Implementation priority tiers (authoritative from MVP §25)

#### P0 — Demo survival and safety gates
1. **Data ingestion:** Tripura CSV adapter, canonical schema conversion, raw-record preservation, source provenance, timestamp normalization, measurement/unit mapping.
2. **Canonical contract:** Long-form typed telemetry event envelope with UCUM units and quality severity.
3. **Quality handling:** Deterministic validation, idempotent deduplication, conflict retention, out-of-order quarantine/reordering, gap handling; no silent value fabrication.
4. **Replay:** Chronological deterministic replay clock with accelerated demo playback.
5. **TwinState:** Deterministic reducer over prior state, canonical event, and versioned artifact bundle; checkpointing.
6. **Electrical features:** Derived apparent power, power factor, phase-current magnitude imbalance, voltage magnitude imbalance, neutral-current ratio, P-Q-S consistency, relative load index.
7. **Thermal observation:** Ambient temperature, observed top-oil temperature, thermal exposure metrics.
8. **Promotion/fallback enforcement:** P0 gate enforcement; if promotion fails, enter `THERMAL_MODEL: FALLBACK` (persistence-based expected behavior, causal what-if disabled) without weakening criteria.
9. **Anomaly/evidence pipeline:** Direct engineering limit checks, direct protection status precedence, typed evidence generation with hypotheses.
10. **Scenario/fixtures:** Dynamic scenario injector for the 5 locked scenarios (spike, stuck, bias/drift, load step, phase imbalance); deterministic static data-integrity fixtures.
11. **OTHI:** Operational Transformer Health Index via Max + 0.2 Secondary aggregation with evidence gating and integer rounding.
12. **Maintenance rules:** Deterministic, versioned rules with P0–P4 priority, qualitative action windows, suppression, merging, and qualified-review escalation.
13. **Core dashboard:** 5 mandatory React views (Overview, Twin Analysis, Anomaly Timeline, Maintenance, Data / Model Card) adhering to UI honesty rules (no color-only states, clear distinction of observed/derived/estimated/unavailable values).

#### P1 — Core predictive and validation value
14. **Thermal calibration quality:** Chronological 60/20/20 split, two-hour embargo, robust Huber-loss parameter estimation.
15. **Uncertainty:** Empirical 90% block-calibrated path interval with reported test coverage.
16. **Two-hour conditional projection:** 8-step conditional top-oil projection under declared load and ambient assumptions; threshold crossing.
17. **CUSUM:** Two-sided CUSUM calibrated to $\le 1$ false warning episode per 7 asset-days and detecting 2-sigma drift within 1 hour (4 samples); explicit disablement if uncalibrated.
18. **Episode refinement:** Duration-based FSM with hysteresis, recovery periods, and corroboration logic.
19. **CPRI adapter hardening:** Alternate adapter fixture proving downstream analytics isolation.

#### P2 — Evidence and polish
20. **Reports:** Deterministic Condition Report, Anomaly Event Report, and Data/Model Card in PDF, CSV, and JSON formats consuming the authoritative FactBundle.
21. **Feedback beyond acknowledgement stub:** Auditable inspection outcomes and action logging into TwinState without automatic parameter changes.
22. **Model/data card refinement:** Comprehensive coverage, limits, and validation metrics disclosure.
23. **Checkpoint/late-event hardening:** Resilient checkpoint rollback and replay for late arrivals beyond the 10-minute watermark.
24. **Drift screen:** Rolling 7-day residual median and coverage drift monitoring.

#### P3 — Optional enhancement
25. **3D component navigator:** Conditional React Three Fiber component navigator linked to state; built only if value gate passes without risking core 2D dashboard.
26. **MQTT:** Gateway adapter subscribing to MQTT v5 and emitting canonical events.
27. **Constrained GenAI:** Fact-grounded natural-language summary citing `fact_id`s, validated against hallucinations.
28. **Excel export:** Optional convenience export alongside standard CSV.

### Canonical REST API surface (12 endpoints)

The backend exposes the 12 canonical MVP endpoints:
1. `POST /v1/telemetry` — Ingest canonical telemetry event.
2. `POST /v1/replay` — Start or control chronological replay.
3. `GET /v1/assets/{asset_id}/state` — Fetch current TwinState / FactBundle.
4. `GET /v1/assets/{asset_id}/history` — Query historical time series and features.
5. `GET /v1/assets/{asset_id}/episodes` — Retrieve anomaly episodes and event timelines.
6. `GET /v1/assets/{asset_id}/recommendations` — Fetch active maintenance recommendations.
7. `GET /v1/assets/{asset_id}/health` — Retrieve current OTHI score, domain severities, and evidence grade.
8. `GET /v1/assets/{asset_id}/capabilities` — Retrieve current `CapabilityManifest` (C0–C4 tiers and flags).
9. `GET /v1/assets/{asset_id}/model-card` — Retrieve model/data card metadata, calibration status, and limitations.
10. `POST /v1/assets/{asset_id}/scenario` — Execute bounded 2-hour what-if scenario projection (isolated from live state).
11. `GET /v1/reports/...` — Generate deterministic condition, anomaly, or model card reports (PDF, CSV, JSON).
12. `POST /v1/feedback` — Record operator acknowledgement, inspection outcome, or action feedback.

### Out of scope / Do not build
- Multi-asset comparison or fleet-scale dashboard (the hackathon prototype strictly monitors one transformer asset).
- Dynamic cooling-degradation simulation in the mandatory injector.
- Direct OPC UA, Modbus, or vendor-SCADA clients in the core week.
- Automatic switching, load control, protection, or closed-loop actuation.
- Numeric RUL, failure probability, insulation health, or standards-compliance badges.
- Isolation Forest, supervised fault classifier, deep neural forecast, reinforcement learning, or multi-model tournament.
- CFD/electromagnetic/finite-element simulation, full CAD viewer, or decorative 3D animation.
- Microservices, Kafka, Kubernetes, PostgreSQL, or an enterprise asset platform.
- Free-form LLM Q&A over engineering state or LLM-authored maintenance rules.

### Seven-day build order (Architectural guidance)

*Note: This high-level build order provides architectural sequencing guidance. As established by `MVP.md` §28, the separate Implementation Plan document (to be created next) is the authoritative owner of repository structure, implementation phases, task breakdown, dependencies, ownership, agent instructions, integration order, test gates, and daily milestones.*

| Day | Guidance outcome | MVP Priority alignment |
| - | - | - |
| 1 | Dataset audit, source map, canonical contract, quality engine, Parquet/DuckDB, and golden fixtures. | P0 |
| 2 | Feature functions, deterministic reducer, checkpoints, capability manifest, and baseline API. | P0 |
| 3 | Thermal model, baselines, chronological split, uncertainty calibration, and promotion report. | P0 / P1 |
| 4 | Evidence engine, CUSUM, episodes, OTHI, exposure gate, maintenance rules, and scenario tests. | P0 / P1 |
| 5 | 5-view UI, what-if, data/model card, and **conditional 3D value-gate decision**. | P0 / P3 |
| 6 | PDF/CSV/JSON reporting, REST ingest, feedback loop, provenance verification, and full replay. | P2 |
| 7 | CPRI-schema adapter drill, failure-mode tests, performance polish, user guide/methodology/assumptions/run instructions, demo script, and claim review. | P0 / Deliverables |

## Q. Final decision ledger

| Area | Final decision | Reason | Evidence/source | Confidence |
| - | - | - | - | - |
| Twin identity | Stateful operational digital-twin prototype in replay, with conditional thermal projection, bounded advisory what-if, and human-mediated feedback; no formal maturity level claimed. | Dynamic synchronization and model/state updates support the twin description while avoiding an unsupported external maturity rating. | [S2], [S3] | High |
| State transition | Deterministic reducer over previous state, canonical event, profile, and versioned artifacts. | Enables replay, audit, tests, and late-event correction. | Design decision consistent with [S3] trust concerns. | High |
| Canonical format | Long-form event envelope plus typed measurement array. | Handles sparse and changing signals across files and protocols. | OPC-UA-inspired status/timestamps [S14]; UCUM [S18]. | High |
| Required telemetry | Identity, event/receive time, source/provenance, and at least one known measurement only. | Capabilities should degrade rather than reject useful sparse data. | Design decision. | High |
| Missing data | Never fabricate or silently impute observations; gate capabilities. | Preserves meaning and prevents false confidence. | Design and safety requirement. | High |
| Rating absent | Do not infer rating from observed maxima; use a frozen training reference only as a relative index. | Operational maxima do not identify nameplate capacity. | Engineering inference; explicit design rule. | High |
| Capability model | C0–C4 prerequisites plus independent flags. | A tier alone cannot describe every sparse signal combination. | Design decision. | High |
| Thermal model | Three-parameter, first-order, physically constrained grey-box top-oil model. | Captures inertia and load heating with identifiable complexity. | [S4], [S5], [S6] | High |
| Fitted parameters | Fit `beta_0`, `beta_1`, `tau`; fix load exponent at 2. | Reduces confounding and reflects squared-current loss. | Engineering fact plus calibration choice. | Medium-high |
| Model fallback | Last-value persistence with empirical horizon bands; otherwise unavailable. | Honest, testable, and robust under missing inputs/model failure. | Baseline design. | High |
| Uncertainty | Block-calibrated empirical 90% path interval with reported test coverage. | Accounts for dependence better than random split; avoids a false coverage guarantee. | [S7] | High |
| Forecast horizon | Two-hour, eight-step conditional thermal projection. | Operator-oriented window with visible inertia; supported as a practical transformer-monitoring horizon, not universal law. | [S17] | Medium |
| Forecast claim | Temperature path, interval, exposure, and verified-limit crossing only. | Prevents thermal projection from becoming failure prediction. | Design rule. | High |
| Anomaly stack | Quality → direct status/limits → residual → CUSUM → independent context. | Interpretable evidence and safe precedence. | CUSUM [S8]; design decision. | High |
| AI/ML scope | Black-box ML forecasting and supervised fault classification are intentionally out of scope; ML remains available only for metric/benchmark utilities unless the architecture is reopened. | The PS permits AI/ML models but does not require a specific model family; supplied data/labels do not justify adding a black-box decision model to the frozen path. | Official problem statement + development-data audit + scope decision. | High |
| ML anomaly model | Remove Isolation Forest and supervised classification from MVP. | No defensible labels or action calibration; weak incremental value. | Method assessment; iForest background [S20]. | High |
| Fusion | Deterministic precedence and corroboration; no Bayesian or probability language. | Inputs do not support calibrated probabilities or independence assumptions. | Design decision. | High |
| Episode logic | Duration-based FSM with hysteresis, recovery, gaps, and direct critical jumps. | Prevents flapping and preserves incident context. | Design decision. | High |
| Index name | Transformer Health Index (Operational), OTHI. | Meets brief wording while limiting scope to observed operation. | Conventional HI evidence [S9], [S10]. | High |
| OTHI aggregation | `base=max(s_d)`; `total=min(1, base + 0.2*sum(other s_d))`; `OTHI=100*(1-total)`. | One severe domain drives the score while additional independent domains contribute a visible fixed secondary penalty. | Transparent policy decision; not a probability. | High |
| Weak evidence | Withhold numeric OTHI; show domains and unavailable reason. | A polished number is harmful when coverage is inadequate. | Design rule. | High |
| Bad telemetry | Reduce confidence or withhold; do not reduce physical health. | Data-system condition and asset condition are different. | Design rule. | High |
| Ageing | Include only gated thermal-equivalent ageing; otherwise report exposure. | Temperature-only ageing has strong assumptions and needs credible hot spot/insulation class. | [S4], [S11] | High |
| RUL | Unavailable; no numeric value. | Required degradation state, future duty, and end-of-life evidence are absent. | [S9], [S11], [S12] | High |
| Maintenance | Versioned deterministic rules with priority, merge, suppression, safe wording, and feedback. | Auditable decisions remain separate from prediction. | CIGRE scoring/action concept [S10]. | High |
| Predictive maintenance wording | “Condition-based and predictive maintenance decision support.” | Prediction is limited to thermal behavior and threshold approach, not failure. | Scope decision. | High |
| GenAI | Optional fact-grounded explanation only; templates authoritative. | Adds communication value without becoming engineering authority. | Design decision. | High |
| Dashboard | 5 core views (Overview, Twin Analysis, Anomaly Timeline, Maintenance, Data / Model Card), reports, and conditional 3D. | Directly answers operator questions within one-week scope. | Product decision. | High |
| 3D | Conditional React Three Fiber component navigator tied to state and scenarios; 2D fallback is complete. | Component context is useful only if it can be linked to evidence without threatening core reliability. | [S16] | Medium-high |
| Reports | Deterministic condition, event, and data/model reports; PDF/CSV/JSON (P2 implementation priority, Excel optional P3). | Covers executive, engineering, and audit needs from one FactBundle. | Design decision. | High |
| Core integration | Implement CSV and canonical REST (12 endpoints); architect gateway adapters for MQTT, OPC UA, Modbus, and SCADA. | Demonstrates openness without consuming the week on protocols. | [S13], [S14], [S15], [S19] | High |
| Development data | Keep Tripura as primary development data; audit semantics before use. | It contains relevant electrical and thermal indicators over a long 15-minute series. | [S22] | High |
| Final demo data | Use the CPRI/hackathon-provided simulated dataset as the final demo target through the canonical adapter. | The official problem statement explicitly requires the solution to work with simulated datasets provided during the hackathon. | Official problem statement | High |
| External data | Do not merge datasets. A Norwegian 2024 direct-monitoring dataset may be used only as a separate external robustness benchmark if needed; no parameters transfer and raw redistribution is not assumed. | It contains voltage/current, ambient, top-oil and winding-temperature measurements plus clamping-force data from a 40 MVA ONAN transformer in southern Norway. | [S21] | Medium |
| Data split | Per-asset chronological 60/20/20 with two-hour embargo. | Separates fit, calibration, and untouched evaluation. | Time-series design; [S7]. | High |
| Synthetic scenarios | Use controlled injection for logic/sensitivity only, clearly labeled synthetic. | Necessary for failure paths, but not real-fault accuracy evidence. | Validation decision. | High |
| Production path | Keep canonical contracts, reducer, models, rules, facts, APIs, and UI; replace local transport/storage/orchestration. | Protects hackathon investment without pretending DuckDB is a fleet platform. | Architecture decision. | High |

## R. What we are claiming

The following wording is safe for the presentation, demo, and documentation **only when the corresponding capability has passed its promotion/calibration gates**. If a gate fails, the UI and documentation use the documented fallback/disabled state instead:

- “We built a stateful transformer digital-twin prototype that updates deterministically from chronological telemetry and supports replay or live canonical events.”

- “When promoted, it combines engineering checks with a calibrated first-order grey-box thermal model rather than relying on a black-box classifier; otherwise it falls back to the documented persistence baseline.”

- “It estimates expected top-oil behavior and shows a two-hour conditional thermal projection under explicit load and ambient assumptions.”

- “When the thermal model is promoted, its 90% band is empirically block-calibrated, and we report the actual untouched-test coverage.”

- “When CUSUM passes its calibration gate, it detects persistent contextual deviations with robust residuals and CUSUM; otherwise CUSUM is explicitly disabled while direct checks remain active.”

- “It monitors voltage, current, loading, oil temperature, and ambient temperature when those signals are available, and reports an Operational Transformer Health Index for current observable operating condition, alongside coverage, driving domain, and evidence grade.”

- “It never silently fills missing measurements; capabilities degrade according to a visible manifest.”

- “It computes thermal-equivalent ageing only when hot-spot evidence and insulation class are adequate; otherwise ageing is disabled and it reports observed thermal exposure.”

- “Maintenance recommendations are deterministic, versioned, traceable, advisory, and subject to operator acknowledgement and inspection feedback.”

- “When the 3D value gate is met, the 3D model is an interactive component view of TwinState and what-if outcomes, not a decorative rotation or multiphysics simulation; otherwise the complete 2D dashboard remains the supported presentation.”

- “CSV and canonical REST are implemented; MQTT, OPC UA, Modbus, and SCADA connect through adapters without changing the analytics core.”

- “Every important output traces to source data, transformations, timestamps, configuration, model, rule, and software version.”

- “The Tripura dataset is the development source; any external transformer dataset is isolated to benchmarking and does not transfer asset parameters.”

- “The system provides condition-based and predictive maintenance decision support, where predictive refers to bounded thermal behavior and threshold approach—not failure prediction or numeric RUL.”

## What we must not claim

- IEC 60076-7, IEEE C57.91, ISO 13381-1, OPC UA, MQTT, Modbus, or other standards **compliance** merely because their concepts or equations informed the design.

- That WTI is a directly measured winding hot spot unless the instrument and semantics are verified.

- That a percentile-based load reference is transformer rating, per-unit loading, or percent nameplate load.

- That a 90% empirical interval guarantees 90% future coverage under any operating regime.

- Failure prediction, failure probability, time to failure, true RUL, insulation life remaining, or total loss of life.

- Whole-asset health, insulation health, DGA diagnosis, moisture/furan/DP condition, or every transformer failure mode.

- Root-cause diagnosis from a residual alone; cooling or sensor causes remain hypotheses pending inspection.

- Real-fault detection accuracy from synthetic injections or alarm bits.

- Autonomous control, protection, switching, or safe-to-operate authorization.

- Direct MQTT, OPC UA, Modbus, or SCADA support until the corresponding adapter/gateway has been implemented and tested.

- Production readiness, cybersecurity certification, fleet-scale availability, or reliability beyond the tests actually run.

- That the Tripura transformer is 1500 kVA, or that any unverified dataset field has a known unit/meaning.

- That GenAI output is verified engineering truth or that it makes maintenance decisions.

- That the 3D mesh is a thermal, fluid, electromagnetic, or mechanical simulation.

## Unavoidable uncertainties

1. The final CPRI file schema, signal names, units, sampling behavior, and label semantics are unknown until delivery (the digital twin prototype strictly scopes to a single monitored asset). The adapter and capability manifest isolate this risk.

2. Transformer-specific rating, cooling class, insulation paper class, manufacturer limits, and the physical meaning of WTI/OTI may be absent. Features that require them remain gated.

3. Actual model accuracy, interval coverage, CUSUM false-episode rate, and useful promotion status cannot be stated until the exact development files and final CPRI data have run through the frozen validation protocol.

4. If the thermal model fails promotion on the final data, the demo will operate in explicit fallback mode and will not claim causal thermal what-if or model-based predictive thermal recommendations.

5. A replay demonstration cannot prove live OT reliability or a real physical feedback loop. Those require deployment integration and operational governance.

## Reconciliation audit change log

This section records the reconciliation decisions aligning the architecture with the MVP specification and hackathon problem statement.

### Key reconciliation items:
1. **MVP Priority Tiers Adopted:** Section P and decision ledgers adopt the P0–P3 hierarchy defined in `MVP.md` §25 as authoritative for sequencing under time constraints.
2. **Canonical REST API Surface Harmonized:** The 12 canonical REST endpoints from `MVP.md` §15 are explicitly enumerated and locked.
3. **Single-Asset Scope Locked:** Multi-asset comparison is removed from the active scope; the hackathon prototype strictly models one transformer asset.
4. **Frontend Views Aligned:** Clarified the 5 mandatory views (Overview, Twin Analysis, Anomaly Timeline, Maintenance, Data / Model Card) and P3 conditional 3D component navigator.
5. **Injector Scope Strictly Limited:** Dynamic injector is locked to the 5 MVP scenarios (spike, stuck, bias/drift, load step, phase imbalance); data-integrity issues remain static validation fixtures; cooling-degradation simulation is de-scoped as future/optional.
6. **Excel Export Classified as P3:** Excel export is classified as P3 optional convenience functionality.
7. **CUSUM & Capability Harmonization:** Harmonized CUSUM calibration limits and capability tier definitions with the MVP specification.
8. **Implementation Plan Boundary:** Affirmed that the Implementation Plan is the subsequent document responsible for daily tasks, ownership, and milestones.

### Deliberate no-change architecture

Canonical event architecture, data-quality gates, deterministic twin reducer, first-order grey-box model family, persistence fallback, CUSUM disable rule, capability manifest, episode FSM, bounded what-if structure, FactBundle, reporting path, standards/compliance safeguards, optional fact-grounded GenAI, and deterministic maintenance policy remain locked.

## Sources

- **[S1]** CPRI, [POWERNext AI 2026 event notice](https://cpri.res.in/en/content/powernext-ai-2026-24-hour-hackathon-undergraduate-engineering-students-karnataka-manipal-0), 2026.

- **[S2]** CIGRE JWG A2/D2.65, [Digital twins for power transformers — concept and future perspectives](https://electra.cigre.org/347-august-2026/technical-brochures/digital-twins-for-power-transformers-concept-and-future-perspectives.html), 2026.

- **[S3]** NIST IR 8356, [Security and Trust Considerations for Digital Twin Technology](https://nvlpubs.nist.gov/nistpubs/ir/2025/NIST.IR.8356.pdf), 2025.

- **[S4]** IEC, [IEC 60076-7:2018 — Loading guide for mineral-oil-immersed power transformers](https://webstore.iec.ch/en/publication/34351). The public page verifies scope; this design does not claim clause-level compliance.

- **[S5]** IEEE Standards Association, [IEEE C57.91-2025 — Guide for Loading Mineral-Oil-Immersed Transformers and Step-Voltage Regulators](https://standards.ieee.org/ieee/C57.91/7163/). The exact standard is not reproduced here.

- **[S6]** A. Wang et al., [Top-oil temperature modelling by calibrating oil time constant for an ONAN distribution transformer](https://doi.org/10.1049/iet-gtd.2020.0155), IET Generation, Transmission & Distribution, 2020.

- **[S7]** V. Chernozhukov, K. Wüthrich, and Y. Zhu, [Exact and Robust Conformal Inference Methods for Predictive Machine Learning with Dependent Data](https://proceedings.mlr.press/v75/chernozhukov18a.html), COLT/PMLR, 2018.

- **[S8]** NIST/SEMATECH, [CUSUM Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm).

- **[S9]** [Power transformer health index and life span assessment: a comprehensive review](https://doi.org/10.1016/J.ENGAPPAI.2024.109474), Engineering Applications of Artificial Intelligence, 2024.

- **[S10]** CIGRE TB 761, [Condition assessment of power transformers](https://www.e-cigre.org/publications/detail/761-condition-assessment-of-power-transformers.html), 2019.

- **[S11]** M. Djamali and S. Tenbohlen, [Hundred years of experience in the dynamic thermal modelling of power transformers](https://doi.org/10.1049/IET-GTD.2016.1321), IET Generation, Transmission & Distribution, 2017.

- **[S12]** ISO, [ISO 13381-1:2025 — Prognostics, general guidelines and requirements](https://www.iso.org/standard/88029.html). Only the public scope was used; no compliance claim is made.

- **[S13]** OPC Foundation, [OPC Unified Architecture overview and concepts](https://reference.opcfoundation.org/specs/OPC-10000-1/full).

- **[S14]** OPC Foundation, [OPC UA DataValue and StatusCode](https://reference.opcfoundation.org/specs/OPC-10000-4/7.11).

- **[S15]** OASIS, [MQTT Version 5.0](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html), 2019.

- **[S16]** Poimandres, [React Three Fiber documentation](https://r3f.docs.pmnd.rs/).

- **[S17]** W. A. Castillo, R. T. Jagaduri, and P. K. Muralimanohar, [Implementation of a transformer monitoring solution per IEEE C57.91-1995 using an automation controller](https://doi.org/10.1109/CPRE.2012.6201252), 2012.

- **[S18]** UCUM Organization, [Unified Code for Units of Measure specification](https://ucum.org/ucum).

- **[S19]** Modbus Organization, [Modbus specifications](https://modbus.org/modbus-specifications).

- **[S20]** F. T. Liu, K. M. Ting, and Z.-H. Zhou, [Isolation Forest](https://ieeexplore.ieee.org/document/4781136), IEEE ICDM, 2008. Cited to document the excluded method, not to endorse it for this MVP.

- **[S21]** H. Bærug, I. Madshaven, and C. Espedal, [Supporting data for thermomechanical modelling of clamping force in power transformer in operation](https://doi.org/10.5281/zenodo.17223516), Zenodo, published 2025; dataset contains 2024 online direct-monitoring data from a 40 MVA ONAN transformer in southern Norway. It is an optional external benchmark only. [verified against the Zenodo record during the consistency audit]

- **[S22]** K. Ramesh et al., [Machine Learning Approach for Smart Distribution Transformers Load Monitoring and Management System](https://doi.org/10.3390/en15217981), Energies, 2022. This is the source study for the Tripura development data.
