# Contract and later integration

## Authority and resolved document conflicts

Official problem statement defines the intended monitoring prototype. FINAL_ARCHITECTURE_DECISIONS §C explicitly defines long-form CanonicalEvent; it therefore governs this export. The latest GridPulse instructions/status override historical Tripura migration, Git operations, phase execution and old cadence text. This task expressly authorizes an isolated backup, overriding the earlier deferral of other datasets solely for this deliverable. No application work is performed.

Current documents conflict on initial candidate filename, CPRI version/cadence, asset naming/rating, and whether OTHI may be revised. This bundle does not resolve those by guessing runtime state: it uses new identities, the requested 30-minute cadence and preserved architecture signal names. OTHI and model policies are untouched. Historical 85/95°C thresholds, workbook 50 A / unspecified 60°C trip tests, and candidate promotion results are not copied into synthetic asset settings.

## Exact primary record fields

`schema_version,event_id,asset_id,event_time_utc,received_time_utc,source,measurements,event_quality_flags,mapping_version` match the documented envelope. Each measurement has `signal_id,phase,value,value_type,unit_ucum,original_name,original_value,original_unit,quality`. Source contains `system,adapter_id,source_record_id,source_uri,raw_sha256`. Quality contains `severity,flags,source_code`. Units: V, A, kW, kvar, kVA, Hz, Cel, %, kPa and dimensionless 1. Bool type-tag spelling remains a declared assumption; all booleans are genuine JSON booleans. Pressure is the explicit current-scope extension, with alias acceptance unverified.

Simulated receive time is event time +2 seconds, representing a declared synthetic transport delay, not actual historic ingestion. Every quantity is a co-timed snapshot of a quasi-steady 50 Hz RMS operating state, not a 30-minute average or waveform. For each snapshot, phase RMS measurements share temporal support. All three phase loads are sinusoidal with a common lagging displacement angle and negligible harmonic content. P/Q/S therefore share a compatible convention even under unequal phase-current magnitudes. No sequence VUF, THD, hotspot, winding temperature, pressure relief contact, or fault waveform is fabricated.

Metadata and manifest use explicit proposed JSON layouts because no actual AssetProfile/manifest file was supplied. `fault_events.csv` uses a clearly declared proposal with stable scenario/event IDs, inclusive frame windows and both inclusive/exclusive UTC ends. It is not an assertion of exact project ledger compatibility. Numerical generator constants are in metadata; they are synthetic assumptions, not fitted runtime model artifacts or manufacturer thresholds.

## Register later without replacing existing data

1. Extract to a new isolated `data/candidates/gridpulse_backup_story_v1/` directory; retain the ZIP and hashes. Do not overwrite processed data or active configs.
2. Inspect the actual CanonicalEvent, Boolean type enum, pressure alias, AssetProfile, candidate registration and replay implementation. Map this package at the adapter boundary; validate one event per asset, then all 1,000.
3. Add the two *new* identities with declared synthetic ratings and sensor inventory. Keep threshold provenance explicit. Verify oil coefficient/bulk-temperature convention, pressure baseline and sensor range against supported configuration. Our synthetic gauge coefficient and pressure baseline are not universal limits.
4. Allow only canonical_events.jsonl (or decoded telemetry.csv), reviewed metadata and source records into replay. Do not put latent_truth.csv, fault_events.csv, offline diagnostics or future interventions in detector/model inputs. Test truth permutation invariance against the actual runtime.
5. Mark the new dataset DEMO_ONLY. Leave existing registrations and active model identities untouched. The new assets have no qualified thermal/forecast/CUSUM artifacts; preserve descriptive monitoring and explicit unavailable states. Do not borrow DT-01 or TX_1000_COMM qualification.
6. Confirm counts, ordering, resets/asset isolation, quality suppression, trip/current coherence, domain coverage and UI/report agreement. Record actual outcomes. Do not expect the physical contact reset at frame 301 to erase a backend trip latch.
7. If the actual runtime produces a trip episode/recommendation, use its returned identity and documented authorized feedback API to ACK/RESOLVE after verified inspection. No feedback payload is fabricated here because current IDs/reason codes/revisions/run identity are unavailable. This is decision-support demo feedback, not a real switching command.

No exact scores or alarm delays are promised. At 30-minute cadence, 24 frames span 11.5 h and 25 span 12 h; first 12-hour-supported oil estimate is no earlier than frame 25 if that warm-up is confirmed. The latest instructions instead require robust multi-day support, so the exact eligibility is blocked pending code/configuration; more than four days of continuous oil observations precede its missing-data challenge. Missing intervals never count as recovery.

## Missing sources needed for runtime verification

