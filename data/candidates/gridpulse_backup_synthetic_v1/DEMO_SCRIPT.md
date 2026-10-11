# Backup replay guide

All UI behavior here is expected, not runtime verified. Integrate only after contract review. Select the new backup identities, never an existing promoted asset. Zero-based replay seeks below assume one asset loaded as 500 frames; actual API positioning must be checked. Interleaved file row numbers are not asset seek positions.

| Asset / seek | One-based frame / UTC | What to inspect | Intended evidence |
|---|---|---|---|
| A / 24 | 25 / 2025-01-01T12:00:00Z | Normal daily load, ambient and lagged oil temperature, moving gauge | Baseline coverage; no promised OTHI value |
| A / 124 | 125 / 2025-01-03T14:00:00Z | Growing loading/temperature and declining oil inventory after compensation | Loading/thermal condition; suspected-loss review if eligible |
| A / 189 | 190 / 2025-01-04T22:30:00Z | Falling load and gradual cooling | Telemetry-supported partial recovery, not an oracle reset |
| A / 274 | 275 / 2025-01-06T17:00:00Z | Second load/thermal episode and continuing level decline | Recurrence/sustained inputs |
| A / 305 | 306 / 2025-01-07T08:30:00Z | Gauge top-up and falling load | Explain documented synthetic intervention, not spontaneous healing |
| A / 369 | 370 / 2025-01-08T16:30:00Z | Missing oil level while electrical/thermal remain current | Coverage/freshness limitation, not a new physical fault |
| A / 429 | 430 / 2025-01-09T22:30:00Z | Unequal phase currents and corresponding neutral current | Phase/neutral evidence may trigger documented MNT-PHASE-004 |
| B / 124 | 125 / 2025-01-03T14:00:00Z | Phase imbalance and sustained gauge-pressure offset | Independent electrical/pressure observations |
| B / 224 | 225 / 2025-01-05T16:00:00Z | Brief pressure pulse with no contact trip | Compare with sustained offset, exact classification unverified |
| B / 276 | 277 / 2025-01-06T18:00:00Z | Sustained higher pressure, then advance one frame | Analog condition is distinct from discrete protection |
| B / 277 | 278 / 2025-01-06T18:30:00Z | breaker_trip=true; phase currents, neutral, P/Q/S all zero | Immediate direct protection path, possible MNT-PROT-001 |
| B / 300 | 301 / 2025-01-07T06:00:00Z | Physical contact=false; gradual load return | Backend trip latch may remain; ACK is not RESOLVE |
| B / 361 | 362 / 2025-01-08T12:30:00Z | Pressure=999 kPa BAD/OUT_OF_RANGE | Reject only this pressure evidence; preserve other domains |
| B / 369 | 370 / 2025-01-08T16:30:00Z | Pressure absent | Show stale/unavailable, never healthy zero |
| B / 429 | 430 / 2025-01-09T22:30:00Z | Balanced supply sag and lower PF | Supply-quality/reactive-demand review, not intrinsic ageing |
| Both / 489 | 490 / 2025-01-11T04:30:00Z | Stable final physical readings and actual outstanding incidents | Do not promise closed trips or OTHI=100 |

Play chronologically for persistence. A direct seek can rebuild or discard history depending on current implementation; do not promise a trend/lifecycle from one selected row. Use event-time speed controls and inspect actual API facts. If the trip creates an episode, acknowledge its actual ID, then record authorized inspection/resolution using the real returned ID and run/revision contract. No fabricated feedback or automatic clearance file is included.

No causal what-if, qualified residual alarms or CUSUM on these assets until independently qualified. No RUL, insulation life, fault probability, standards compliance, leak diagnosis or field accuracy claims. Export only actual backend FactBundle facts. Do not ingest the offline oracle files.
