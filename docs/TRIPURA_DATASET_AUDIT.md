# Tripura Distribution Transformer Dataset — Schema & Physical Integrity Audit

**Audit Status:** Completed and Locked (Phase 1, Substep 1.1)
**Audited Directory:** `C:\1st year learning programs\CPRI\Transformer_Digital_Twin\data\tripura_raw`
**Audit Generated (UTC):** `2026-10-04T10:24:23.785287+00:00`
**Total Raw Files:** 5 CSVs (6.60 MB)
**Common Timestamps Across All Files:** 18,324
**Total Union Timestamps:** 20,024

---

## 1. Executive Summary & Feasibility Verdict

> [!NOTE]
> **PREREQUISITE DATA-VOLUME & CALIBRATION FEASIBILITY: PASS**  
> The Tripura dataset (`tripura_dt_01`) satisfies prerequisite criteria (valid sample count >= 500, calendar span >= 7 days, continuous 2-hour calibration origins >= 30, and dynamic load variation) to attempt first-order grey-box thermal calibration. This dataset serves as the project's engineering development and calibration dataset (with acknowledged historical exposure during early methodology development), while unseen simulated datasets will serve as the final hackathon evaluation target. On the frozen Tripura evaluation, the model achieved +18.59% 2-hour MAE improvement but remains `NOT_PROMOTED` due to boundary hit $\tau = 0.5\,\text{h}$ and trajectory bias, cleanly exercising the `C3` fallback gating.

---

## 2. File Inventory & Dimensions

| File Name | Size (Bytes) | Row Count | Column Count | Unique Timestamps | Exact Duplicates | Conflicting Duplicates |
| - | - | - | - | - | - | - |
| `CurrentVoltage.csv` | 1,428,576 | 19,352 | 11 | 18,915 | 64 | 810 |
| `Overview.csv` | 1,003,649 | 20,316 | 8 | 19,376 | 1,144 | 727 |
| `Power.csv` | 1,183,477 | 19,309 | 10 | 18,871 | 858 | 18 |
| `PowerFactor.csv` | 1,739,626 | 19,308 | 16 | 18,877 | 2 | 860 |
| `TotalPower.csv` | 1,560,439 | 19,248 | 9 | 18,842 | 786 | 26 |

---

## 3. Sampling Characteristics & Temporal Continuity

| File Name | Earliest Timestamp | Latest Timestamp | Nominal $\Delta t$ (Median) | Mean $\Delta t$ (min) | Gaps > 1h | Gaps > 24h | Gaps > 7d |
| - | - | - | - | - | - | - | - |
| `CurrentVoltage.csv` | `2019-06-25T13:06` | `2020-04-14T00:30` | 15.0 min | 22.3 min | 60 | 18 | 3 |
| `Overview.csv` | `2019-06-25T13:06` | `2020-04-14T00:30` | 15.0 min | 21.8 min | 58 | 19 | 3 |
| `Power.csv` | `2019-06-25T13:06` | `2020-04-14T00:30` | 15.0 min | 22.4 min | 60 | 18 | 3 |
| `PowerFactor.csv` | `2019-06-25T12:39` | `2020-04-14T00:30` | 15.0 min | 22.4 min | 59 | 18 | 3 |
| `TotalPower.csv` | `2019-06-27T10:51` | `2020-04-14T00:30` | 15.0 min | 22.3 min | 59 | 17 | 3 |

### Key Sampling Observations:
- **Nominal Resolution:** Telemetry is nominally sampled at 15-minute intervals ($\approx 81\%$ of all records).
- **Span:** Data spans from late June 2019 to mid April 2020 (~294 calendar days / 9.8 months).
- **Continuous Partitions:** Found multiple large continuous segments with no gaps > 30 minutes, including a 15.0-day block (1,486 consecutive samples) and an 10.9-day block (1,078 consecutive samples).

---

## 4. Signal Inventory & Descriptive Statistics

### File: `CurrentVoltage.csv`

