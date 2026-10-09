# CPRI ONAN practical-schema synthetic transformer benchmark — v3.0.2

## Authoritative methodology

| Item | Value |
|---|---|
| Clean benchmark | `transformer_practical_schema_v3.0.2_30min.csv` — 280,182 rows, 47 columns |
| DQ stress benchmark | `transformer_practical_schema_v3.0.2_with_dq.csv` — raw telemetry + labels + DQ labels |
| Generator | `src/simulate_v3_0_2.py`, generator version 3.0.2 |
| Configuration | `config/simulator_config_v3.0.2.json` (every numeric parameter below) |
| Base seed | `2026100902` |
| Validation | `src/validate_v3_0_2.py` → `validation_report_v3.0.2.json` (27/27 PASS) |
| Manifest | `dataset_manifest.json` (file SHA-256s, seeds, environment) |

> **What this is.** A deterministic synthetic benchmark for Digital-Twin software integration, thermal calibration
> exercises and leakage-safe detector evaluation. **Not** Tripura, CPRI, utility or field data. No claim of real
> fault prevalence, field accuracy, RUL or insulation condition. The thermal structure is *inspired by*
> IEC 60076-7 / IEEE C57.91 first-order models; it is **not** a standards-compliant implementation.

> **Relationship to v3.0.1.** v3's original generator was unavailable. v3.0.2 is produced by a new, fully
> published generator that re-implements the v3 design (same 8 assets, ratings, thermal parameters, 30-min
> cadence, splits, 12 fault classes, column schema) with the refinements listed in §13. Row values differ
> from v3.0.1; event timings and noise realisations are new. v3.0.1 should be retired.

Every equation in this document is the one executed by the generator. Mechanisms marked **[EMPIRICAL]** are
deliberate benchmark models, not physics. Mechanisms marked **[PHYSICS-INSPIRED]** follow an established model
family with synthetic parameters.

---

## 1. Time grid, assets, partitions

- Grid: `t_k = 2024-01-01T00:00+05:30 + 30 min·k`, k = 0 … 35,087 (end exclusive 2026-01-01T00:00+05:30). Δt = 30 min.
- One **continuous latent simulation per asset over the full grid**. Partitions are assigned afterwards by timestamp:

| Partition | Interval (IST, start inclusive, end exclusive) |
|---|---|
| FIT | 2024-01-01 00:00 → 2025-01-01 00:00 |
| CAL | 2025-01-01 00:00 → 2025-07-03 00:00 |
| TEST | 2025-07-03 00:00 → 2026-01-01 00:00 |

- Latent state, lag and rolling features run continuously across partition boundaries.
- Notation: `h` = local hour (fractional), `d` = 1-based fractional day of year, `t_h` = hours since grid start,
  `K` = latent load (pu of rating), `i` = 0-based asset index in config order.

Assets (all `ASSUMPTION`; synthetic, not heat-run data):

| i | Asset | kVA | Profile | Base load (pu) | ΔT_oil,r (K) | τ_oil,r (min) | n | ΔT_wdg,r (K) | τ_wdg,r (min) | R |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | TX_100_RES | 100 | residential | 0.53 | 35.5 | 250.0 | 0.80 | 19.0 | 8.0 | 8.5 |
| 1 | TX_160_RURAL | 160 | rural | 0.50 | 37.0 | 275.0 | 0.82 | 20.0 | 9.0 | 9.0 |
| 2 | TX_250_MIX | 250 | mixed | 0.58 | 38.4 | 294.3 | 0.82 | 21.0 | 9.5 | 9.73 |
| 3 | TX_315_RES | 315 | residential | 0.61 | 38.8 | 300.0 | 0.83 | 21.5 | 9.8 | 9.9 |
| 4 | TX_400_COMM | 400 | commercial | 0.59 | 39.2 | 307.0 | 0.84 | 22.0 | 10.0 | 10.0 |
| 5 | TX_500_RURAL | 500 | rural | 0.56 | 39.5 | 315.0 | 0.85 | 22.5 | 10.5 | 10.2 |
| 6 | TX_630_MIX | 630 | mixed | 0.63 | 40.0 | 325.0 | 0.86 | 23.0 | 11.0 | 10.5 |
| 7 | TX_1000_COMM | 1000 | commercial | 0.64 | 41.0 | 340.0 | 0.88 | 24.0 | 12.0 | 11.0 |

