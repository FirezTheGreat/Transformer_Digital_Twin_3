# GridPulse Implementation Instructions — Two-Pass Plan

## Documentation authority

Before changing code, inspect the repository and follow this hierarchy:

1. **Authoritative current plan:** the latest `GRID_PULSE_MASTER_EXECUTION_PLAN*.md` in the project root (use the exact filename that exists). Its phases and sequencing govern the work.
2. **Other current root-level documents:** relevant parts of `FINAL_ARCHITECTURE_DECISIONS.md`, `CRITICAL_DECISIONS.md`, `CODING_RULES.md`, `PRINCIPLES.md`, `SRS.md`, `IMPLEMENTATION_PLAN.md`, `MVP.md`, and the latest verification/handoff reports.
3. **`docs/` files may be outdated.** Treat them as historical/reference material unless current root-level documents confirm they are current. Do not let old phase descriptions or recommendations in `docs/` override the root master plan.
4. If documents conflict, follow explicit critical decisions and the root-level master execution plan. Mention material conflicts briefly in the final report; do not spend time reconciling every old document.

Do not assume filenames exist exactly as listed. Inspect the actual repository filenames. Do not use Git commands to inspect repository state.

## Global rules

- Work only on the existing `main` branch. Do not create or switch branches.
- **Never run Git commands.** No status, diff, log, checkout, reset, stash, add, commit, push, pull, fetch, or other Git operations.
- Preserve user work, untracked files, datasets, checkpoints, model artifacts, configs, frozen results, and existing evidence. Do not delete or overwrite datasets/checkpoints/evaluation artifacts.
- The other two synthetic datasets are **intentionally deferred**. Do not search for, reconstruct, invent, compare, or integrate them in either pass. Keep the existing GridPulse synthetic dataset and CPRI benchmark intact. Tripura is not the current migration target.
- Do not tune on TEST, change frozen TEST partitions or evaluation gates to force a pass, alter historical metrics, promote unqualified models, or automatically switch the active model.
- Inspect current code before acting on older audit findings. Phase 8 fixes may already exist; verify and extend rather than blindly reimplementing.
- Keep the implementation physically defensible and practical for a strong hackathon demo. Do not disable useful functionality unnecessarily, and do not claim unsupported measurements or validation.
- Prefer targeted changes, clean code, and tests that reduce real risk. Avoid repeated exploration, redundant tests, unrelated refactors, and speculative features.
- If something cannot be safely implemented and verified, report the limitation rather than faking a pass.

---

# Pass 1 — Telemetry contracts, detection, and condition assessment

## Goal

Make backend evidence and condition assessment trustworthy before expanding lifecycle behavior or doing final end-to-end polish.

### 1. Inspect current state efficiently

Read the authoritative root-level plan and relevant architecture/engineering documents first. Inspect the current adapter, canonical signal mapping, detectors, model qualification gates, OTHI/domain-health logic, and related tests. Treat old `docs/` content as historical where it conflicts with current root-level documentation. Create a short implementation checklist and proceed; do not spend time producing another long audit report.

### 2. Fix telemetry and signal contracts

Verify and correct these where still present:

- Partition metadata such as `PARTITION_CAL` must not be interpreted as a data-quality fault.
- Static/nameplate/configuration fields must not be streamed as live measurements.
- Canonical aliases for breaker contacts, protection trips, OTI alarms/trips, pressure, and domain signals must agree across adapters, detectors, OTHI, and API output.
- Sealed-tank assets must not require an oil-level gauge to assess their pressure domain.
- Detector IDs must map to the correct domain/family.
- Thresholds must follow existing documented asset/scenario configuration, not invented universal thresholds.
- Missing, stale, and bad-quality measurements must be represented honestly. Bad-quality data is not trusted physical evidence.
- Evidence grades and provenance must not overstate confidence.

Centralize mappings where this reduces duplication. Preserve units, timestamps, quality, provenance, and measurement-versus-estimate distinctions.

### 3. Correct thermal residual/model qualification behavior

