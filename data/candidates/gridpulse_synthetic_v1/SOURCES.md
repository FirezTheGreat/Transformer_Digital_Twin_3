# Sources — gridpulse_physics_synth v1.0.0

"Inspected" means the full text of the cited part was read during this work. Where only an abstract, a search summary or a secondary
reproduction was available, that is stated, and nothing beyond it is attributed to the source. No clause numbers or values were taken from
standards that were not inspected.

## Bibliography

| ID | Citation | Type | Access | What it supports in this dataset | Limits |
|---|---|---|---|---|---|
| S1 | S. Najar, J.-F. Tissier, S. Cauet, E. Etien, "Improving thermal model for oil temperature estimation in power distribution transformers," *Applied Thermal Engineering*, vol. 119, pp. 73–78, 2017. doi:10.1016/j.applthermaleng.2017.03.061 | Peer-reviewed | Full text inspected | IEC 60076-7 top-oil model structure (Fig. 1); IEC parameter values for ONAN 50–1000 kVA as reported by the authors, Table 1: x = 0.8, R = 5, τo = 180 min, Δθor = 55 K; identified parameters of real 160/400/800 kVA ONAN units (20 kV/400 V), Table 2 (160 kVA: x 0.80, τo 199 min, Δθor 54.87 K; 400 kVA: x 0.76, τo 141 min, Δθor 57.56 K). Also: ±10 °C error of generic IEC parameters motivates per-asset fitting | k11 not tabulated; units are French 20 kV designs, transferred to 11 kV profiles by assumption |
| S2 | F. Tembo, F. Bragone, T. Laneryd, M. Barreau, K. Morozovska, "Data-Driven vs Traditional Approaches to Power Transformer's Top-Oil Temperature Estimation," arXiv:2501.16831, 2025 | Preprint | Full text inspected | IEC 60076-7 top-oil differential equation with k11·τo (Eq. 15) and its finite-difference solution; cites IEC 60076-7:2017 | Power-transformer case study; preprint |
| S3 | IEC 60076-7, *Power transformers – Part 7: Loading guide for mineral-oil-immersed power transformers* (2018 edition current) | Normative | **Not inspected** (paywalled) | Cited only through S1 and S2 | Temperature-limit tables were not verified; no IEC limit is claimed |
| S4 | A. Kazemi, C. Labuschagne, "Protecting Power Transformers From Common Adverse Conditions," Schweitzer Engineering Laboratories; 32nd Western Protective Relay Conference 2005, revised edition 2026 | Manufacturer technical paper | Full text inspected | IEEE C57.109 categories (Table I: Category I = 15–500 kVA three-phase); Category I curve I²t = 1250 for 25–40 pu, maximum current from transformer impedance only; worked example 4 % → 25 pu → 2 s; Category II/III frequent/infrequent curves; IEEE aging factor F_AA with constant 15,000 and 110 °C reference (not used for generation); calculated-vs-measured top-oil as a cooling-efficiency indicator (motivates residual-based checks) | Secondary reproduction of IEEE C57.109/C57.91; curve below 25 pu not given, hence the conservative 2 s bound |
| S5 | IEEE Std C57.109, *Guide for Liquid-Immersed Transformers Through-Fault-Current Duration* | Normative guide | **Not inspected** | Cited through S4 only | – |
| S6 | IEC 60076-5, *Power transformers – Part 5: Ability to withstand short circuit*, Table 1 (recognised minimum short-circuit impedance) | Normative | **Not inspected**; values seen only in engineering-forum posts (IET EngX, eng-tips) via search | Context only: 4.0 % minimum for ≤ 630 kVA two-winding units is consistent with the assumed 4.5 % | Not used as a source for a number |
| S7 | Kerala State Electricity Board Ltd, Supply Chain Management, *Technical Specification: Distribution Transformer 11kV/433V, 100, 160, 250 & 500 kVA*, Doc. SCM-SPEC/XD/DT2 Rev 0.2, effective 17-11-2021. https://kseb.in (Downloadtemsuppy) | Utility procurement specification | Full text inspected | 11 kV / 433–250 V, Dyn11, ONAN, 50 Hz (§4.1); service conditions: max ambient 55 °C, max daily average 40 °C, yearly weighted average 32 °C (§3.1); maximum total losses at 50 % and 100 % load (§10.1), used to derive Pk, P0, R and r; tank pressure in operation ≤ 0.4 kg/cm² positive or negative (§16.2.1–16.2.2); conservator volume 10 % of oil, normally 3 % held, minimum level at −5 °C above sump (§17); oil to IS 335:2018 (§8.1); impedance per IS 1180 tables (§12) | IS 1180 impedance and temperature-rise tables not inspected; sealed design of DT-03 is outside this spec |
| S8 | ASTM D3487, *Standard Specification for Mineral Insulating Oil Used in Electrical Apparatus*, table of typical properties (coefficient of expansion 0.0007–0.0008 per °C, 25–100 °C, by ASTM D1903) | Normative (ASTM) | **Not inspected** (download failed); value seen in a search summary of the 2004 edition | Range within which β = 7.5 × 10⁻⁴ K⁻¹ was chosen (ENGINEERING_ASSUMPTION) | Product-specific values vary; measure per D1903 / DL/T 1204 |
| S9 | A. Tonin, F. Stevanato, "Sealed transformer monitoring," *Transformers Magazine*, vol. 9, no. SE1, pp. 64–67, 2022. https://hrcak.srce.hr/277835 | Trade journal | Abstract only | Sealed distribution transformers with and without gas cushion; sealed tanks must tolerate higher pressure (seal stress) and low pressure risks the internal dielectric seal; pressure and temperature monitoring are crucial | No pressure values or models taken from it |
| S10 | Automation 2000 DGPT2-X transformer protection relay, parts-supplier listing (kc-co.com) | Vendor listing | Search summary only (page returned 403) | Example device for completely filled transformers with 0.2 bar pressure threshold and 90 °C / 100 °C temperature thresholds; shows the OTI 90/100 °C SCENARIO_SETTINGs are plausible | One vendor example; settings are per order |
| S11 | IEEE Std C57.91, *Guide for Loading Mineral-Oil-Immersed Transformers* | Normative guide | **Not inspected** | Aging factor only through S4; not used in generation | – |
| S12 | IEEE Std C57.152 (2013, superseded by 2025), *Guide for Diagnostic Field Testing of Fluid-Filled Power Transformers, Regulators, and Reactors* | Normative guide | **Not inspected** (only catalogue/search information) | Nothing numerical. Oil-level temperature correction is implemented from volume expansion (§6), not from this guide | – |
| S13 | Central Electricity Authority (Measures relating to Safety and Electric Supply) Regulations, 2010 (India) | Regulation | **Not inspected**; the ±6 % LV supply band could not be confirmed | The ±6 % voltage band is an assumption marked "to verify" | – |
| S14 | Zhiyue Group S11-M-400/10 distribution transformer datasheet (10/0.4 kV, 400 kVA): impedance 4.5 %, oil mass 220 kg | Manufacturer datasheet | Search summary only | Order of magnitude for oil volumes and a common 4.5 % impedance | Not an 11 kV / IS-compliant unit |

