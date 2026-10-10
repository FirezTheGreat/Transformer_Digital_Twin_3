# Methodology — gridpulse_physics_synth v1.0.0

A focused, physics-based synthetic benchmark for the GridPulse distribution-transformer digital twin. It is separate from, and does not
modify, the CPRI v3.0.2 benchmark or any of its artifacts. Source IDs (S1…S14) refer to `SOURCES.md`.

Provenance classes used throughout: `SOURCE_DERIVED`, `FITTED` (from FIT), `CALIBRATED` (on CAL), `ENGINEERING_ASSUMPTION`,
`SCENARIO_SETTING`, `SYNTHETIC_GROUND_TRUTH`, `DERIVED`.

## 1. What this benchmark can and cannot support

| Can support | Cannot support |
|---|---|
| Deterministic software behaviour, data-quality handling and event lifecycles | Field fault-detection accuracy or generalisation to real transformers |
| Duration- and ambient-dependent thermal consequence of overload under the IEC 60076-7 top-oil model | Hot-spot temperature, insulation ageing, remaining life |
| Temperature-corrected oil-level and sealed-tank pressure trend detection under the declared geometry | Leak confirmation (a falling corrected level is evidence for a *suspected* leak only) |
| Through-fault current magnitude, clearing time and C57.109 Category I comparison under declared impedances | Mechanical withstand, transient waveforms, asymmetric peak current |
| Leakage-free FIT/CAL/TEST development and a TEST-only demo replay | Any claim about transformers or sites other than the four declared profiles |

## 2. Asset profiles

All four are three-phase, 50 Hz, 11 kV / 433 V (250 V line-to-neutral), Dyn11, ONAN, mineral oil, LV neutral brought out
(`SOURCE_DERIVED`, S7 §4.1). None represents a real manufacturer or nameplate.

| Field | DT-01 | DT-02 | DT-03 | DT-04 | Provenance |
|---|---|---|---|---|---|
| Role | Conservator baseline, residential | Commercial: peaks, overload, imbalance, short circuit | Hermetically sealed corrugated tank, pressure | Rural: slow leak, gauge fault, repair | SCENARIO_SETTING |
| Rated power (kVA) | 250 | 500 | 250 | 160 | SOURCE_DERIVED ratings offered in S7 |
| Rated LV current (A) | 333.3 | 666.7 | 333.3 | 213.3 | DERIVED: S/(√3·433) |
| Total loss at 50 % / 100 % load (W) | 980 / 2930 | 1510 / 4300 | 980 / 2930 | 670 / 1950 | SOURCE_DERIVED, S7 §10.1 (maximum allowable values) |
| Load loss Pk / no-load loss P0 (W) | 2600 / 330 | 3720 / 580 | 2600 / 330 | 1706.7 / 243.3 | DERIVED: Pk = (L100 − L50)/0.75, P0 = L100 − Pk |
| R = Pk/P0 | 7.88 | 6.41 | 7.88 | 7.01 | DERIVED |
| Impedance z (%) | 4.5 | 4.5 | 4.5 | 4.5 | ENGINEERING_ASSUMPTION (≥ 4.0 % minimum reported for ≤ 630 kVA, S6; S7 defers to IS 1180 tables not inspected) |
| r / x (%) | 1.04 / 4.38 | 0.74 / 4.44 | 1.04 / 4.38 | 1.07 / 4.37 | DERIVED: r = Pk/S, x = √(z² − r²) |
| Oil exponent x | 0.80 | 0.76 | 0.80 | 0.80 | SOURCE_DERIVED: S1 Table 1 (IEC values) for DT-01/03; S1 Table 2 identified units for DT-02 (400 kVA unit) and DT-04 (160 kVA unit) |
| Oil time constant τo (min) | 180 | 141 | 180 | 199 | as above |
| Rated top-oil rise Δθor (K) | 55.0 | 57.56 | 55.0 | 54.87 | as above |
| k11 | 1.0 | 1.0 | 1.0 | 1.0 | ENGINEERING_ASSUMPTION |
| Oil volume (L) | 210 | 320 | 210 | 170 | ENGINEERING_ASSUMPTION (order of magnitude consistent with a 400 kVA datasheet listing 220 kg oil, S14) |
| Oil system | Conservator 10 % of oil volume, 3 % normally held | same | Fully filled corrugated tank, no conservator, no gas cushion | Conservator as DT-01 | SOURCE_DERIVED S7 §17(iv) for conservators; DT-03 design is an ENGINEERING_ASSUMPTION outside S7 scope (S7 requires conservators ≥ 63 kVA for plain tanks) |
| Oil-level gauge | Conservator gauge with 4-20 mA output, % of conservator span, reference 30 % at 30 °C | same | none | same | SCENARIO_SETTING (reference temperature is an assumption) |
| Pressure sensor | none | none | Tank-cover transducer, kPa gauge (relative to atmosphere), + = above atmosphere | none | SCENARIO_SETTING |
| Protection | LV ACB with OTI trip; HV drop-out fuse; OTI alarm 90 °C / trip 100 °C; MOG low-level alarm 10 % | same | same + pressure alarm 25 kPa(g), pressure-relief device 35 kPa(g) | same | SCENARIO_SETTING (OTI 90/100 °C match one vendor example, S10) |
| Load profile, peak per-unit load | residential, 0.70 | commercial, 0.60 | mixed, 0.80 | rural (agricultural pumping), 0.82 | ENGINEERING_ASSUMPTION |

