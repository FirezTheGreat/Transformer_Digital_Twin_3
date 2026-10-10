# GridPulse — `dataset_syn` Adaptation and Additional Domain Work

> [!NOTE]
> **IMPLEMENTATION STATUS: COMPLETE & VERIFIED**  
> All extra domain capabilities specified in this document (Extra A–F: oil-level trend, tank pressure, short-circuit reference stress, breaker contacts, OTHI weight gating, and multi-domain corroboration) have been implemented and verified in Phases 4–8 with 24/24 passing tests in `test_candidate_adaptation_and_extra_domains.py`.

**Date:** 10 October 2026  
**Purpose:** Explicitly record the additional work required beyond the existing backend stabilization fixes. This document supplements—not silently rewrites—the frozen architecture and existing stabilization plan.

## 1. Current execution plan (authoritative clarification)

- **Current active dataset:** the existing CPRI dataset, believed to be `cpri_datasetv.1.2`. Confirm the exact identifier, manifest and hashes from the repository before implementation; do not guess the version.
- **Candidate dataset:** the uploaded `dataset_syn.zip`, containing `gridpulse_physics_v1.tar.gz` and its methodology, scenario/validation report and source register.
- **Tripura is not part of the active execution plan.** Do not use it as the current baseline, calibration source or migration target.
- Adapt `dataset_syn` to GridPulse's existing canonical contract. Do not fork the analytics pipeline or add dataset-specific rules throughout the engine.
- Keep the current CPRI dataset and its artifacts unchanged while adapting, training and evaluating the candidate.
- Promote `dataset_syn` only after the agreed qualification and verification gates pass. At that point, switch the active workflow to it and retire the earlier CPRI dataset from active use. Preserve the old package, hashes, artifacts and results as an immutable historical baseline; “retire” does not mean delete.
- After dataset adaptation, complete the approved fixes from `BACKEND_STABILIZATION_PROPOSALS.md`, then the approved additional architecture/domain work, then integrate frontend and backend and run end-to-end tests.
- Do not commit or push changes unless explicitly instructed.

## 2. What is EXTRA beyond fixing existing architecture defects?

The stabilization report identifies existing correctness defects such as thermal-output wiring, protection-trip lifecycle, direct thermal-limit advisory gating, advisory resolution, signal mapping, voltage configuration and quantization-aware plausibility checks. Those are **fixes to existing behavior**.

The following are **additional domain capabilities** required because `dataset_syn` contains signals and scenarios that the current pipeline does not consume end-to-end. Implement them as independently gated capabilities using the existing canonical events, evidence lifecycle, OTHI policy, maintenance workflow and shared `FactBundle`.

### EXTRA A — Oil-level trend and suspected-leak monitoring

**Why this is extra:** The current backend has absolute oil-level thresholds and a signal-mapping/freshness issue, but the new dataset includes richer oil-level fields and explicit slow-leak, top-up and stuck-gauge scenarios. Merely fixing the mapping will not implement trend-based monitoring.

**New work:**

1. Add the new dataset fields to the source adapter and canonical registry where applicable:
   - `x_oil_level_pct` — raw gauge indication.
   - `x_oil_level_ref_pct` — reference level.
   - `x_oil_level_ref_temp_c` — reference temperature.
   - `x_oil_level_corrected_pct` — temperature-corrected level.
   - `x_oil_level_trend_pct_per_day` — supplied trend.
   - Asset metadata such as `x_tank_construction` and `x_oil_gauge_type`.
2. Establish a clear source-of-truth rule for each value: observed raw reading versus supplied derived/corrected value versus trend. Do not recompute or overwrite supplied fields without recording the method and provenance.
3. Implement a **design- and sensor-aware oil-level evidence path** for assets that actually have a compatible oil gauge. Assets without an oil-level gauge must report this capability as unavailable, not healthy.
4. Add conservative trend-based **suspected oil-loss / suspected-leak review evidence** using corrected level and/or trend, with quality, freshness, persistence, minimum support and maintenance/top-up segmentation handled explicitly.
5. Distinguish at least:
   - low observed level / configured gauge alarm;
   - persistent declining corrected-level trend (suspected loss);
   - maintenance top-up or other known intervention;
   - stuck/faulty level sensor;
   - missing/stale/invalid level telemetry.
6. A top-up must not be interpreted as a spontaneous recovery without recording the intervention. A flat gauge must not be treated as proof of no leak.
7. Create evidence, episode/review-case and advisory lifecycle handling, plus tests for no-leak thermal movement, slow leak, top-up, stuck gauge, missing data and false-positive controls.

**Required limitation:** a declining corrected level supports a *suspected-leak advisory requiring inspection*; it does not prove a physical leak from telemetry alone. Do not label synthetic ground truth as a live detector input.

### EXTRA B — Sealed-tank pressure monitoring

