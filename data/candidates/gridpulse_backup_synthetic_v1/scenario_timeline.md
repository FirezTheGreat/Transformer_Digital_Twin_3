# Scenario timeline

All indices are one-based inclusive. Evidence responses are hypotheses until actual runtime testing. No intended health scores or episode states are encoded.

## GP-BACKUP-A-CONS-315

| Frames | UTC endpoints | Narrative | Signals/mechanism |
|---|---|---|---|
| 1–50 | 2025-01-01T00:00:00Z → 2025-01-02T00:30:00Z | Healthy baseline | Normal daily load and thermal/gauge expansion. |
| 51–100 | 2025-01-02T01:00:00Z → 2025-01-03T01:30:00Z | Early warning | Smooth load increase; no point impulse. |
| 101–150 | 2025-01-03T02:00:00Z → 2025-01-04T02:30:00Z | Developing incident | Sustained loading plus synthetic oil inventory decline. |
| 151–200 | 2025-01-04T03:00:00Z → 2025-01-05T03:30:00Z | Partial recovery | Load falls and oil temperature cools with inertia; inventory loss continues. |
| 201–250 | 2025-01-05T04:00:00Z → 2025-01-06T04:30:00Z | Recurrence or secondary stress | Recurring load growth; oil inventory loss increases from 221. |
| 251–300 | 2025-01-06T05:00:00Z → 2025-01-07T05:30:00Z | Sustained abnormal operation | Elevated loading persists; oil inventory keeps declining. |
| 301–350 | 2025-01-07T06:00:00Z → 2025-01-08T06:30:00Z | Intervention and improvement | Load redistribution plus six-point top-up at 301–306; simulated leak source removed. |
| 351–400 | 2025-01-08T07:00:00Z → 2025-01-09T07:30:00Z | Data-quality challenge | Mostly stable physics; oil observations absent 361–376 only. |
| 401–450 | 2025-01-09T08:00:00Z → 2025-01-10T08:30:00Z | New operating stress | Phase demand imbalance grows and produces neutral current. |
| 451–500 | 2025-01-10T09:00:00Z → 2025-01-11T09:30:00Z | Final stabilization | Phase rebalancing by 465; stable load/oil thereafter. |

## GP-BACKUP-B-SEAL-250

| Frames | UTC endpoints | Narrative | Signals/mechanism |
|---|---|---|---|
| 1–50 | 2025-01-01T00:00:00Z → 2025-01-02T00:30:00Z | Healthy baseline | Different daily load and thermal profile; sealed pressure baseline. |
| 51–100 | 2025-01-02T01:00:00Z → 2025-01-03T01:30:00Z | Early warning | Growing phase imbalance and small pressure offset. |
| 101–150 | 2025-01-03T02:00:00Z → 2025-01-04T02:30:00Z | Developing incident | Sustained unequal phase demand plus pressure offset. |
| 151–200 | 2025-01-04T03:00:00Z → 2025-01-05T03:30:00Z | Partial recovery | Load/phase and pressure gradually return toward baseline. |
| 201–250 | 2025-01-05T04:00:00Z → 2025-01-06T04:30:00Z | Recurrence or secondary stress | Milder loading plus a brief pressure pulse at 224–226. |
| 251–300 | 2025-01-06T05:00:00Z → 2025-01-07T05:30:00Z | Sustained abnormal operation | Pressure offset grows; separate trip at 278 removes downstream power/current. |
| 301–350 | 2025-01-07T06:00:00Z → 2025-01-08T06:30:00Z | Intervention and improvement | Physical contact reset at 301 and gradual re-energization; backend latch not auto-resolved. |
| 351–400 | 2025-01-08T07:00:00Z → 2025-01-09T07:30:00Z | Data-quality challenge | Pressure BAD/OUT_OF_RANGE 361–364, absent 365–376; unrelated channels current. |
| 401–450 | 2025-01-09T08:00:00Z → 2025-01-10T08:30:00Z | New operating stress | Balanced supply sag and lower PF create a different electrical story. |
| 451–500 | 2025-01-10T09:00:00Z → 2025-01-11T09:30:00Z | Final stabilization | Supply/PF restored by 465; stable physical state, possible unresolved backend trip. |

## Precise event windows and intervention assumptions