Pressure and oil level are deliberately not interchangeable: conservator assets have no pressure column values; the sealed asset has
no oil-level values (NaN, documented by `tank_type`).

## 3. Timeline, schema and units

- 180 days from 2025-01-01T00:00:00Z at 30-min intervals; 8,640 rows per asset, 34,560 total. Timestamps are UTC, ISO 8601, interval end.
  Load shapes use local time (UTC+05:30) because demand follows the local clock.
- Electrical quantities are interval means; temperatures, oil level and pressure are instantaneous samples at interval end; contacts are
  the state at interval end, `lv_breaker_trip` = 1 in the interval in which a trip occurred.
- Missing data are rows with NaN measurements and `dq_flag = COMM_LOSS`. Zero never encodes "unavailable". Genuine zeros occur: currents
  and power are 0 while the LV breaker is open, voltages are 0 while the HV fuse has operated. Power factor and unbalance are NaN when current is zero.

| Column | Unit | Meaning |
|---|---|---|
| `timestamp_utc`, `asset_id`, `partition` | – | Identity and FIT/CAL/TEST assignment |
| `dq_flag` | – | `OK` or `COMM_LOSS` (acquisition-system flag; sensor faults are *not* flagged) |
| `rated_kva`, `rated_lv_v_ll`, `impedance_pct`, `tank_type` | kVA, V, %, – | Operational metadata the utility knows |
| `v_l1n_v`…`v_l3n_v` | V | Line-to-neutral RMS voltages at the LV bus |
| `v_l12_v`, `v_l23_v`, `v_l31_v` | V | Line-to-line voltages, DERIVED assuming 120° phase displacement |
| `i_l1_a`…`i_l3_a`, `i_n_a` | A | Phase and neutral RMS currents |
| `p_kw`, `q_kvar`, `s_kva`, `pf` | kW, kvar, kVA, – | Total powers and power factor |
| `freq_hz` | Hz | System frequency |
| `v_unbalance_pct`, `i_unbalance_pct` | % | 100·max\|X_p − X̄\|/X̄ (maximum deviation from mean; declared definition) |
| `load_ratio`, `i_ratio_l1..l3` | pu | S/S_rated and I_p/I_rated |
| `ambient_c`, `top_oil_c` | °C | Ambient air and top-oil (PT100 transmitter) |
| `oil_level_pct` | % of conservator span | Gauge reading |
| `oil_level_ref_pct`, `oil_level_ref_temp_c` | %, °C | Gauge reference (30 % at 30 °C) |
| `oil_level_corrected_pct`, `oil_level_trend_pct_per_day` | %, %/day | DERIVED: level − 0.75·(top-oil − 30); trailing 24-h OLS slope |
| `tank_pressure_kpa_g` | kPa(g) | Sealed-tank pressure, gauge |
| `pressure_corrected_kpa_g`, `pressure_trend_kpa_per_day` | kPa, kPa/day | DERIVED: p − (Vβ/C)·(top-oil − 20); trailing 24-h slope |
| `lv_breaker_closed`, `lv_breaker_trip`, `hv_fuse_operated` | 0/1 | Breaker state, trip-in-interval, HV fuse state |
| `oti_alarm`, `oti_trip`, `oil_level_low_alarm`, `pressure_alarm`, `prd_operated` | 0/1 | Contacts from independent devices (unaffected by transmitter faults) |
| `protection_event_ref` | – | Relay event-record ID in the interval of a protection event (links to `fault_events.csv`) |