| Column | Type | Min | Max | Mean | Median | Std | Zeros (%) | Nulls | Out of Bounds / Notes |
| - | - | - | - | - | - | - | - | - | - |
| `VL1` | `float64` | 0.00 | 261.20 | 241.07 | 242.70 | 9.54 | 3 (0.0%) | 0 | Phase-to-neutral voltage nominal ~240V; 0V denotes de-energized/outage. |
| `VL2` | `float64` | 0.00 | 261.30 | 240.52 | 242.10 | 9.80 | 6 (0.0%) | 0 | Phase-to-neutral voltage nominal ~240V; 0V denotes de-energized/outage. |
| `VL3` | `float64` | 0.00 | 261.30 | 239.91 | 241.10 | 8.85 | 3 (0.0%) | 0 | Phase-to-neutral voltage nominal ~240V; 0V denotes de-energized/outage. |
| `IL1` | `float64` | 0.00 | 224.10 | 73.71 | 69.50 | 41.26 | 1574 (8.1%) | 0 | Current magnitude strictly non-negative. |
| `IL2` | `float64` | 0.00 | 253.60 | 58.97 | 50.20 | 40.46 | 1663 (8.6%) | 0 | Current magnitude strictly non-negative. |
| `IL3` | `float64` | 0.00 | 247.30 | 83.23 | 80.20 | 43.61 | 1662 (8.6%) | 0 | Current magnitude strictly non-negative. |
| `VL12` | `float64` | 0.00 | 446.50 | 379.48 | 417.80 | 119.96 | 1730 (8.9%) | 0 | Line-to-line voltage nominal ~415V; 0V denotes outage/offline. |
| `VL23` | `float64` | 0.00 | 444.80 | 378.53 | 416.30 | 119.42 | 1729 (8.9%) | 0 | Line-to-line voltage nominal ~415V; 0V denotes outage/offline. |
| `VL31` | `float64` | 0.00 | 447.30 | 379.97 | 417.90 | 120.07 | 1732 (8.9%) | 0 | Line-to-line voltage nominal ~415V; 0V denotes outage/offline. |
| `INUT` | `float64` | 0.00 | 145.80 | 26.32 | 25.60 | 15.10 | 1653 (8.5%) | 0 | Current magnitude strictly non-negative. |

### File: `Overview.csv`

| Column | Type | Min | Max | Mean | Median | Std | Zeros (%) | Nulls | Out of Bounds / Notes |
| - | - | - | - | - | - | - | - | - | - |
| `OTI` | `float64` | 0.00 | 250.00 | 30.06 | 29.00 | 12.17 | 53 (0.3%) | 0 | Top-oil temperature indicator (deg C); contains extreme outlier(s) up to 250 deg C. |
| `WTI` | `float64` | 0.00 | 1.00 | 0.27 | 0.00 | 0.44 | 14821 (73.0%) | 0 | OOB: 0 |
| `ATI` | `float64` | 0.00 | 44.00 | 27.50 | 28.00 | 5.69 | 54 (0.3%) | 0 | Ambient temperature indicator (deg C). |
| `OLI` | `float64` | 36.00 | 100.00 | 70.95 | 73.00 | 27.64 | 0 (0.0%) | 0 | OOB: 0 |
| `OTI_A` | `float64` | 0.00 | 1.00 | 0.00 | 0.00 | 0.07 | 20215 (99.5%) | 0 | OOB: 0 |
| `OTI_T` | `float64` | 0.00 | 1.00 | 0.00 | 0.00 | 0.05 | 20269 (99.8%) | 0 | OOB: 0 |
| `MOG_A` | `float64` | 0.00 | 1.00 | 0.11 | 0.00 | 0.31 | 18163 (89.4%) | 0 | OOB: 0 |

### File: `Power.csv`

| Column | Type | Min | Max | Mean | Median | Std | Zeros (%) | Nulls | Out of Bounds / Notes |
| - | - | - | - | - | - | - | - | - | - |
| `WL1` | `float64` | -0.20 | 48.60 | 17.25 | 16.50 | 9.23 | 1707 (8.8%) | 0 | OOB: 0 |
| `WL2` | `float64` | -0.20 | 52.60 | 13.53 | 11.70 | 9.03 | 1711 (8.9%) | 0 | OOB: 0 |
| `WL3` | `float64` | -0.20 | 53.80 | 19.23 | 18.80 | 9.77 | 1708 (8.8%) | 0 | OOB: 0 |
| `VAL1` | `float64` | 0.00 | 49.00 | 17.37 | 16.70 | 9.28 | 1707 (8.8%) | 0 | OOB: 0 |
| `VAL2` | `float64` | 0.00 | 53.10 | 13.79 | 12.00 | 9.05 | 1711 (8.9%) | 0 | OOB: 0 |
| `VAL3` | `float64` | 0.00 | 54.30 | 19.62 | 19.20 | 9.86 | 1708 (8.8%) | 0 | OOB: 0 |
| `RVAL1` | `float64` | -2.50 | 16.80 | 1.60 | 1.30 | 1.57 | 2737 (14.2%) | 0 | OOB: 0 |
| `RVAL2` | `float64` | -0.20 | 8.90 | 2.39 | 2.30 | 1.33 | 1733 (9.0%) | 0 | OOB: 0 |
| `RVAL3` | `float64` | -0.00 | 0.02 | 0.00 | 0.00 | 0.00 | 1819 (9.4%) | 0 | OOB: 0 |

