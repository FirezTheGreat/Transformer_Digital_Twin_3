# Validation report

Validation applies to delivered file bytes, not the GridPulse application.

Executed **116 checks**: **116 PASS, 0 FAIL**. 1,000 frames, 500 per asset, 15,949 individual measurements, four BAD pressure values. All 499 intervals per asset are exactly 30 minutes.

Commands actually executed for the final delivery:
```bash
python output/gridpulse_backup_v1/scripts/generate.py --output output/gridpulse_backup_final
python output/gridpulse_backup_final/scripts/generate.py --output tmp/backup_review/regenerated_final
python output/gridpulse_backup_final/scripts/validate.py --bundle output/gridpulse_backup_final --write-report
python output/gridpulse_backup_final/scripts/package.py --bundle output/gridpulse_backup_final --zip output/GridPulse_Backup_Synthetic_v1.zip
```
The initial source register was captured with `python output/gridpulse_backup_v1/scripts/generate.py --output output/gridpulse_backup_v1 --source-dir upload`. A separate Python byte-comparison checked all 21 fresh generator outputs (including the initial manifest), found zero mismatches, and verified all 19 supplied source-file hashes remained unchanged. See reproducibility_evidence.json.

Initial validation found one *validator* bug: an overly broad phase-name match mistakenly treated oil_level_percent as a phase signal. The selector was corrected to match only voltage_l/current_l prefixes. No telemetry values were changed to make that check pass. Final file validation: 116 PASS, zero FAIL. Package finalization then verified all delivered inventory hashes (including this report and JSON results): 119 PASS, zero FAIL. Archive CRC, all 24 member-byte round trips, and two byte-identical ZIP builds passed. The deterministic package command recreates those checks and emits package_verification.json beside its output ZIP.

No backend/frontend, source adapter, Git command, model fitting, TEST evaluation or runtime replay was executed.

## Descriptive scenario statistics

```json
{
  "GP-BACKUP-A-CONS-315": {
    "mean_baseline_load_ratio": 0.599566,
    "mean_final_load_ratio": 0.608149,
    "peak_top_oil_c": 97.841275,
    "max_top_oil_step_c": 1.780401,
    "baseline_imbalance_mean_pct": 1.0,
    "final_imbalance_mean_pct": 1.0
  },
  "GP-BACKUP-B-SEAL-250": {
    "mean_baseline_load_ratio": 0.545513,
    "mean_final_load_ratio": 0.551125,
    "peak_top_oil_c": 60.151914,
    "max_top_oil_step_c": 3.644242,
    "baseline_imbalance_mean_pct": 1.2,
    "final_imbalance_mean_pct": 1.0
  }
}
```

## Executed checks and tolerances