Ratings are the declared configuration of the synthetic assets and are written to `x_rating_kva` in every row.

## 2. Random number generation

- Bit generator: NumPy `PCG64`. Each stream = `Generator(PCG64(SeedSequence(2026100902, spawn_key=(i, s))))`.
- Streams `s`: 0 ambient · 1 load · 2 electrical_latent · 3 electrical_noise · 4 thermal_noise · 5 condition_noise ·
  6 event_schedule · 7 fault_perturbation · 8 dq.
- Changing one stream's consumption does not alter any other stream.
- AR(1) helper used throughout: `e_k ~ N(0, σ²)`, `x_0 = e_0/√(1−φ²)`, `x_k = φ·x_{k−1} + e_k`.
- Reproducibility verified: two independent runs produced byte-identical output files (manifest records hashes
  and Python/NumPy/pandas/SciPy versions; PCG64 + SeedSequence are stable across NumPy ≥ 1.17).

## 3. Ambient temperature [EMPIRICAL] — stream 0

```
synoptic: daily nodes s_j = AR(1)(φ=0.7, σ=1.2 °C), j = 0…D+1, node time = 24j + 12 h, linearly interpolated to t_h
micro_k  = AR(1)(φ=0.9, σ=0.2 °C) per grid step
T_amb = 25 + 5.4·sin(2π(d − 92)/365.25) + 4.2·sin(2π(h − 9.5)/24) + synoptic + micro + 0.12·(i − 3.5)
```
Draw order in stream 0: synoptic nodes, then micro.

## 4. Load [EMPIRICAL] — stream 1

Shape functions (`g` = circular Gaussian on 24 h, `P(a,b) = σ((h−a)/0.5)·σ((b−h)/0.5)`, σ = logistic):
```
residential = 0.55 + 0.35·g(h; 7.5, 1.5) + 0.75·g(h; 20.0, 2.0)
commercial  = 0.40 + 0.75·P(9, 18)
rural       = 0.50 + 0.45·g(h; 5.5, 1.2) + 0.55·g(h; 19.5, 2.0)
mixed       = 0.50 + 0.30·g(h; 8.0, 1.5) + 0.30·P(10, 17) + 0.55·g(h; 20.0, 2.0)
profile     = shape(h) / mean(shape over 48 half-hours) × (weekend factor on Sat/Sun)
weekend factor: residential 1.05 · commercial 0.73 · rural 1.00 · mixed 0.90
```
```
daily = exp(interp(AR(1) daily nodes, φ=0.5, σ=0.08·√(1−0.5²)))        (node at 12:00 each day)
annual = 1 + 0.06·sin(2π(d − 120)/365.25)
fast  = AR(1)(φ=0.9, σ=0.02) per step
K = clip(base_load · profile · daily · annual · (1 + fast), 0.05, 1.45)
overload rows: K = clip(max(K·(1+m), 1.02 + 0.5·m), 0.05, 1.45)
```
Note: normal operation can exceed 1 pu at evening peaks (13,337 rows > 1 pu; only 7.3 % are labelled `overload`).
This is intentional: "overload" is an injected *sustained* event, not "any row above 1 pu".

## 5. Three-phase electrical model [PHYSICS-INSPIRED] — stream 2 (latent)