### File: `PowerFactor.csv`

| Column | Type | Min | Max | Mean | Median | Std | Zeros (%) | Nulls | Out of Bounds / Notes |
| - | - | - | - | - | - | - | - | - | - |
| `PFL1` | `float64` | -0.98 | 1.00 | 0.99 | 0.99 | 0.02 | 5 (0.0%) | 0 | OOB: 0 |
| `PFL2` | `float64` | -0.96 | 1.00 | 0.97 | 0.98 | 0.03 | 5 (0.0%) | 0 | OOB: 0 |
| `PFL3` | `float64` | -0.95 | 1.00 | 0.97 | 0.98 | 0.03 | 5 (0.0%) | 0 | OOB: 0 |
| `Avg_PF` | `float64` | -0.96 | 1.00 | 0.98 | 0.98 | 0.03 | 6 (0.0%) | 0 | OOB: 0 |
| `Sum_PF` | `float64` | -164.40 | 35.20 | 4.82 | 10.10 | 21.71 | 5 (0.0%) | 0 | OOB: 0 |
| `FRQ` | `float64` | 0.00 | 50.20 | 49.94 | 50.00 | 0.81 | 5 (0.0%) | 0 | Grid frequency nominal 50 Hz. |
| `THDVL1` | `float64` | 0.00 | 6.20 | 1.82 | 1.80 | 0.57 | 9 (0.0%) | 0 | OOB: 0 |
| `THDVL2` | `float64` | 0.00 | 6.50 | 1.80 | 1.70 | 0.59 | 8 (0.0%) | 0 | OOB: 0 |
| `THDVL3` | `float64` | 0.00 | 6.30 | 1.83 | 1.80 | 0.58 | 5 (0.0%) | 0 | OOB: 0 |
| `THDIL1` | `float64` | 0.00 | 30.60 | 11.25 | 11.10 | 6.12 | 1548 (8.0%) | 0 | OOB: 0 |
| `THDIL2` | `float64` | 0.00 | 65.90 | 11.65 | 11.20 | 6.04 | 1633 (8.5%) | 0 | OOB: 0 |
| `THDIL3` | `float64` | 0.00 | 33.10 | 8.65 | 8.00 | 4.52 | 1631 (8.4%) | 0 | OOB: 0 |
| `MDIL1` | `float64` | 0.00 | 234.00 | 149.01 | 152.30 | 48.74 | 52 (0.3%) | 0 | OOB: 0 |
| `MDIL2` | `float64` | 0.00 | 234.70 | 129.04 | 135.20 | 62.82 | 1673 (8.7%) | 0 | OOB: 0 |
| `MDIL3` | `float64` | 0.00 | 230.50 | 160.76 | 175.80 | 61.35 | 1673 (8.7%) | 0 | OOB: 0 |

### File: `TotalPower.csv`

| Column | Type | Min | Max | Mean | Median | Std | Zeros (%) | Nulls | Out of Bounds / Notes |
| - | - | - | - | - | - | - | - | - | - |
| `KWH` | `float64` | 0.00 | 346071.90 | 162739.82 | 164884.95 | 109130.99 | 3 (0.0%) | 0 | OOB: 0 |
| `KWH_I` | `float64` | -54.50 | 33000.50 | 17.98 | 11.70 | 300.71 | 1509 (7.8%) | 0 | OOB: 0 |
| `KVARH` | `float64` | 0.00 | 350124.20 | 164581.70 | 166658.55 | 110392.84 | 3 (0.0%) | 0 | OOB: 0 |
| `KW` | `float64` | -0.84 | 142.15 | 50.27 | 47.48 | 27.02 | 1516 (7.9%) | 0 | OOB: 0 |
| `KVA` | `float64` | 0.00 | 142.90 | 50.92 | 48.21 | 27.18 | 1516 (7.9%) | 0 | OOB: 0 |
| `KVAR` | `float64` | -0.21 | 27.04 | 7.66 | 7.81 | 3.86 | 1652 (8.6%) | 0 | OOB: 0 |
| `MPD` | `float64` | 0.00 | 134.80 | 95.31 | 102.50 | 32.73 | 47 (0.2%) | 0 | OOB: 0 |
| `MKVAD` | `float64` | 0.00 | 135.70 | 95.92 | 103.10 | 32.92 | 47 (0.2%) | 0 | OOB: 0 |

---

## 5. Thermal Feasibility & Physical Integrity Findings