## 4. Electrical model

- Load: K(t) = K_peak · shape(local hour) · weekday factor · (1 + c_season·(T_daily_mean − 25 °C)) · daily log-normal factor (σ 0.06) ·
  (1 + AR(1) noise, σ 0.04). ENGINEERING_ASSUMPTION.
- Phase shares (1 + ε_p)/3 with a fixed per-asset ε (±4 %) plus small AR noise; imbalance scenarios add (+δ, −δ/2, −δ/2), which gives a current
  unbalance of ≈ δ.
- Supply: v_HV(t) = 1 + daily AR + intraday AR − evening sag + night rise (pu). LV no-load voltage = 250 V · v_HV · (1 + per-phase offset).
- Regulation: V_p = V0_p · (1 − K_p (r cos φ + x sin φ)), K_p = 3 S_p / S_rated (standard approximate regulation formula, DERIVED).
- I_p = S_p / V_p; S = Σ V_p I_p; P = S·pf; Q = S·sin φ. For balanced conditions this equals S = √3 V_LL I_L (checked).
- Neutral current: magnitude of the phasor sum of the phase currents at 0°, −120°, +120°, combined in quadrature with an assumed 3 % triplen
  component per phase. ENGINEERING_ASSUMPTION.

## 5. Thermal model

IEC 60076-7 top-oil differential equation in the form reproduced by S1 (Fig. 1) and S2 (Eq. 15):

    k11 · τo · dθo/dt = Δθor · [(1 + R K²)/(1 + R)]^x · (1 + η(t)) + G_sun(t) − (θo − θa)

- Solved with 5-min explicit Euler sub-steps; checked against the exact exponential step solution (p99 error 0.23 K).
- η(t): unmodelled heat-transfer variability, AR(1), sd 3 %; G_sun(t): tank solar gain up to 2 K at clear midday. Both are
  ENGINEERING_ASSUMPTIONs added so that the fitted model is not structurally identical to the truth.
- De-energised (HV fuse operated): losses zero, oil cools towards ambient. LV breaker open but energised: no-load losses remain (K = 0).
- Ambient: seasonal mean rising from 15 °C (January) to 34 °C (late May) and easing to 30 °C (late June), diurnal amplitude 5.5–7.5 K
  peaking at 15:00 local, day-level AR anomalies. Range 3.8–46.1 °C, within the S7 service conditions (max 55 °C). ENGINEERING_ASSUMPTION.
- OTI contacts: alarm at 90 °C, trip at 100 °C (trip opens the LV ACB; operator recloses when top-oil < 75 °C and ≥ 2 h have passed).
  SCENARIO_SETTINGs. Consequences such as OTI trips are produced by the physics, not scripted, and recorded as derived ground truth.
- No hot-spot, winding temperature or ageing is simulated. The CPRI-style "simulated WTI" channel is omitted on purpose.

## 6. Oil level (conservator assets)

Two independent mechanisms:

    V_cons(t) = 0.03·V + V·β·(θ_bulk − 30 °C) − V_lost(t)
    level(t)  = 100 · V_cons / (0.10·V)                          [% of conservator span]
    θ_bulk    = θa + 0.8·(θo − θa)