| Check | Result | Actual evidence / tolerance |
|---|---|---|
| exact total frames | PASS | 1,000 frames in each representation, not 1,000 scalar measurements |
| exact two assets | PASS | ['GP-BACKUP-A-CONS-315', 'GP-BACKUP-B-SEAL-250'] |
| exact per-asset counts | PASS | 500 frames each |
| unique canonical event IDs | PASS | UUIDv5 content-context IDs |
| unique frame keys | PASS | No duplicated asset/time frames |
| global deterministic ordering | PASS | UTC then asset identity |
| documented envelope field set | PASS | Nine exact document-derived envelope fields |
| CSV exact envelope columns | PASS | Nested cells are JSON; no invented wide inference schema |
| measurement field set | PASS | Documented fields; Boolean type spelling declared assumption |
| mandatory IDs nonblank | PASS | All identities populated |
| unit/signal allowlist | PASS | 16 signal IDs per asset; 17 union including documented pressure extension |
| phase assignments | PASS | LV phase identity consistent |
| typed numeric and discrete values | PASS | No NaN/Infinity/null numeric observations |
| quality vocabulary | PASS | STALE remains an elapsed-time state, not invented fresh records |
| one instance per signal/frame | PASS | No duplicated measurements |
| lossless frame CSV round-trip | PASS | All 1,000 canonical events reproduced exactly |
| raw source record hashes | PASS | 1,000 hashes recomputed from delivered raw bytes excluding newline |
| source/original observation round-trip | PASS | No cleaning overwrites raw observation values |
| no truth fields in inference | PASS | Canonical values, source and CSV checked for oracle field leakage; runtime permutation test is blocked |
| no partition-quality metadata | PASS | No PARTITION_CAL or scenario truth flags |
| static metadata not measurements | PASS | Nameplate, corrections and models stay outside telemetry |
| metadata two new identities | PASS | No transferred promotion/model or invented universal thresholds |
| not a qualification holdout | PASS | No existing FIT/CAL/TEST boundary altered |
| GP-BACKUP-A-CONS-315 UTC timestamps | PASS | All parseable and UTC-aware |
| GP-BACKUP-A-CONS-315 exact cadence | PASS | 499 consecutive 1,800-second intervals; no frame gaps |
| GP-BACKUP-A-CONS-315 exact endpoint span | PASS | 500 observations span 249.5 hours |
| GP-BACKUP-A-CONS-315 endpoints match manifest | PASS | 2025-01-01T00:00:00Z through 2025-01-11T09:30:00Z |
| GP-BACKUP-A-CONS-315 declared receive delay | PASS | Synthetic two-second transport assumption |
| GP-BACKUP-A-CONS-315 asset sensor applicability | PASS | Pressure only sealed B; gauge only conservator A |
| GP-BACKUP-A-CONS-315 three-phase apparent power | PASS | Absolute tolerance 0.000003 kVA after 6-decimal rounding; common-angle sinusoidal phase loads |
| GP-BACKUP-A-CONS-315 compatible power triangle | PASS | Tolerance 0.000002 kVA; explicitly declared power convention |
| GP-BACKUP-A-CONS-315 PF semantics | PASS | PF omitted at zero S; otherwise P/S within 0.000001 |
| GP-BACKUP-A-CONS-315 fundamental neutral phasor | PASS | Tolerance 0.000003 A; no invented harmonic currents |
| GP-BACKUP-A-CONS-315 thermal lag equation | PASS | Generator ODE verified against rounded delivered inputs and offline state; not application model validation |
| GP-BACKUP-A-CONS-315 slow-temperature continuity | PASS | Max observed change 1.780401 C/30min; simulation QA bound, not a universal sensor-fault threshold |
| GP-BACKUP-A-CONS-315 signal ranges | PASS | Declared simulation QA bounds, not standards or operating limits |
| GP-BACKUP-A-CONS-315 channel quality isolation | PASS | No unrelated channel made BAD |
| A developing loading vs baseline | PASS | Window mean difference >0.4 of declared rating |
| A thermal recovery visible | PASS | Recovery window at least 10 C cooler than developing window |
| A recurring stress distinguishable | PASS | Separate low-load interval before recurrence |
| A corrected inventory loss | PASS | More than four gauge percentage points of latent inventory loss; no leak diagnosis |
| A no-leak baseline expansion | PASS | Raw gauge moves with temperature despite constant reference inventory |
| A bulk-oil correction | PASS | Residual <0.15 gauge percentage points; own declared bulk-oil model, not top-oil substitution |
| A gradual top-up exactly six points | PASS | Top-up 301–306, repair assumption keeps reference level constant thereafter |
| A exact oil missing interval | PASS | 16 absent observations; not zero |
| A history before oil missingness | PASS | 360 consecutive observations span 179.5 h; exact runtime trend warm-up unverified |
| A new phase stress | PASS | Late phase imbalance then restoration |
| A final inventory stable | PASS | No continuing generator loss after intervention |
| GP-BACKUP-B-SEAL-250 UTC timestamps | PASS | All parseable and UTC-aware |
| GP-BACKUP-B-SEAL-250 exact cadence | PASS | 499 consecutive 1,800-second intervals; no frame gaps |
| GP-BACKUP-B-SEAL-250 exact endpoint span | PASS | 500 observations span 249.5 hours |
| GP-BACKUP-B-SEAL-250 endpoints match manifest | PASS | 2025-01-01T00:00:00Z through 2025-01-11T09:30:00Z |
| GP-BACKUP-B-SEAL-250 declared receive delay | PASS | Synthetic two-second transport assumption |
| GP-BACKUP-B-SEAL-250 asset sensor applicability | PASS | Pressure only sealed B; gauge only conservator A |
| GP-BACKUP-B-SEAL-250 three-phase apparent power | PASS | Absolute tolerance 0.000003 kVA after 6-decimal rounding; common-angle sinusoidal phase loads |
| GP-BACKUP-B-SEAL-250 compatible power triangle | PASS | Tolerance 0.000002 kVA; explicitly declared power convention |
| GP-BACKUP-B-SEAL-250 PF semantics | PASS | PF omitted at zero S; otherwise P/S within 0.000001 |
| GP-BACKUP-B-SEAL-250 fundamental neutral phasor | PASS | Tolerance 0.000003 A; no invented harmonic currents |
| GP-BACKUP-B-SEAL-250 thermal lag equation | PASS | Generator ODE verified against rounded delivered inputs and offline state; not application model validation |
| GP-BACKUP-B-SEAL-250 slow-temperature continuity | PASS | Max observed change 3.644242 C/30min; simulation QA bound, not a universal sensor-fault threshold |
| GP-BACKUP-B-SEAL-250 signal ranges | PASS | Declared simulation QA bounds, not standards or operating limits |
| GP-BACKUP-B-SEAL-250 channel quality isolation | PASS | No unrelated channel made BAD |
| B phase incident and recovery | PASS | Phase/neutral story differs from A thermal story |
| B sustained pressure 1 | PASS | Pressure offset persistent then returns near declared baseline |
| B pressure pulse separate | PASS | Three-frame pulse 224–226; no protective contact operation |
| B sustained pressure 2 | PASS | Distinct later sustained pressure window |
| B exact trip interval | PASS | 23 true frames, physical indication clears at 301 |
| B no-load trip consistency | PASS | Seven downstream current/power channels exactly zero during trip |
| B bus alive during LV trip | PASS | Upstream voltage/frequency persist; core remains energized |
| B physical contact reset/load return | PASS | Physical observation only; no backend resolution asserted |
| B BAD range values | PASS | Exactly four deliberate sensor-invalid values retained, not physical tank pressure |
| B exact pressure missing interval | PASS | 12 absent observations; pressure resumes at 377 |
| B late voltage/PF stress | PASS | Different late supply/reactive-demand story |
| B final pressure stable | PASS | Final physical pressure near own baseline; backend trip may remain active |
| exact measurement count | PASS | 16,000 nominal minus 16 missing oil, 12 missing pressure, 23 undefined PF = 15,949 |
| exact BAD count | PASS | Four pressure sensor-invalid measurements |
| event ledger IDs unique | PASS | 14 separate event/intervention windows |
| event labels explicitly synthetic | PASS | No actual transformer faults asserted |
| ledger A-LOAD-1 | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger A-OIL-LOSS | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger A-LOAD-2 | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger A-TOPUP | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger A-LEVEL-MISSING | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger A-PHASE-2 | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger B-PHASE-1 | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger B-PRESSURE-1 | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger B-PRESSURE-PULSE | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger B-PRESSURE-2 | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger B-TRIP | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger B-PRESSURE-BAD | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger B-PRESSURE-MISSING | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| ledger B-SUPPLY-2 | PASS | Start/end match exact frames; end-exclusive follows by 30 minutes |
| manifest DEMO_SCRIPT.md | PASS | Delivered bytes SHA-256 and byte count match |
| manifest README.md | PASS | Delivered bytes SHA-256 and byte count match |
| manifest asset_metadata.json | PASS | Delivered bytes SHA-256 and byte count match |
| manifest canonical_events.jsonl | PASS | Delivered bytes SHA-256 and byte count match |
| manifest capability_coverage_matrix.md | PASS | Delivered bytes SHA-256 and byte count match |
| manifest fault_events.csv | PASS | Delivered bytes SHA-256 and byte count match |
| manifest latent_truth.csv | PASS | Delivered bytes SHA-256 and byte count match |
| manifest plots/A_story.png | PASS | Delivered bytes SHA-256 and byte count match |
| manifest plots/B_story.png | PASS | Delivered bytes SHA-256 and byte count match |
| manifest raw_frames.jsonl | PASS | Delivered bytes SHA-256 and byte count match |
| manifest requirements.txt | PASS | Delivered bytes SHA-256 and byte count match |
| manifest scenario_timeline.md | PASS | Delivered bytes SHA-256 and byte count match |
| manifest schema_and_integration_notes.md | PASS | Delivered bytes SHA-256 and byte count match |
| manifest scripts/generate.py | PASS | Delivered bytes SHA-256 and byte count match |
| manifest scripts/package.py | PASS | Delivered bytes SHA-256 and byte count match |
| manifest scripts/validate.py | PASS | Delivered bytes SHA-256 and byte count match |
| manifest signal_dictionary.md | PASS | Delivered bytes SHA-256 and byte count match |
| manifest source_document_register.json | PASS | Delivered bytes SHA-256 and byte count match |
| manifest telemetry.csv | PASS | Delivered bytes SHA-256 and byte count match |
| manifest telemetry_flat_view.csv | PASS | Delivered bytes SHA-256 and byte count match |
| all JSON read-back | PASS | 4 JSON files parse |
| all CSV read-back | PASS | Four CSV files parse |
| plots have valid PNG signatures | PASS | Two readable PNG diagnostic plots, not detector outputs |
| fresh regeneration byte equality | PASS | Independent fresh generation: 21 files, seed 20261011 |