- An unpromoted model must not emit qualified operational anomaly evidence solely because its artifact carries a qualification flag.
- Respect existing registry, promotion, and explicit-approval boundaries.
- Do not apply iid-style CUSUM assumptions blindly to strongly autocorrelated residuals.
- Until residual detection is validated for its intended use, gate it from OTHI and qualified operational decisions. If a correct, testable prewhitening or alternative method is feasible, implement it; otherwise keep it clearly unqualified.
- Keep forecast uncertainty, model residuals, sensor faults, and physical-condition evidence distinct.

Do not change model promotion status or historical evaluation results as a shortcut.

### 4. Correct oil-level and pressure physics

**Conservator assets**
- Inspect the dataset's actual temperature/level-generation assumptions.
- Apply a consistent bulk-oil temperature correction using documented project assumptions.
- Estimate leakage from a robust multi-day trend, not short-term temperature-driven level variation.
- Estimate leakage rate/time-to-low-level only with sufficient valid data.
- Detect stuck/invalid gauges and suppress unsupported leakage conclusions.
- Label estimates and confidence explicitly.

**Sealed-tank assets**
- Route pressure evidence into the correct domain even without an oil-level gauge.
- Use a temperature-aware expected-pressure baseline only where available data and documented assumptions support it.
- Distinguish transient pressure excursions from sustained abnormal conditions.
- Use existing asset/scenario settings; do not claim universal standards compliance.

### 5. Implement a coherent OTHI/domain-health model

Do not merely tweak fixed penalty weights to make the dashboard look better. Make OTHI a defensible, explainable assessment based on available evidence.

- Separate the slower-moving **condition score** from instantaneous **operating stress**.
- Keep protection state (e.g. TRIPPED/OUT OF SERVICE) explicit and immediately visible rather than allowing averaging to hide it.
- Use physics-based domain calculations where supported: thermal/loading without double-counting, electrical balance, conservator oil, sealed-tank pressure, and low-weight supply-quality indicators if justified by current architecture.
- Exclude genuinely unobserved domains from aggregation and show coverage. Missing data must not artificially improve health.
- Reduce confidence for stale data. Label inferred values as estimates.
- Explain leading drivers with values/thresholds where available.
- Use documented persistence, smoothing, and recovery behavior; avoid scattered magic numbers.
- Preserve deterministic replay/reset behavior.
- Do not claim IEC calibration or universal validation without evidence.
- Preserve the current contract or deliberately document necessary semantic changes. A trip must be visible and urgent, but literal OTHI zero is not automatically the correct representation of underlying asset health.

Add a small deterministic test set covering monotonicity, normal conditions, missing/stale data, isolated excursions, sustained faults, protection state, and recovery. Treat numeric targets as project acceptance targets, not universal physical laws. Never tune on TEST. Keep the old score for comparison if practical and safe; do not silently reinterpret historical results.

## Pass 1 test strategy

- Inspect existing tests once and map changes to the smallest relevant test modules.
- Run focused tests for adapter/signal contracts, qualification gates, oil/pressure handling, and OTHI.
- Fix failures and rerun only affected tests.
- After stabilization, run one suitable consolidated backend regression pass if time/resources allow.
- Do not repeatedly run the same broad suite or weaken/delete tests to pass.
- Do not spend Pass 1 on a frontend redesign or full-system smoke test; those belong in Pass 2.

## Pass 1 completion report

Report: (1) changes and important files; (2) exact tests/commands and actual results; (3) remaining defects/limitations and unmet acceptance criteria; (4) OTHI semantic changes and compatibility implications; (5) confirmation no Git commands were run and no datasets/checkpoints/frozen TEST results were altered.

**Stop after the Pass 1 report. Do not start Pass 2 automatically.**

---

# Pass 2 — Episodes, replay/injection state, frontend integration, and demo verification

Start Pass 2 only after reviewing Pass 1 results and deciding to proceed. Recheck the root-level master plan for applicable phase gates. Older `docs/` phase descriptions do not override it.

## Goal

Make replay, evidence, episodes, recommendations, frontend views, and reports behave coherently, then verify one end-to-end path.

### 1. Episode and advisory lifecycle