- β = 7.5 × 10⁻⁴ K⁻¹ (ENGINEERING_ASSUMPTION inside the 7–8 × 10⁻⁴ K⁻¹ typical range, S8). Gauge sensitivity is 0.75 % per K of bulk oil.
- 10 % / 3 % conservator sizing from S7 §17(iv). With these values the true level on DT-01/DT-02 stays between 19 % and 74 % of span over the season
  (DT-04 falls to 7.9 % only at the end of a leak), so the gauge never saturates, and the level at −5 °C stays above zero (S7 §17(vi)).
- Leak: V_lost grows at the declared L/day from onset; the repair (gasket fix and top-up) restores inventory. Rates are SCENARIO_SETTINGs
  and live only in the ground truth.
- The correction published in the CSV uses measured top-oil only (what a field engineer can do), so a small daily residual remains.

## 7. Sealed-tank pressure (DT-03 only)

Fully filled corrugated tank, linear tank compliance C (L/kPa):

    p(t) = (V·β·(θ_bulk − 20 °C) − V_lost(t)) / C        [kPa gauge; filled at 0 kPa(g), 20 °C]

- C = 0.36 L/kPa, chosen so that the extreme bulk temperature in the scenario set stays inside the ±0.4 kg/cm² (±39.2 kPa) operating
  envelope that S7 §16.2 sets for tanks. ENGINEERING_ASSUMPTION; not validated against a manufacturer curve.
- Sensitivity 0.44 kPa per K of bulk oil. An oil weep lowers pressure at a given temperature by V_lost/C (0.25 L/day → 0.69 kPa/day).
- Pressure alarm 25 kPa(g), pressure-relief device 35 kPa(g): SCENARIO_SETTINGs below the S7 envelope. The PRD never operates in this dataset.
- Arbitrary pressure spikes (e.g. internal arcing gas) are not simulated because no defensible model was available.
- S9 supports why pressure and temperature monitoring of sealed tanks matters (high pressure stresses seals, low pressure the internal dielectric seal).

## 8. Short-circuit and protection (`fault_events.csv`)

Event-level only; the 30-min telemetry shows the consequence (breaker state, zero current, outage, restoration), never transients.

    I_fault [pu] = 1 / (z_T + z_source + z_cable),  z_source = S_rated / S_k,  z_cable = Z_cable / (433² / S_rated),  c = 1.0
    I_fault [kA] = I_fault [pu] · I_rated

- Symmetrical three-phase fault; impedances added arithmetically (same X/R assumed). Source fault level at 11 kV: 250 MVA (ENGINEERING_ASSUMPTION).
- IEEE C57.109 Category I (15–500 kVA three-phase) applies to all four assets (S4 Table I). For Category I the maximum current is based on the
  transformer impedance only (S4). The through-fault allowance t = 1250/I² is stated by S4 for 25–40 pu; our currents are below 25 pu
  (transformer-only 22.2 pu), so we use the conservative 2 s bound (the curve is monotone and equals 2 s at 25 pu, S4 worked example).
- Protection (SCENARIO_SETTING): LV ACB clears in 0.1–0.2 s; if it fails, the HV drop-out fuse clears in 1.0–1.5 s and the transformer is de-energised.

| Event | Fault | I_fault | Clearing | Outcome |
|---|---|---|---|---|
| FIT DT-02 | LV bus, 3-phase bolted | 14.19 kA (21.3 pu) | 0.2 s ACB | Within allowance |
| CAL DT-02 | LV feeder 0.012 Ω, 3-phase | 8.44 kA (12.7 pu) | 0.1 s ACB | Within allowance |
| TEST DT-02 | LV bus, ACB fails | 14.19 kA (21.3 pu) | 1.0 s HV fuse | Within 2 s bound; de-energised 6 h |

Nothing here establishes the actual withstand capability of a transformer or predicts a short circuit from half-hourly data.

## 9. Measurement layer and data quality

| Signal | Noise (1σ) | Resolution |
|---|---|---|
| Voltage | 0.3 V | 0.1 V |
| Current | 0.3 % | 0.1 A |
| Power factor | 0.002 | 0.001 |
| Frequency | 0.003 Hz | 0.01 Hz |
| Ambient / top-oil | 0.2 / 0.15 K | 0.1 K |
| Oil level | 0.25 % of span | 0.1 % |
| Pressure | 0.15 kPa | 0.1 kPa |