```
share bias b_p = 1/3 + N(0, 0.01²), renormalised            (constant per asset)
share_p,k = b_p + AR(1)(φ=0.95, σ=0.0015)                    (independent per phase)
phase imbalance (magnitude m): share_1 += m; share_2 −= m/2; share_3 −= m/2; clip ≥ 0.05; renormalise
V0 = 433/√3 V
weekly = 1 + 0.012·sin(2π·t_h/168)
pv_p = AR(1)(φ=0.95, σ=0.0012) per phase
K_p = 3·share_p·K
PQD term (s = PQD magnitude): pq_p = 0.004·s·[1, −0.5, −0.5]_p
V_p = V0 · weekly · (1 + pv_p) · (1 − 0.035·K_p) · (1 + pq_p)
θ_p = [0°, −120°, +120°] + N(0, 0.3°²)  (iid each step)
pf_c = clip(0.93 − 0.04·(K − 0.5) + AR(1)(φ=0.97, σ=0.003), 0.80, 0.99)
pf_p = clip(pf_c + δ_p, 0.80, 0.99),  δ_p ~ N(0, 0.005²) constant per asset per phase
S_p = share_p · K · rating   [kVA];   I_p = 1000·S_p / V_p   [A];   φ_p = arccos(pf_p)
P = Σ S_p·pf_p;   Q = Σ S_p·sin φ_p;   S = √(P² + Q²)
I_N = |Σ I_p·e^{j(θ_p − φ_p)}|
V_LL = mean(|V_a∠θ_a − V_b∠θ_b|, |V_b − V_c|, |V_c − V_a|)  (phasor magnitudes)
f = 50 + AR(1)(φ=0.96, σ=0.005) + 0.01·sin(2π(h − 14)/24) + 0.02·s·sin(π·k/2)
THD_V = max(0.2, 1.2 + 0.25·K + AR(1)(φ=0.95, σ=0.03) + 0.6·s)       [EMPIRICAL scalar, not waveform-derived]
THD_I = max(0.2, 6.0 − 2.0·K + AR(1)(φ=0.95, σ=0.12) + 0.9·s)        [EMPIRICAL scalar, not waveform-derived]
```
Draw order in stream 2: share bias, 3 share AR series, 3 voltage AR series, angle jitter, pf AR, pf phase offsets,
frequency AR, THD-V AR, THD-I AR.

## 6. Electrical measurement model — stream 3

```
constant per-asset biases ~ N(0, 0.003²): b_V,p (3), b_I,p (3), b_P, b_Q, b_S
V_p,obs = V_p·(1 + b_V,p + N(0, 0.0035²))       I_p,obs = I_p·(1 + b_I,p + N(0, 0.008²))
P_obs = P·(1 + b_P + ε_P);  Q_obs = Q·(1 + b_Q + ε_Q);  S_obs = S·(1 + b_S + ε_S);  ε ~ N(0, 0.009²)
```
**Admissibility (clean data):** the joint error (ε_P, ε_Q, ε_S) is a Gaussian **truncated to the physically
admissible region** `P_obs ≤ S_obs` and `|Q_obs| ≤ S_obs`: for any row outside it, all three ε are redrawn from the
same stream until admissible (35 redraws in total across 280k rows; per-asset counts in the manifest). Measurements
are never clipped or rewritten. Result: realistic inconsistency (median |S_obs − √(P_obs²+Q_obs²)| = 1.46 kVA;
S_obs ≠ √3·V·I exactly) with no impossible rows.

```
PF_obs = clip(P/S + N(0, 0.003²), 0, 0.999)       (independent of P_obs/S_obs)
f_obs = f + N(0, 0.002²);  THD_obs = max(0, THD + N(0, 0.03²))
V_LL,obs = V_LL·(1 + N(0, 0.001²));  I_N,obs = max(0, I_N·(1 + N(0, 0.02²)))
x_current_a = mean(I_p,obs);  x_voltage_unbalance_pct = max_p|V_p,obs − mean|/mean·100 (same for current)
x_load_pu = S_obs / rating
```

## 7. Thermal model [PHYSICS-INSPIRED, IEC 60076-7-inspired] — latent, deterministic

```
c = cooling-degradation magnitude (0 outside event);  q = internal heat (K, 0 outside event)
ΔT_oil,u = ΔT_oil,r · ((1 + R·K²)/(1 + R))^n · (1 + c) + q
τ_oil = clip(τ_oil,r·(0.88 + 0.22/(0.35 + K))·(1 + 0.003·(24 − T_amb))·(1 + 1.10·c), 0.5·τ_oil,r, 1.9·τ_oil,r)
ΔT_wdg,u = ΔT_wdg,r · max(K, 0.02)^y,   y = 1.6
τ_wdg = τ_wdg,r·(0.92 + 0.10/(0.4 + K))
α = 1 − exp(−Δt/τ),  Δt = 30 min (latent grid is never interrupted; gaps remove observations only)
ΔT[k] = ΔT[k−1] + α[k]·(ΔT_u[k] − ΔT[k−1]),   ΔT[0] = ΔT_u[0]  (steady-state start)
T_oil = T_amb + ΔT_oil;   T_wdg = T_oil + ΔT_wdg
```
`y = 1.6` is the corrected winding exponent (v3/v3.0.0 used 3.2 in error). `x_winding_temp_c` is a WTI-like channel
generated from the winding-rise state; it is **not** a measured fibre-optic hot-spot.