- Current canonical schema/types and asset profile examples.
- Existing synthetic telemetry example, adapter/tag map, manifest and fault_events schema.
- Pressure registry alias, baseline/threshold configuration and pressure-relief contact definition.
- Bulk-oil temperature estimator, level correction coefficient and multi-day trend/intervention segmentation configuration.
- Replay/episode/feedback run-scope contracts and currently loaded model registry.

## Source register

- `CODING_RULES(3).md` — SHA-256 `4561f17473bad98087c89bc42d1346d2d302ccd10166cf018c4f529fcc38af90`
- `CRITICAL_DECISIONS(3).md` — SHA-256 `6968e99bcb3f6006943b2622439baf19e066e79d72e79cc0d1d217949739b568`
- `DT Problem Statement(6).pdf` — SHA-256 `8a98651b2b89b9dc9fbef1e865a6b8565305d01911b9b16dab3f6058837e9ef1`
- `Draft Data for Condition Monitoring(6).xlsx` — SHA-256 `c532b52dbf6f52c8edbc9111915983fbcae3ae53482a03c8f26123ce87a35a2d`
- `FINAL_ARCHITECTURE_DECISIONS(5).md` — SHA-256 `8cd2cee51d49ddb9ca429c1d4c5855a7c6a6c687efee44804c26d57072917abb`
- `GRIDPULSE_DATASET_SYN_ADAPTATION_AND_EXTRA_DOMAIN_SCOPE.md` — SHA-256 `a4bb24de8d2383319cd42b9ff905718112326e587d9843fb423409ef9d7707de`
- `GRIDPULSE_IMPLEMENTATION_INSTRUCTIONS.md` — SHA-256 `46417c779f43d7066f9f5968edf8a355e1e42ce0011407f254c7fb5ece0d5a90`
- `GRIDPULSE_MASTER_EXECUTION_PLAN.md` — SHA-256 `28b01cc110d2734be7aed5a3d3a1f040bf84d49c5e63e84ab393e2023ede6e55`
- `HACKATHON_RUNBOOK(2).md` — SHA-256 `64cbf38372d6316259cc0fc85e23a3b4c5c6acb1b56c273613a7c81076e0e508`
- `IMPLEMENTATION_PLAN(5).md` — SHA-256 `64c4e7a44a0289ecd03ee80146d23a9076059ef4b46a696820c9f0dc880aebef`
- `MVP(5).md` — SHA-256 `586b1dc46f4d3a7ef3cdd4e8feb8032351222dc653d7a5a79de90326f5c917df`
- `PHASE_10_5_FINAL_VERIFICATION_REPORT(2).md` — SHA-256 `1f09689ac25c36feea2ab608ceeb000e23286154f3b4774f0805b041ad963dc2`
- `PHASE_9_4_VERIFICATION_REPORT(2).md` — SHA-256 `aa3ecb7e2843e97f3970dd31350c6a3ec6034d628c93f017f6bdb3a27e07396b`
- `POST_AUDIT_IMPLEMENTATION_BRIEF_CPRI_FINAL.md` — SHA-256 `0c4e92b657a79b824ae8c73332554d8e91635422a517a907c86432918f9cfc66`
- `PRINCIPLES(5).md` — SHA-256 `f0f4f6137b06bf1c3858ed79899a97510f813e52c74ecb3d7cf266c28f47a3e3`
- `Pasted text(20261010-223635).txt` — SHA-256 `340ff9add18e3b5df66ae5aaaceecbf02951c12fb196860ec456e5e939b23aad`
- `README.md` — SHA-256 `26f80c5088da2c880d0dfd3f202367e7066e11f10d74776df2663fadd0e9868a`
- `SRS(5).md` — SHA-256 `8be8582c57f46a047e5a6c2a0f4cdb8b359c333da681a6a5c976dda84d4f0538`
- `TRIPURA_DATASET_AUDIT(3).md` — SHA-256 `79231b83e62c7b77dbaf17a15d0a68ed6698afe1ddd856fcac933be225e71d58`

Primary public references (scope/design grounding, not numerical parameter validation):
- IEC 60076-7:2018 public scope: https://webstore.iec.ch/en/publication/34351
- Hitachi Energy distribution transformer construction: https://www.hitachienergy.com/in/en/products-and-solutions/transformers/distribution-transformers/liquid-filled-distribution-transformers/medium-distribution-transformers-316-2-499-kva
- Hitachi Energy breather/thermal contraction context: https://www.hitachienergy.com/products-and-solutions/insulation-and-components/transformer-insulation-components/measurement-and-safety-devices/dehydrating-breathers/conventional

These primary sources support general loading/temperature and construction context only. The gauge/pressure coefficients and schedules below are declared simulation assumptions; no IEC/IEEE compliance or field calibration is asserted.