Sensor faults (`TOPOIL_FROZEN`, `TOPOIL_SPIKE`, `GAUGE_STUCK`) alter the transmitter value only; independent contacts keep working. The
frequency channel genuinely repeats at 0.01 Hz resolution, so a fault check must be resolution-aware.

## 10. Scenario design

37 scenarios, every kind instantiated separately in FIT, CAL and TEST with different timing and magnitude, assigned to assets whose design
supports them. The full manifest with intervals, injected parameters and physics outcomes is in `SCENARIOS_AND_VALIDATION.md` §2.

| Kind | Asset | FIT / CAL / TEST magnitude |
|---|---|---|
| Normal operation, normal oil expansion | all | everywhere outside scenario windows |
| BRIEF_PEAK | DT-02 | 1.30 pu 1 h and 1.25 pu 1.5 h / 1.28 pu 1.5 h / 1.32 pu 1 h |
| SUSTAINED_OVERLOAD | DT-02 | 1.12 pu 5 h / 1.15 pu 5 h / 1.18 pu 6 h |
| HIGH_PRESSURE_LOAD | DT-03 | 1.12 / 1.15 / 1.15 pu for 6 h |
| PHASE_IMBALANCE | DT-02 | +30 % 96 h / +25 % 72 h / +35 % 96 h |
| VOLT_DEV | DT-01 | −9 % 8 h / −11 % 6 h / −10 % 7 h |
| OIL_LEAK + repair | DT-04 | 0.12 L/d 30 d / 0.20 L/d 18 d / 0.22 L/d 18 d |
| SEALED_LEAK + repair | DT-03 | 0.15 / 0.20 / 0.25 L/d |
| GAUGE_STUCK | DT-04 | 96 h / 72 h / 96 h |
| TOPOIL_FROZEN, TOPOIL_SPIKE, COMM_LOSS | DT-01 | 10 h, +20 °C, 3 h / 8 h, +25 °C, 5 h / 12 h, +22 °C, 4 h |
| SHORT_CIRCUIT + restoration | DT-02 | see §8 |

For loading scenarios the expected thermal and pressure consequence is not assumed: it is the simulated outcome (top-oil and pressure maxima
and whether alarm settings were crossed), recorded as SYNTHETIC_GROUND_TRUTH.

## 11. FIT / CAL / TEST construction

- Chronological per asset: FIT days 0–107 (5,184 rows), CAL 108–143 (1,728), TEST 144–179 (1,728). TEST is the hottest period, so models fitted
  in winter and spring are tested on extrapolation in summer.
- The scenario table is a constant in the generator, fixed before simulation. No scenario crosses a boundary; every scenario keeps ≥ 12 h margin.
- Ground truth never enters the telemetry. Trailing statistics (24-h means, 3-day slopes) may use earlier telemetry across a partition boundary,
  as a live system would; no future data are used.
- Protocol: `--stage dev` builds the data, fits on FIT, calibrates and reports on CAL and never touches TEST. `--stage final` records the
  configuration SHA-256, then evaluates TEST once and runs GridPulse on TEST.
- Development changes made before the final run (all on FIT/CAL evidence): peak loading reduced (DT-01 0.78 → 0.70, DT-02 0.72 → 0.60) so that
  normal operation stays below the OTI alarm; unmodelled thermal effects added; supply-voltage drift reduced so that normal operation stays inside
  the ±6 % band; expected loading outcomes switched from assumed text to physics ground truth after the CAL brief peak legitimately crossed 90 °C.