## Assumptions and blockers

- Actual GridPulse adapter/CanonicalEvent enum acceptance: BLOCKED-MISSING-SOURCE.
- Exact current wide CSV, AssetProfile, fault-event and manifest layouts: BLOCKED-MISSING-SOURCE; proposed layouts explicitly identified.
- Current pressure alias/baseline/thresholds and relief-contact semantics: BLOCKED-MISSING-SOURCE.
- Oil bulk-temperature correction and multi-day trend warm-up/segmentation: BLOCKED-MISSING-SOURCE.
- Runtime OTHI scores, detector firing/delay, episode/advisory lifecycle, feedback and replay/UI/report checks: NOT-RUNTIME-VERIFIED.
- Runtime truth-permutation invariance: BLOCKED-MISSING-SOURCE; static no-oracle-field check executed.
- Forecast, CUSUM, residual qualification, RUL and insulation-ageing validation: intentionally not attempted; no promoted new-asset artifacts.

Electrical equations are validated only under the explicitly declared compatible sinusoidal snapshot convention. Current-squared heating drives thermal inertia; the exact generator equation is checked, but following it does not validate the application model. Bulk-oil, gauge and pressure constants are synthetic assumptions. QA range/step tolerances are engineering test bounds for this file, not universal limits. Intentional BAD observations are not physical contradictions. No active detector thresholds are changed.