- **A-LOAD-1** (PHYSICAL_CONDITION): frames 51–200, 2025-01-02T01:00:00Z through 2025-01-05T03:30:00Z. Gradual loading rise, sustained thermal stress, and load-led recovery. Load dispatch improves from frame 151; thermal state cools with inertia.
- **A-OIL-LOSS** (PHYSICAL_CONDITION): frames 101–300, 2025-01-03T02:00:00Z through 2025-01-07T05:30:00Z. Synthetic oil inventory loss: -1 gauge percentage point/day, increasing to -1.8/day from frame 221. Physical loss is generator truth only; declining corrected level supports inspection, not confirmed runtime leakage.
- **A-LOAD-2** (PHYSICAL_CONDITION): frames 201–350, 2025-01-05T04:00:00Z through 2025-01-08T06:30:00Z. Recurring elevated loading and thermal exposure, followed by gradual unloading. Authorized synthetic load redistribution begins frame 301.
- **A-TOPUP** (SYNTHETIC_INTERVENTION): frames 301–306, 2025-01-07T06:00:00Z through 2025-01-07T08:30:00Z. Six gauge percentage points added over 2.5 h during hypothetical maintenance. Synthetic top-up and leak repair; no automatic application feedback is fabricated.
- **A-LEVEL-MISSING** (DATA_QUALITY): frames 361–376, 2025-01-08T12:00:00Z through 2025-01-08T19:30:00Z. Level channel absent for 16 frames while all other channels remain current. No imputation; last available level can become stale according to application policy.
- **A-PHASE-2** (PHYSICAL_CONDITION): frames 401–465, 2025-01-09T08:00:00Z through 2025-01-10T16:00:00Z. New uneven phase demand; neutral current is calculated from the fundamental phasor sum. Rebalancing from frame 451 to 465.
- **B-PHASE-1** (PHYSICAL_CONDITION): frames 51–200, 2025-01-02T01:00:00Z through 2025-01-05T03:30:00Z. Phase demand imbalance grows, persists and subsequently recovers. Phase load redistribution between frames 151 and 200.
- **B-PRESSURE-1** (PHYSICAL_CONDITION): frames 51–200, 2025-01-02T01:00:00Z through 2025-01-05T03:30:00Z. Temperature-aware pressure baseline plus a smooth, sustained synthetic accommodation offset. Offset relaxation represents a simplified construction-specific scenario, not a diagnosed internal fault.
- **B-PRESSURE-PULSE** (PHYSICAL_CONDITION): frames 224–226, 2025-01-05T15:30:00Z through 2025-01-05T16:30:00Z. Short smooth pressure pulse peaking at +9 kPa above baseline. No contact operation; transient versus sustained classification is runtime-dependent.
- **B-PRESSURE-2** (PHYSICAL_CONDITION): frames 251–315, 2025-01-06T05:00:00Z through 2025-01-07T13:00:00Z. Sustained pressure offset preceding an independent protective trip; then gradual relaxation. Synthetic pressure-source removal at trip and hypothetical engineering intervention; no universal threshold is asserted.
- **B-TRIP** (DISCRETE_PROTECTION): frames 278–300, 2025-01-06T18:30:00Z through 2025-01-07T05:30:00Z. LV protective trip indication held true; downstream currents and powers are zero. Inspection and physical contact reset at frame 301 followed by gradual re-energization. Application latch clearance still requires actual authorized feedback.
- **B-PRESSURE-BAD** (DATA_QUALITY): frames 361–364, 2025-01-08T12:00:00Z through 2025-01-08T13:30:00Z. Pressure sensor value fixed at +999 kPa and marked BAD/OUT_OF_RANGE. Only the pressure channel is unusable; other measurements are preserved.
- **B-PRESSURE-MISSING** (DATA_QUALITY): frames 365–376, 2025-01-08T14:00:00Z through 2025-01-08T19:30:00Z. Pressure channel absent for 12 frames following sensor malfunction. Sensor returns at frame 377 without filling the missing history.
- **B-SUPPLY-2** (PHYSICAL_CONDITION): frames 401–465, 2025-01-09T08:00:00Z through 2025-01-10T16:00:00Z. New balanced supply-voltage reduction and lower PF; temperature remains governed by phase-current losses. Synthetic feeder voltage restoration and downstream reactive-demand improvement between frames 451 and 465.

Final physical conditions have stabilized, but runtime incident closure is unverified. A has no ongoing generator oil loss and a restored gauge reference; B has no active contact indication and re-energized load. The backend trip may remain latched. End of a scenario window is not an instruction to close an episode.