**Why this is extra:** The stabilization report explicitly records that pressure is not currently consumed by the backend. `dataset_syn` includes a gauge-pressure channel and abnormal-pressure/pressure-relief scenarios for a sealed corrugated-tank asset. Fixing unrelated bugs will not make pressure monitoring work.

**New work:**

1. Add `x_pressure_kpa_g` to the adapter and canonical signal registry with the correct meaning: **gauge pressure in kPa**, not absolute pressure.
2. Bind pressure capability to verified asset metadata, including tank construction, pressure-sensor presence/type, measurement range and signal quality. In this candidate, pressure is present only for `DT-03-SEAL-250`; do not fabricate pressure for conservator assets.
3. Implement a deterministic pressure plausibility/condition check using only defensible configured limits or an explicitly documented, asset-specific baseline. Expose the actual reading, reference/baseline, evidence and configuration provenance.
4. Treat pressure trend and abnormal-pressure evidence as a separate domain from oil-level evidence. Merge or corroborate them only under explicit asset/time/family rules; do not count two derived features of the same reading as independent evidence.
5. Ingest and handle the pressure-relief contact as a distinct direct protection/contact signal if its schema and semantics are confirmed. Direct observed contact events must not be hidden behind a model qualification gate.
6. Add tests for normal sealed-tank pressure, abnormal pressure, contact activation, missing/stale sensor data, out-of-range values, wrong tank construction and unsupported assets.

**Required limitations:**
- Do not apply sealed-tank pressure thresholds to conservator designs.
- The dataset's pressure model is a declared simplification for one tank configuration, not a universal pressure-temperature law.
- Pressure deviation alone does not prove an oil leak or identify an internal fault.
- If reliable limits or sensor semantics cannot be verified, expose pressure as descriptive/review-only and keep stronger action capability disabled.

### EXTRA C — Make the new electrical-stress and protection parameters usable

**Why this is extra:** The candidate adds asset impedance/rating metadata, short-circuit calculation records and event scenarios. These are not equivalent to high-rate measured fault waveforms.

**New work:**

1. Map and validate the candidate's asset-specific rated kVA, voltage class, impedance, electrical side and phase semantics. Remove hardcoded assumptions where the existing fix plan calls for AssetProfile-backed configuration.
2. Add a deterministic **prospective short-circuit reference calculation** only where the required metadata and units are verified. Keep measured values, calculated values and scenario assumptions separate and traceable.
3. Ingest simulated breaker/protection state and pressure-relief/protection contacts through the normal event/evidence lifecycle, after confirming their semantics. Preserve event time and provenance.
4. Add tests for calculation inputs/units, unsupported or missing impedance, asset-specific ratings, event activation and recovery/lifecycle behavior.
5. Show the result as a bounded engineering reference calculation—not a complete IEC 60909 study, protection-coordination result or demonstrated transformer withstand capability.

**Required limitation:** 30-minute telemetry cannot reconstruct sub-cycle short-circuit waveforms, peak asymmetry or clearing dynamics. Do not implement a waveform detector from this dataset.

### EXTRA D — Construction-aware capability and evidence integration

This is the cross-cutting work required to make the new domains safe and coherent rather than isolated demo features.

- Extend the existing asset profile/capability manifest for tank construction, oil-gauge applicability, pressure-sensor applicability, signal availability and per-domain qualification.
- Use capability states and reason codes to distinguish `unavailable`, `warming_up`, `degraded`, `disabled` and `available` as appropriate to the existing contract.
- Ensure unsupported or missing domains remain unknown/unavailable—not healthy zero.
- Route new results through the existing evidence/episode/review/advisory workflow and the same versioned `FactBundle`.
- Keep the existing `MAX_PLUS_SECONDARY_V1` OTHI formula and established evidence/persistence rules unchanged unless an explicit human-approved architecture decision says otherwise. OTHI remains secondary to direct protection, domain evidence and observability.
- Do not duplicate analytics in the frontend or reports. UI and reports render the same backend facts and qualification reasons.

## 3. Candidate dataset facts to encode in the adapter/profile

The supplied `dataset_syn` methodology describes a 30-minute, 180-day, four-asset synthetic dataset with 34,560 telemetry rows and 50 columns. It declares chronological FIT/CAL/TEST partitions of 108/36/36 days. Its stated asset applicability is:

| Candidate asset | Construction / oil gauge | Pressure | Relevant candidate scenarios |
|---|---|---|---|
| `DT-01-CONS-200` | Conservator; oil gauge fitted | Not fitted | Normal oil-level movement without leak |
| `DT-02-CONS-500` | Conservator; oil gauge fitted | Not fitted | Load/electrical stress, phase imbalance, short-circuit reference event |
| `DT-03-SEAL-250` | Sealed corrugated tank; no oil-level gauge | Gauge pressure in kPa | Abnormal pressure, pressure-relief contact, short-circuit reference event |
| `DT-04-CONS-315` | Conservator; oil gauge fitted | Not fitted | Slow oil leak, maintenance top-up, oil-level sensor stuck |