## 8. Condition channels [EMPIRICAL] — latent deterministic, noise stream 5

**Bushing temperature** (first-order lag, τ_b = 45 min, steady-state start):
```
B* = T_amb + 3.0 + 0.40·ΔT_oil + 18.0·K² + E_b
E_b (bushing overheating, magnitude m °C) = m·(0.4 + 0.6·K²)·min(1, (t_ev + 0.5 h)/2 h)
T_b[k] = T_b[k−1] + (1 − e^{−30/45})·(B*[k] − T_b[k−1])
```
**Oil level** (conservator gauge, % of scale):
```
L = 88.0 + 0.15·(T_oil − 40) − leak
leak (oil leak, rate r %/day) = r·(t_ev + 0.5 h)/24 during the event, 0 otherwise  (event end = repair/top-up)
```
**Vibration** (tank-wall RMS):
```
v = 1.20 + 0.30·K² + 0.20·(mean_p V_p / V0)² + A·(1 + 0.3·K²)       (A = anomaly amplitude, mm/s, 0 outside event)
```
`t_ev` = hours since event start (0 at the first event row).

## 9. Thermal and condition observation — streams 4 and 5

| Channel | Observation | Quantum |
|---|---|---|
| Ambient | T_amb + N(0, 0.35²) | 0.1 °C |
| Oil | T_oil + N(0, 0.28²) + sensor-fault bias | 0.5 °C |
| Winding | T_wdg + N(0, 0.40²) | 0.5 °C |
| Bushing | T_b + N(0, 0.5²) | 0.5 °C |
| Oil level | L + N(0, 0.4²), clip 0–100 | 0.1 % |
| Vibration | v · exp(N(0, 0.08²)) | none |

Quantisation = `round(x/quantum)·quantum`. Stream 4 draw order: ambient, oil, winding. Stream 5: bushing, oil level,
vibration.

## 10. Fault mechanisms (12 classes) — magnitudes from stream 7

| Class | Domain | Duration (h) | Magnitude m by severity (low / medium / high) | Exact mechanism |
|---|---|---|---|---|
| overload | operational | 8–30 | +0.12–0.20 / +0.24–0.34 / +0.38–0.52 (fraction) | §4: K = max(K(1+m), 1.02+0.5m), clip 1.45 → electrical and thermal respond |
| phase_imbalance | electrical | 6–18 | 0.06–0.10 / 0.12–0.17 / 0.19–0.25 (share) | §5 share shift → phase currents, unbalance, neutral |
| cooling_degradation | physical | 72–240 | 0.07–0.12 / 0.15–0.23 / 0.26–0.36 (c) | §7: ΔT_oil,u ×(1+c), τ_oil ×(1+1.1c) |
| abnormal_internal_heating | physical | 18–72 | 2–4 / 5–8 / 9–13 K (q) | §7: ΔT_oil,u + q |
| oil_sensor_bias | sensor | 10–36 | 1.5–2.8 / 3.2–5.0 / 5.5–8.0 °C | observed oil + m (before quantisation) |
| oil_sensor_drift | sensor | 48–168 | 2.0–3.5 / 4.0–6.5 / 7.0–10.0 °C (terminal) | observed oil + m·(t_ev/t_ev,last), 0 → m linearly |
| oil_sensor_stuck | sensor | 4–14 | — | observed oil held at the observed value of the row before the event |
| power_quality_disturbance | electrical | 4–18 | 1.0–2.0 / 2.5–4.0 / 4.5–7.0 (s) | §5: phase V ×(1+0.004s·[1,−½,−½]), f + 0.02s·sin(πk/2), THD-V + 0.6s, THD-I + 0.9s |
| oil_leak | condition | 72–192 | 0.4–0.7 / 0.8–1.4 / 1.5–2.5 %/day | §8: level − r·(t_ev+0.5)/24; restored at event end |
| bushing_overheating | condition | 24–96 | 6–10 / 12–20 / 22–35 °C | §8: bushing target + m(0.4+0.6K²)·ramp(2 h) |
| vibration_anomaly | condition | 12–30 | 0.6–1.0 / 1.2–2.2 / 2.5–4.5 mm/s | §8: vibration + A(1+0.3K²) |
| communication_gap | data | 1.0–4.5 | — | observed rows in the window are deleted; first row after the gap is labelled |