Basic circuit relations (S = √3·V_LL·I_L, P/Q/S triangle, approximate regulation ΔV/V ≈ K(r cos φ + x sin φ), per-unit fault current
I = 1/z, phasor neutral current) are standard electrical-engineering relations and are classed `DERIVED`; no specific source is cited for them.

## Mapping: equations, parameters and assumptions → sources

| Item (METHODOLOGY §) | Value / form | Class | Source |
|---|---|---|---|
| Top-oil ODE (§5) | k11·τo·dθo/dt = Δθor·[(1+RK²)/(1+R)]^x − (θo − θa) | SOURCE_DERIVED | S1 Fig. 1, S2 Eq. 15 (IEC 60076-7 via S3) |
| x, τo, Δθor for DT-01/03 (§2) | 0.8, 180 min, 55 K | SOURCE_DERIVED | S1 Table 1 |
| x, τo, Δθor for DT-02 (§2) | 0.76, 141 min, 57.56 K (400 kVA unit applied to a 500 kVA profile) | SOURCE_DERIVED + ENGINEERING_ASSUMPTION (transfer) | S1 Table 2 |
| x, τo, Δθor for DT-04 (§2) | 0.80, 199 min, 54.87 K | SOURCE_DERIVED | S1 Table 2 |
| k11 | 1.0 | ENGINEERING_ASSUMPTION | – |
| R per asset | from maximum losses at 50 % / 100 % load | DERIVED from SOURCE_DERIVED | S7 §10.1 |
| Unmodelled thermal effects | η sd 3 %, solar gain ≤ 2 K | ENGINEERING_ASSUMPTION | motivated by S1 (±10 °C with generic parameters) and S4 (calculated vs measured top-oil) |
| Ratings, voltages, vector group, cooling | 160/250/500 kVA, 11 kV/433 V, Dyn11, ONAN | SOURCE_DERIVED | S7 §4.1 |
| Ambient range | 3.8–46.1 °C constructed | ENGINEERING_ASSUMPTION within S7 §3.1 | S7 |
| Impedance | 4.5 % | ENGINEERING_ASSUMPTION | context S6, S14 |
| Oil expansion β | 7.5 × 10⁻⁴ K⁻¹ | ENGINEERING_ASSUMPTION within reported range | S8 |
| Conservator sizing | 10 % capacity, 3 % normal content | SOURCE_DERIVED | S7 §17(iv) |
| Reference temperature for 3 % | 30 °C | ENGINEERING_ASSUMPTION | – |
| Bulk-oil fraction | 0.8 | ENGINEERING_ASSUMPTION | – |
| Sealed-tank compliance | 0.36 L/kPa | ENGINEERING_ASSUMPTION constrained by envelope | S7 §16.2 (±0.4 kg/cm²); relevance of pressure monitoring S9 |
| Pressure alarm / PRD | 25 / 35 kPa(g) | SCENARIO_SETTING | below S7 envelope |
| OTI alarm / trip | 90 / 100 °C | SCENARIO_SETTING | plausible per S10 |
| Fault current | I = 1/(z_T + z_s + z_c), c = 1.0, symmetrical | DERIVED | – |
| Source fault level | 250 MVA at 11 kV | ENGINEERING_ASSUMPTION | – |
| Through-fault category and allowance | Category I; 1250/I² for 25–40 pu; conservative 2 s below 25 pu | SOURCE_DERIVED (secondary) | S4 (IEEE C57.109 via S5) |
| Clearing times | ACB 0.1–0.2 s, HV fuse 1.0–1.5 s | SCENARIO_SETTING | – |
| Voltage band | ±6 % of 250 V | ENGINEERING_ASSUMPTION (to verify) | S13 not confirmed |
| Imbalance definition and 20 % threshold | max deviation from mean | Declared definition / SCENARIO_SETTING | – |
| Load shapes, PF, harmonics, noise, resolutions | see METHODOLOGY §4, §9 | ENGINEERING_ASSUMPTION | – |
