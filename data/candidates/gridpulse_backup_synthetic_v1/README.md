# GridPulse backup story dataset v1.0.0

Isolated synthetic demo candidate. Two new assets, 500 frames each, exactly 1,000 frames at 30-minute cadence. UTC range: 2025-01-01T00:00:00Z to 2025-01-11T09:30:00Z. Elapsed span per asset: 249.5 hours. Each 50-observation phase spans 24.5 hours between its own endpoints, and occupies a 25-hour scheduling block. The prompt's statement that 50 samples span 25 hours between first and last is corrected here.

Use `canonical_events.jsonl` as the primary document-derived telemetry representation. `telemetry.csv` has exactly 1,000 frame rows and the same nine envelope columns; nested source/measurement/flag cells contain JSON. Decode those three cells before use. This CSV serialization is a lossless convenience proposal, not a claim about the missing current wide-CSV adapter.

`telemetry_flat_view.csv` is a derived browsing view, not the authoritative ingestion contract. Its blanks mean absent observations, never healthy zero. Quality accompanies every scalar. The main files use absence from `measurements` for missing signals. BAD pressure is retained for audit and must not enter engineering calculations.

All observations are simulated sensor-equivalent snapshots. Generator truth, corrected oil inventory and diagnostic features live only in `latent_truth.csv`; event labels and interventions live only in `fault_events.csv`. Do not ingest either oracle file. No scenario IDs, expected OTHI, advisory states, or future outcomes are in inference telemetry. Source provenance identifies synthetic origin without encoding future events. `raw_frames.jsonl` contains only simulated observations and quality, with per-record SHA-256 links.

Nothing registers this dataset, alters models, changes thresholds, promotes capabilities, changes partitions, or touches existing GridPulse/CPRI/Tripura files. This is DEMO_ONLY, with no FIT/CAL/TEST partition assignment. Do not relabel these deliberately designed stories as a fresh qualification holdout. All sensor locations are LV bus voltage upstream of the LV breaker and downstream load current; hence voltage/frequency persist during a trip while load current and load power are zero. The transformer core remains energized.

## Commands

Python 3.12 and Matplotlib 3.10.8 were used. Data generation uses only the Python standard library; plots need Matplotlib.

```bash
python scripts/generate.py --output /absolute/path/to/new_backup_bundle
python /absolute/path/to/new_backup_bundle/scripts/validate.py --bundle /absolute/path/to/new_backup_bundle --write-report
python /absolute/path/to/new_backup_bundle/scripts/package.py --bundle /absolute/path/to/new_backup_bundle --zip /absolute/path/to/gridpulse_backup_v1.zip
```

Generation copies the delivered scripts/source register into a new directory. A nonempty existing dataset directory is refused; use a new directory. Package finalization adds the report hash and verifies the manifest after writing it. The manifest lists every bundle member except itself, avoiding an impossible self-hash. ZIP timestamps and member ordering are fixed. A fresh generator run with the recorded seed was byte-compared with this delivery; see validation_report.md.

## Compatibility

DOCUMENT-VERIFIED: architecture §C canonical envelope/base signals; §D first-order thermal update; §F evidence/lifecycle; §G five OTHI domains; current GridPulse scope Extra B explicitly names x_pressure_kpa_g. FILE-VALIDATED: generated structure/physics/scenarios/hashes/reproducibility. INFERRED: expected domain response. NOT-RUNTIME-VERIFIED: adapter acceptance, dashboard, replay, OTHI, episode/advisory outcomes. BLOCKED-MISSING-SOURCE: exact current wide CSV, manifest, AssetProfile, fault-event, Boolean value_type enum, pressure aliases/configuration and oil correction/warm-up details.

The canonical Boolean value is true/false. `value_type="boolean"` is an explicit serialization assumption because only `value_type="float"` is shown in the supplied architecture. A mapping review must confirm the application's enum before import. `x_pressure_kpa_g` is the documented extension; README mentions different source names. Do not silently substitute either.

Read schema_and_integration_notes.md before integration and DEMO_SCRIPT.md before replay.