- **Top-Oil Signal:** Present (`OTI`) with range 0.0 to 250.0 deg C.
- **Ambient Signal:** Present (`ATI`) with range 0.0 to 44.0 deg C.
- **Load Drivers:** Present (TotalPower.KVA, TotalPower.KW, CurrentVoltage.I_equivalent).
- **Valid Paired Thermal Points:** 19,284 samples.
- **Severe Temperature Inversions ($T_o < T_a - 10^\circ\text{C}$):** 2 instances.
- **Slight Temperature Inversions ($T_o < T_a$):** 1730 instances (attributed to integer rounding and transient thermal lag).
- **Continuous Blocks $\ge 7$ Days:** 5 segments.
- **Continuous Blocks $\ge 500$ Points:** 11 segments.
- **Longest Segment:** 14.97 days (1,486 consecutive samples).

### Detailed Thermal Observations:
- Top-oil (OTI) and Ambient (ATI) present with 19284 physically valid paired samples.
- Nominal 15-minute resolution across 102 continuous segments.
- Found 5 continuous segments spanning >= 7 calendar days and 11 segments with >= 500 samples.
- Longest continuous segment spans 15.0 days (1486 consecutive samples).
- Detected 2 severe thermal inversions (`T_o < T_a - 10 degC`) and 1730 slight inversions (`T_o < T_a`).
- Quantization observed: OTI and ATI are recorded as integer-rounded values (step size 1.0 deg C).


---

## 6. Unresolved Questions & Semantic Ambiguities

- **Asset Nameplate Ratings:** Nameplate kVA, rated voltages, and rated currents are not recorded in raw CSV headers; must be supplied via AssetProfile configuration.
- **WTI Semantics:** WTI column contains only binary values {0.0, 1.0} (73% 0, 27% 1) rather than continuous winding temperatures; likely an overtemperature trip/alarm contact or threshold indicator rather than a continuous PT100 sensor.
- **Thermal Quantization:** OTI and ATI values are recorded in integer steps of 1.0 deg C, introducing rounding noise at low load rises.
- **Conflicting Duplicate Timestamps:** Multiple rows share identical DeviceTimeStamp strings with differing telemetry values (e.g. 727 in Overview.csv, 810 in CurrentVoltage.csv), requiring deterministic selection/deduplication in the ingestion adapter.
- **Reactive Power Phase 3:** RVAL3 in Power.csv is near zero (max 0.02 kvar) while RVAL1 reaches 16.8 kvar; indicates potential single-phase reactive metering configuration or sensor channel dropout on phase 3 reactive power.

---

## 7. Supported vs. Gated Capabilities

### Supported Capabilities (Tier P0/P1):
- [x] C0 (Data Integrity): Telemetry validation, duplicate detection, range checks, and freshness tracking across 5 telemetry domains.
- [x] C1 (Electrical Balance & Power Quality): Three-phase voltage magnitude unbalance (%VUB), current unbalance (%IUB), neutral current ratio, power factor, frequency tracking, and harmonic distortion (THD-V, THD-I).
- [x] C2 (Descriptive Thermal Monitoring): Top-oil temperature (OTI), ambient temperature (ATI), oil temperature rise over ambient, oil level indicator (OLI), and contact alarms (OTI_A, OTI_T, MOG_A).
- [x] C3 (Predictive Thermal Modeling & What-If): First-order grey-box differential thermal model (beta0, beta1, tau) with conformal path uncertainty and 2-hour forward scenario projection.
- [x] C4 (Thermal Exposure & Accelerated Ageing Gate): Relative ageing rate and equivalent ageing hours calculation gated under valid hot-spot and declared insulation class.

### Gated / Unsupported Capabilities (Scope Exclusions):
- [ ] Continuous Winding Hot-Spot Tracking from Direct Sensor: Direct continuous winding temperature is unavailable because WTI is a binary contact indicator; hot-spot must be derived via IEC 60076-7 / IEEE C57.91 equations or gated when hot-spot estimation prerequisites are absent.
- [ ] Whole-life Remaining Useful Life (RUL) & Failure Probability: Prohibited by principles (P0 scope constraint; true insulation end-of-life requires unmeasured DP/DGA/furan history).
- [ ] Dissolved Gas Analysis (DGA) & Partial Discharge (PD): No gas or acoustic channels present in telemetry.
- [ ] Mechanical Vibration Monitoring: No accelerometer or acoustic telemetry available.

---

## 8. Preserved Raw Data Integrity & Development Partitioning

- All raw CSV files under `data/tripura_raw/` remain untouched and bit-exact.
- No raw data has been renamed, interpolated, imputed, or modified.
- Downstream processing created versioned, immutable partitioned Parquet files in `data/processed/` (`tripura_fit.parquet`, `tripura_calibration.parquet`, `tripura_test.parquet`) with strict two-hour embargo gaps.
- The Tripura dataset is the development/calibration baseline for Phase 1–7 engineering; holdout evaluations on unseen simulated datasets will serve as the final competition benchmarks.
