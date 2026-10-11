# Signal dictionary

All listed signals are **simulated sensor-equivalent observations**, not field measurements. Generator calculations create coherent observations; runtime must still label derived features separately. Every scalar is tied to immutable raw observation bytes. Pressure is the documented current extension with unverified runtime alias; no static nameplate fields are streamed.

| Field/signal_id | Meaning | Unit | Phase | Applicability | Delivered GOOD range | Generation |
|---|---|---|---|---|---|---|
| voltage_l1_n | LV phase-to-neutral RMS | V | L1 | Both | 230.2578 to 250.6934 | Nominal 433/√3 with smooth load drop, small correlated variation; B late balanced sag |
| voltage_l2_n | LV phase-to-neutral RMS | V | L2 | Both | 230.2694 to 250.9551 | Nominal 433/√3 with smooth load drop, small correlated variation; B late balanced sag |
| voltage_l3_n | LV phase-to-neutral RMS | V | L3 | Both | 230.3082 to 251.1067 | Nominal 433/√3 with smooth load drop, small correlated variation; B late balanced sag |
| current_l1 | LV phase RMS current | A | L1 | Both | 0.0000 to 537.5085 | Coherent phase load allocation; exact zero during LV trip |
| current_l2 | LV phase RMS current | A | L2 | Both | 0.0000 to 530.5901 | Coherent phase load allocation; exact zero during LV trip |
| current_l3 | LV phase RMS current | A | L3 | Both | 0.0000 to 528.4613 | Coherent phase load allocation; exact zero during LV trip |
| neutral_current | LV fundamental neutral RMS | A | N | Both | 0.0000 to 92.4976 | Fundamental phasor sum of unequal currents; no harmonic neutral components |
| active_power_total | Total import active power | kW | asset | Both | 0.0000 to 371.3357 | S=sum(Vphase Iphase)/1000; P=S PF; Q=S sqrt(1−PF²); common sinusoidal phase angle |
| reactive_power_total | Total inductive reactive power | kvar | asset | Both | 0.0000 to 141.5835 | S=sum(Vphase Iphase)/1000; P=S PF; Q=S sqrt(1−PF²); common sinusoidal phase angle |
| apparent_power_total | Arithmetic sum of per-phase apparent powers | kVA | asset | Both | 0.0000 to 394.9202 | S=sum(Vphase Iphase)/1000; P=S PF; Q=S sqrt(1−PF²); common sinusoidal phase angle |
| power_factor_total | P/S true ratio for stipulated common displacement angle | 1 | asset | Both, energized only | 0.8161 to 0.9508 | S=sum(Vphase Iphase)/1000; P=S PF; Q=S sqrt(1−PF²); common sinusoidal phase angle |
| frequency | Upstream LV bus supply frequency | Hz | asset | Both, including open-breaker interval | 49.9820 to 50.0180 | 50 Hz plus small smooth upstream variation |
| ambient_temperature | External ambient temperature | Cel | asset | Both | 22.9748 to 32.8480 | Diurnal sinusoid with correlated meteorological variation |
| top_oil_temperature | Top-oil analog sensor observation | Cel | asset | Both | 32.0209 to 97.8413 | First-order state, current-squared heating, correlated 0.045°C sensor noise |
| oil_level_percent | Conservator gauge scale, not total tank volume percent | % | asset | A only | 66.0515 to 75.2132 | Reference inventory +0.23 percentage points/°C ×(bulk−40°C), small correlated noise |
| x_pressure_kpa_g | Tank gauge pressure relative to atmosphere | kPa | asset | B only; documented extension | 1.6969 to 34.1718 | 4+0.35×(bulk−40) kPa plus smooth offsets and pulse; four BAD +999 kPa values excluded from range |
| breaker_trip | Latched LV protective trip indication; Boolean | 1 | asset | Both | false/true | Discrete physical protective-trip indication; true at B frames 278–300 only |

GOOD denotes declared usable synthetic observations. BAD/OUT_OF_RANGE is limited to B pressure frames 361–364. Missing signals are absent, with no fictitious source timestamp/value; age-based STALE is to be computed by the application using the last observation. A oil is absent 361–376; B pressure absent 365–376. PF is absent throughout B trip because 0/0 is undefined. B has no oil gauge; A has no pressure sensor. No unrelated signal is invalidated. No UNCERTAIN or frame-level partition-quality flag is manufactured.

CSV nested-cell interpretation, transport timestamp and Boolean type-tag assumptions are described in schema_and_integration_notes.md. raw_sha256 hashes canonical compact sorted JSON bytes for the corresponding raw record, excluding the trailing newline.