Sensor faults touch only the observed oil channel; winding, bushing and oil level use latent oil, so they are
unaffected. Oil and winding respond physically to overload, cooling degradation and internal heating.

## 11. Event scheduling — stream 6 (timing, severity) and stream 7 (magnitude)

For each asset, for each partition in order FIT, CAL, TEST, place in this order: overload, phase_imbalance,
cooling_degradation, abnormal_internal_heating, oil_sensor_bias, oil_sensor_drift, oil_sensor_stuck,
power_quality_disturbance, oil_leak, bushing_overheating, vibration_anomaly, then 4 communication gaps. For each:

1. duration `U(dur_min, dur_max)` h (stream 6); rows = max(1, round(2·duration)); a gap reserves one extra recovery row;
2. start index uniform over `[first_row + 96, last_row − 96 − rows + 1]` (48 h split margin), redrawn until the window
   is ≥ 24 rows (12 h guard) from every already-placed event in that partition (stream 6);
3. non-gap events: severity drawn with P(low, medium, high) = (0.35, 0.40, 0.25) (stream 6), magnitude `U(range)`
   for that severity (stream 7).

Result: 360 events (8 assets × 3 splits × 15), all classes in every asset × split, no overlaps, no event crosses a
split boundary (minimum margin 48.0 h). `v3.0.2_event_windows.csv` lists every event with ID, class, severity,
magnitude, start, end, recovery row and row count.

## 12. Labels, engineered features, fit eligibility

**Labels** (evaluation only — `labels_are_runtime_inputs = false`):

| Column | Rule | Depends on observed telemetry? |
|---|---|---|
| `y_fault_type`, `y_fault_domain`, `y_severity`, `y_event_id` | event schedule; whole event window; gaps: recovery row only | No (oracle) |
| `y_anomaly` | `y_fault_type ≠ normal` | No |
| `y_thermal_alert_level` | `x_winding_temp_c`: ≥120 critical, ≥105 warning, ≥95 watch, else normal | **Yes — deterministic rule on an input** |
| `y_wti_alarm` | `x_winding_temp_c ≥ 105` | **Yes — deterministic rule on an input** |
| `y_fit_eligible` | see below | No (schedule + validity) |

The `communication_gap` label is equivalent to `x_minutes_since_previous > 30`. Do not report alert/alarm or gap
"detection" as model performance.

**Engineered features** (time-based; no rows are fabricated):

| Feature | Definition | When unavailable |
|---|---|---|
| `x_load_pu_lag_1h` | `x_load_pu` of the row whose timestamp is exactly t − 60 min | NaN (row missing) |
| `x_load_pu_rolling_6h` | mean of `x_load_pu` over rows with timestamp in (t − 6 h, t] | always ≥1 row (itself) |
| `x_oil_temp_rate_c_per_h` | (oil(t) − oil(t − 60 min)) / 1 h | NaN (row missing) |
| `x_minutes_since_previous` | minutes to previous emitted row of the same asset | NaN on the first row |
| `x_oil_rise_over_ambient_c`, `x_winding_rise_over_ambient_c` | observed − observed ambient | — |
| `x_hour_*`, `x_dayofyear_*` | sin/cos of h/24 and dayofyear/365.25 | — |

**`y_fit_eligible` = 1** iff all hold:
1. the row is outside every injected event window (all 11 non-gap classes);
2. the row is not a gap-recovery row and not within the 2 h after it;
3. the row is not within `3·τ_oil,r` after the end of an overload, cooling-degradation or internal-heating event
   (thermal state still elevated);