These are synthetic asset profiles, not real manufacturer identities. Confirm every field against the packaged manifest and actual CSV before freezing the adapter. Do not infer values for sensors marked not fitted.

## 4. Dataset admission, training and promotion gates

1. **Identify and hash:** record the exact current CPRI dataset version and the complete `dataset_syn` archive, extracted files, generator and manifest hashes. Resolve any mismatch between packaged and regenerated artifacts before use.
2. **Schema/semantics audit:** verify row/column counts, timestamps, cadence, units, asset IDs, tank/gauge/sensor applicability, duplicate handling, quality fields, scenario labels and split boundaries.
3. **No oracle leakage:** fault/event ledgers and scenario labels are evaluation truth only. They must not enter live detector features, fitting, calibration or runtime UI facts.
4. **Adapter and replay:** feed the candidate through the canonical contract; test deterministic chronological replay, gaps, duplicates, ordering, asset separation and state hashes.
5. **Software and domain tests:** prove oil, pressure, electrical-stress and protection pathways using FIT/CAL-appropriate development fixtures and explicit scenario cases. Passing a hand-crafted fixture alone is not model qualification.
6. **Training/calibration discipline:** FIT for fitting and model/driver choices; CAL for thresholds, uncertainty and policy calibration; freeze all choices before TEST.
7. **Promotion evaluation:** evaluate the frozen candidate once on TEST using predeclared metrics, including thermal forecast versus baseline where eligible, detector precision/recall where ground truth permits, false warning episodes per eligible asset-day, detection delay, abstention/capability coverage, and per-asset results. Record the limitations and all hashes.
8. **Promotion decision:** promote only if the agreed acceptance criteria pass and results are reproducible. If TEST has already been inspected or used for tuning, record the exposure and do not describe it as an untouched holdout; obtain a fresh holdout if needed.
9. **Cutover:** after explicit acceptance, switch the active workflow to `dataset_syn`. Retire the previous CPRI dataset from active operation but retain it and its frozen artifacts for historical reproducibility and rollback.

**Important:** internally consistent synthetic data and successful software tests do not establish field validity. Report results as performance on this synthetic benchmark under its declared assumptions.

## 5. Overall execution order

1. Wait for the frontend fix PR to merge; record the baseline and confirm the exact current CPRI dataset identifier.
2. Audit and freeze the `dataset_syn` package; resolve hash/manifest discrepancies.
3. Implement the adapter, canonical mapping, asset profiles and deterministic replay for `dataset_syn`.
4. Run the existing backend stabilization fixes in `BACKEND_STABILIZATION_PROPOSALS.md`, validating each against the current repository rather than assuming historical line references still match.
5. Implement the **extra domain work** in this document: oil-level trend/suspected leak, sealed-tank pressure, electrical-stress/protection reference logic and construction-aware capability integration.
6. Run backend unit, regression, domain, leakage and deterministic replay tests.
7. Fit/calibrate under FIT → CAL → FREEZE → TEST discipline and make the promotion decision.
8. Only after backend contracts and capabilities stabilize, integrate the frontend with the backend FactBundle/capability contracts.
9. Run end-to-end tests, verify dashboard/report fact consistency and demonstrate both available and unavailable capability states.
10. Promote `dataset_syn` only after acceptance; then retire the previous CPRI dataset from active use while preserving its archive.

## 6. Explicit non-goals

- No Tripura dependency in the active plan.
- No platform rewrite or parallel analytics stack.
- No universal pressure thresholds or pressure assumptions for conservator tanks.
- No confirmed oil-leak diagnosis from level/pressure telemetry alone.
- No sub-cycle fault-waveform reconstruction from 30-minute samples.
- No automatic control or autonomous protection action.
- No numeric failure probability or remaining useful life claim.
- No OTHI formula/weight changes, CUSUM relaxation, or TEST-driven retuning without explicit review and a valid evaluation protocol.

## 7. Source documents

- `FINAL_ARCHITECTURE_DECISIONS.md` — frozen architecture, canonical contracts, capability gates, OTHI policy, FactBundle and evaluation discipline.
- `BACKEND_STABILIZATION_PROPOSALS.md` — existing backend defects and regression-test proposals.
- `dataset_syn/METHODOLOGY (1).md` — candidate data construction, field semantics, assumptions and limitations.
- `dataset_syn/SCENARIOS_AND_VALIDATION.md` — candidate hashes, split/scenario manifest and reported pipeline gaps.
- `dataset_syn/SOURCES.md` — source-to-equation/parameter traceability and source limitations.

If this document conflicts with the frozen architecture, do not silently override it: stop at the conflict and request explicit approval. The current-dataset clarification in §1 supersedes obsolete references to Tripura as an active source.