| Parameter | Type | Where |
|---|---|---|
| R, Δθor/τo/x of the truth, conservator sizing, voltages, ratings, losses | SOURCE_DERIVED (some via declared transfer) | §2 |
| Thermal (x, τo, Δθor) used by detectors | FITTED on FIT, R fixed from S7 | grid search + LS with outlier trimming |
| Level and pressure models (a + b·θo + c·θa) | FITTED on FIT | robust LS |
| Leak thresholds (drop, slope) | CALIBRATED on CAL | zero CAL false alarms, all CAL leaks detected, smallest delay |
| OTI, pressure, low-level, voltage band, imbalance threshold | SCENARIO_SETTING / declared engineering check | fixed a priori |
| Fault currents, I²t, clearing | DERIVED | §8 |
| Injected magnitudes, onsets, physics outcomes | SYNTHETIC_GROUND_TRUTH | manifest only |

## 12. Reference detectors (defined in `generate_dataset.py`)

| Detector | Rule | Development |
|---|---|---|
| Thermal limit | measured top-oil ≥ 90 °C | none (setting) |
| Projected exceedance (information) | load ≥ 1.0 pu and the 2-h projection with the present load held ≥ 90 °C | thermal model FITTED |
| 2-h conditional projection | 4-step free run with measured future load and ambient vs persistence | FITTED |
| Top-oil spike | jump ≥ 8 K that reverts within 2 K at the next sample | fixed |
| Frozen / stuck sensor | 4 h with change < half a resolution step while the model expects ≥ 1 K (top-oil) or ≥ 1 % (level) | fixed, resolution-aware |
| Oil leak / sealed weep | residual of the FIT level/pressure model: 24-h mean minus the 3–7-day-old median ≤ −drop and 3-day slope ≤ −slope; suppressed during gauge faults and data gaps | thresholds CALIBRATED |
| Phase imbalance | i_unbalance ≥ 20 % for 2 samples at load ≥ 0.2 pu | fixed |
| Voltage deviation | any phase outside ±6 % of 250 V for 2 samples | fixed (band to verify) |
| High pressure | measured ≥ 25 kPa(g) | setting |
| Advisory closure | an alarm episode closes after 12 h without alarm | fixed |

A falling temperature-corrected level supports a *suspected leak* advisory with a field-inspection action; it does not confirm a leak. Pressure
alone does not confirm a leak either.

## 13. Demo consumption and GridPulse integration

- The demo must replay `partition == TEST` rows only, in timestamp order, per asset, through the GridPulse input adapter. It must not receive
  `SCENARIOS_AND_VALIDATION.md`, `fault_events.csv` calculated fields as hidden inputs, or any FIT/CAL labels. `protection_event_ref` is a
  legitimate relay-record reference.
- The validation harness maps CSV columns to GridPulse canonical signal IDs (`voltage_v1`, `current_i1`, `neutral_current`,
  `apparent_power_total`, `top_oil_temperature`, `oil_level_pct`, `oil_temp_alarm_flag`, `oil_temp_trip_flag`, `mog_alarm`, `breaker_trip`, …),
  builds the production engines exactly as `deps.build_runtime_reducer` does with an asset profile (rating, 30-min cadence) and an UNCALIBRATED
  thermal artifact, and scores outputs against the ground truth afterwards. GridPulse code was not modified.
- To use the dataset in the live server, GridPulse needs a small adapter for this schema and its own FIT/CAL thermal calibration (see
  `SCENARIOS_AND_VALIDATION.md` §10 for the required fixes).

## 14. Reproducibility

`python data/gridpulse_synthetic_v1/generate_dataset.py --stage final` (Python ≥ 3.11, numpy, pandas; the GridPulse step also needs the backend
package). Master seed 20261010; per-asset, per-component generators `default_rng([seed, asset, component])`. CSVs are written with `\n` line
endings and fixed float formatting so the SHA-256 values in `SCENARIOS_AND_VALIDATION.md` reproduce on any OS. The final stage regenerates the data
in memory a second time and checks the hash.

## 15. Simplifications and limits

See `SCENARIOS_AND_VALIDATION.md` §11. In short: first-order top-oil model with mild declared mismatch; no hot-spot; linear conservator and tank
geometry; constructed ambient and load profiles; symmetrical faults only; several declared assumptions (impedance, oil volume, β, k11, bulk-oil
fraction, ±6 % band) that a domain mentor should confirm.