- Separate brief audit events from sustained operational conditions.
- Use domain-appropriate persistence for thermal, electrical, oil, and pressure episodes.
- Handle verified protection trips and similarly severe protection events immediately.
- Deduplicate by asset/domain/family where appropriate.
- Track confirmation, escalation, recovery, and closure using event/replay time.
- Keep acknowledgement (seen) distinct from resolution (fixed/closed).
- Conditions that clear must not remain indefinitely as active urgent advisories.
- Distinguish recurrences from old closed episodes.
- Use the twin watermark and run identity for feedback timestamps.
- Reset/asset switching must not carry stale feedback or trip latches into another run.
- Trip unlatching requires a relevant resolution after the trip, not any historical RESOLVE record.

Extend the current architecture instead of introducing a large framework unnecessarily.

### 2. Replay, state, and scenario injection

Verify before changing whether these remain:
- Frontend-generated synthetic trip events bypassing the backend injector architecture.
- Injected zero-current readings persisting after replay advances/resets.
- Stale observations accumulating rather than being superseded/evicted.
- Reset/seek/asset switching leaving stale time bounds or asynchronous UI responses.
- Normal CAL partition completion being reported as an unexpected stop.

Where defects remain, route supported injections through the existing backend scenario/injector architecture; keep them deterministic, attributable, resettable, and distinct from recorded telemetry. Keep trip, breaker, current, power, evidence, and protection state consistent. Clear/recompute run-scoped state on reset/asset switch. If physics-consistent injection cannot be safely completed, disable/constrain that path and explain why. Do not fabricate telemetry or extend the dataset to lengthen the demo.

### 3. Frontend/backend integration

Check API URLs, auth/CORS, request/response schemas, errors, capability manifest, FactBundle, evidence, episodes, recommendations, generated types, and contract tests where present.

Verify consistency across dashboard, anomaly timeline, maintenance view, recommendations, historical performance, and report/export:
- Same underlying facts and timestamps.
- Correct asset/dataset/model provenance and qualification status.
- Honest missing/stale/estimated-value states.
- No hardcoded demo telemetry or duplicated frontend analytics.
- Live transient snapshots are not mislabeled as full historical run summaries.
- Unsupported panels are hidden/disabled or explained, while useful defensible information remains visible.

Reuse existing Phase 8 fixes where correct.

### 4. One end-to-end integration check

After focused tests and frontend build are ready, perform one deliberate smoke check using only the existing GridPulse synthetic dataset and current CPRI benchmark as appropriate. Do not integrate the other two datasets.

At minimum:
1. Start backend and frontend using the supported project procedure.
2. Confirm backend/frontend health.
3. Load a supported asset and verify initial telemetry/capability information.
4. Advance replay and verify consistent telemetry, stress, condition, and evidence.
5. Verify one representative sustained condition or supported scenario injection.
6. Verify protection-trip state and breaker/current consistency.
7. Reset and switch assets; confirm no stale telemetry, time bounds, feedback, injection, or UI request contaminates the new state.
8. Verify normal end-of-partition behavior.
9. Exercise one advisory/episode lifecycle and confirm UI/backend agreement.
10. Verify report/export facts and provenance.

Record only what was actually tested. State anything that could not be verified.

### 5. Efficient testing strategy

Focused tests first; rerun only affected tests after fixes; one consolidated backend regression pass after stabilization; one frontend build after frontend changes stabilize; one end-to-end smoke check. No redundant full-suite runs. Do not weaken tests or fabricate results.

## Pass 2 completion report

Report: (1) changes and important files; (2) exact tests/build/E2E steps and results; (3) limitations and unverified behavior; (4) demo readiness and safest coherent demo path; (5) manual checks before commit/push; (6) confirmation no Git commands were run and no commits/pushes were made.

Stop after the report. Do not run Git commands or commit/push.

---

## Final priorities

1. Correct physical meaning and data contracts.
2. Trustworthy OTHI, stress, protection state, and model qualification.
3. Correct episode/advisory lifecycle and replay state.
4. End-to-end UI/backend consistency.
5. Demo polish only after correctness.

Stay scoped, use the current root-level master plan as authority, and explicitly defer the two additional synthetic datasets.
