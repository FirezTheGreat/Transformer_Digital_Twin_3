# Capability coverage before generation

This design matrix describes inputs and gates, not executed detector outcomes.

| Capability | Asset | Required signals/metadata | Support | Gate/limitation |
|---|---|---|---|---|
| Integrity/replay | Both | Canonical identity, timestamps, units, quality, provenance | DOCUMENT-VERIFIED / FILE-VALIDATED | Runtime replay and schema acceptance NOT-RUNTIME-VERIFIED |
| Loading/electrical | Both | Phase V/I, P/Q/S, PF and declared synthetic rating | DOCUMENT-VERIFIED / FILE-VALIDATED | Configured thresholds and asset-profile registration required |
| Thermal trends/exposure | Both | Ambient and lagged top-oil observations | DOCUMENT-VERIFIED / FILE-VALIDATED | Direct limit/exposure bands depend on actual asset settings |
| Oil trend / suspected loss | A | Raw oil level, reference metadata, temperature-aware bulk-oil generation | INFERRED / FILE-VALIDATED | Exact correction, bulk estimator and multi-day warm-up BLOCKED-MISSING-SOURCE |
| Phase/neutral | A late; B early | Three phase-current magnitudes and fundamental neutral RMS | DOCUMENT-VERIFIED / FILE-VALIDATED | MNT-PHASE-004 is documented; firing/timing NOT-RUNTIME-VERIFIED |
| Pressure transient/sustained | B | x_pressure_kpa_g; declared sealed construction and range | DOCUMENT-VERIFIED extension / FILE-VALIDATED | Active pressure alias, baseline and thresholds BLOCKED-MISSING-SOURCE |
| Direct protective trip | B | Boolean breaker_trip; zero downstream currents and power | DOCUMENT-VERIFIED / FILE-VALIDATED | MNT-PROT-001 is documented; application latch remains until actual authorized resolution |
| Missing/BAD observability | Both | A missing oil; B BAD then missing pressure; unrelated signals preserved | DOCUMENT-VERIFIED / FILE-VALIDATED | Staleness display and suppression NOT-RUNTIME-VERIFIED |
| OTHI/episodes/advisories | Both | Distinct condition inputs, recovery, recurrence, protection | INFERRED | No score/state/advisory is supplied; runtime policy decides all results |
| Forecast/what-if/residual/CUSUM | Neither newly qualified | Thermal inputs available; no applicable promoted artifact | NOT-RUNTIME-VERIFIED | Disabled unless separately qualified; no borrowed parameters or TEST tuning |
| RUL/insulation ageing/DGA | Neither | No hotspot, insulation class, DGA or degradation history | DOCUMENT-VERIFIED exclusion | Unavailable; generator latent states do not establish capability |
| Pressure-relief contact / short-circuit | Neither | Exact current contact schema/verified impedance unavailable | BLOCKED-MISSING-SOURCE | Omitted instead of inventing aliases or waveform evidence |