4. ambient, oil, winding, `x_load_pu` and apparent power are finite.

Eligible share: FIT 92.4 %, CAL 85.7 %, TEST 85.3 %. Never use `y_fit_eligible` at runtime; it exists so a calibration
pipeline can fit the normal thermal model on known-normal synthetic periods. A twin that cannot rely on it should
use its own data-quality checks; report which was used.

## 13. Data-quality stress benchmark — stream 8

`transformer_practical_schema_v3.0.2_with_dq.csv` = clean **raw** telemetry columns + fault labels + `y_dq_defect`,
`y_dq_id`. Engineered features are deliberately omitted (consumers recompute after their own cleaning). Defects
are placed only on normal rows ≥ 6 h from events/gaps and ≥ 12 h from each other. Per asset:

| Defect | Count | Mechanism |
|---|---:|---|
| SUPPLY_OUTAGE | 1 | 1–3 h: V, I, P, Q, S, neutral, load = 0; PF, f, THD, unbalance = blank; temperatures keep reading |
| MISSING_VALUES | 2 | 2–6 rows: 1–3 random raw columns blank |
| UNIT_ERROR_KW_AS_W | 1 | 3–8 h: kW × 1000 (creates P > S) |
| SPIKE_OIL_TEMP | 2 | single row oil = 250 °C (1st), −40 °C (2nd) |
| DQ_GAP_ROWS_MISSING | 1 | 3–8 h of rows deleted (no fault label; logged in DQ file only) |
| EXACT_DUPLICATE | 2 | identical row repeated |
| CONFLICTING_DUPLICATE | 2 | same timestamp repeated with oil + 3 °C and kVA × 1.2 |
| OUT_OF_ORDER | 1 | two adjacent rows swapped |
| TIMESTAMP_WRITTEN_AS_UTC | 1 | 4–8 rows: timestamp shifted −5 h 30 min but still suffixed +05:30 |

`v3.0.2_dq_defects.csv` lists every defect (asset, ID, type, start, end, rows). **The clean file contains none of these.**

## 14. Changes from v3.0.1

1. Authoritative published generator, config, seeds and equations (no `[FITTED]`/`[UNKNOWN]` items).
2. Winding exponent y = 1.6 at source.
3. `y_fit_eligible` added.
4. Oil-leak, bushing-overheating and vibration-anomaly mechanisms defined explicitly (§8, §10).
5. Lag, rolling and rate features are timestamp-based; unavailable → NaN.
6. Clean and DQ benchmarks separated; DQ adds outage, missing values, unit error, spikes, duplicates, out-of-order,
   timezone shift and unlabelled gaps.
7. Clean data: joint P/Q/S noise truncated to the admissible region (no P > S, no |Q| > S).
8. Oil level now follows oil thermal expansion (0.15 %/°C).
9. Independent RNG streams per asset and purpose; byte-identical reproducibility verified.

## 15. Known limitations

- All parameters are synthetic assumptions; thermal behaviour is a reduced-order model family, not a specific unit.
- Ambient and load are stylised; no holidays, monsoon outages, DER, EV charging or tariff effects.
- THD is a scalar benchmark feature; no harmonic spectrum or waveforms.
- Faults never overlap; no compound or cascading faults.
- Splits are temporal holdouts of the same 8 assets with continuous state: TEST measures later-time generalisation on
  known assets, not unseen transformers.
- Anomaly prevalence FIT 7.0 %, CAL 13.1 %, TEST 13.4 % (same event count over shorter splits).
- A twin using the same first-order thermal family will look better here than on real data; benchmark results do not
  substitute for field evaluation.

## 16. Reproduce

```bash
pip install numpy pandas scipy        # versions in dataset_manifest.json
python src/simulate_v3_0_2.py --config config/simulator_config_v3.0.2.json --out data
python src/validate_v3_0_2.py --config config/simulator_config_v3.0.2.json --data data
python src/project_cpri_schema.py --data data --asset TX_250_MIX     # optional CPRI-column demo files
sha256sum data/*.csv                  # compare with dataset_manifest.json
```
