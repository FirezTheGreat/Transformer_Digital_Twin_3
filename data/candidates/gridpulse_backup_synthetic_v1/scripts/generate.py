#!/usr/bin/env python3
"""Generate isolated, document-grounded demo observations. No application imports."""
import argparse
import csv
import hashlib
import json
import math
import platform
import random
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATASET = 'gridpulse_backup_story_v1'
VERSION = '1.0.0'
SEED = 20261011
START = datetime(2025, 1, 1, tzinfo=timezone.utc)
ASSETS = ['GP-BACKUP-A-CONS-315', 'GP-BACKUP-B-SEAL-250']
NS = uuid.UUID('bd5722b6-c5d1-53f8-85ae-b56f5c56929b')
ENVELOPE = ['schema_version', 'event_id', 'asset_id', 'event_time_utc',
            'received_time_utc', 'source', 'measurements', 'event_quality_flags', 'mapping_version']
SIGNALS = {
    'voltage_l1_n': ('V', 'L1', 'LV phase-to-neutral RMS', 'Both'),
    'voltage_l2_n': ('V', 'L2', 'LV phase-to-neutral RMS', 'Both'),
    'voltage_l3_n': ('V', 'L3', 'LV phase-to-neutral RMS', 'Both'),
    'current_l1': ('A', 'L1', 'LV phase RMS current', 'Both'),
    'current_l2': ('A', 'L2', 'LV phase RMS current', 'Both'),
    'current_l3': ('A', 'L3', 'LV phase RMS current', 'Both'),
    'neutral_current': ('A', 'N', 'LV fundamental neutral RMS', 'Both'),
    'active_power_total': ('kW', None, 'Total import active power', 'Both'),
    'reactive_power_total': ('kvar', None, 'Total inductive reactive power', 'Both'),
    'apparent_power_total': ('kVA', None, 'Arithmetic sum of per-phase apparent powers', 'Both'),
    'power_factor_total': ('1', None, 'P/S true ratio for stipulated common displacement angle', 'Both, energized only'),
    'frequency': ('Hz', None, 'Upstream LV bus supply frequency', 'Both, including open-breaker interval'),
    'ambient_temperature': ('Cel', None, 'External ambient temperature', 'Both'),
    'top_oil_temperature': ('Cel', None, 'Top-oil analog sensor observation', 'Both'),
    'oil_level_percent': ('%', None, 'Conservator gauge scale, not total tank volume percent', 'A only'),
    'x_pressure_kpa_g': ('kPa', None, 'Tank gauge pressure relative to atmosphere', 'B only; documented extension'),
    'breaker_trip': ('1', None, 'Latched LV protective trip indication; Boolean', 'Both'),
}

def iso(t):
    return t.isoformat(timespec='seconds').replace('+00:00', 'Z')

def stamp(frame):
    return iso(START + timedelta(minutes=30 * (frame - 1)))

def dumps(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')

def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)

def interp(frame, knots):
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x0 <= frame <= x1:
            q = (frame - x0) / (x1 - x0)
            q = q * q * (3 - 2 * q)
            return y0 + q * (y1 - y0)
    return knots[-1][1]

def ar_noise(rng, length, sd, rho):
    value = 0.0
    out = []
    for _ in range(length):
        value = rho * value + rng.gauss(0, sd * math.sqrt(1 - rho * rho))
        out.append(value)
    return out

PROFILES = {
    ASSETS[0]: {'rated_kva': 315, 'tank_construction': 'CONSERVATOR', 'oil_gauge_type': 'MAGNETIC_PERCENT_SCALE',
                'thermal': {'beta_0_c': 8, 'beta_1_c': 37, 'tau_hours': 3.6},
                'bulk_oil': {'beta_0_c': 6, 'beta_1_c': 28, 'tau_hours': 5.0},
                'gauge_sensitivity_pct_per_c': 0.23, 'oil_reference_temperature_c': 40.0,
                'oil_reference_level_pct': 67.0},
    ASSETS[1]: {'rated_kva': 250, 'tank_construction': 'SEALED_CORRUGATED', 'oil_gauge_type': 'NOT_FITTED',
                'thermal': {'beta_0_c': 7, 'beta_1_c': 32, 'tau_hours': 3.0},
                'bulk_oil': {'beta_0_c': 5, 'beta_1_c': 24, 'tau_hours': 4.2},
                'pressure_baseline_kpa_at_40c': 4.0, 'pressure_sensitivity_kpa_per_c': 0.35,
                'pressure_reference_temperature_c': 40.0, 'pressure_sensor_range_kpa_g': [-20, 80]},
}

KNOTS_A = [(1,.60),(50,.60),(70,.80),(100,.99),(115,1.13),(145,1.16),(170,.87),(200,.63),
           (220,.97),(240,1.25),(270,1.23),(300,1.21),(315,.77),(345,.61),(400,.61),
           (425,.90),(445,.88),(465,.62),(500,.60)]
KNOTS_B = [(1,.55),(50,.55),(100,.73),(130,.85),(150,.82),(180,.62),(200,.56),
           (225,.70),(250,.82),(277,.85),(278,0),(300,0),(313,.50),(350,.54),
           (400,.54),(425,.75),(445,.74),(465,.54),(500,.54)]
IMB_A = [(1,.01),(400,.01),(412,.12),(436,.16),(448,.10),(465,.01),(500,.01)]
IMB_B = [(1,.012),(50,.012),(100,.065),(115,.20),(145,.22),(180,.03),(200,.01),
         (250,.045),(277,.06),(301,.01),(500,.01)]
PRESSURE_OFFSET = [(1,0),(50,0),(100,2),(112,12),(145,12),(175,1),(200,0),
                   (250,0),(260,24),(277,26),(278,25),(288,7),(300,1),(315,0),(500,0)]

EVENTS = [
    (0, 'A-LOAD-1', 'PHYSICAL_CONDITION', 51, 200, ['apparent_power_total','current_l1','current_l2','current_l3','top_oil_temperature'], 'Gradual loading rise, sustained thermal stress, and load-led recovery.', 'Load dispatch improves from frame 151; thermal state cools with inertia.'),
    (0, 'A-OIL-LOSS', 'PHYSICAL_CONDITION', 101, 300, ['oil_level_percent'], 'Synthetic oil inventory loss: -1 gauge percentage point/day, increasing to -1.8/day from frame 221.', 'Physical loss is generator truth only; declining corrected level supports inspection, not confirmed runtime leakage.'),
    (0, 'A-LOAD-2', 'PHYSICAL_CONDITION', 201, 350, ['apparent_power_total','top_oil_temperature'], 'Recurring elevated loading and thermal exposure, followed by gradual unloading.', 'Authorized synthetic load redistribution begins frame 301.'),
    (0, 'A-TOPUP', 'SYNTHETIC_INTERVENTION', 301, 306, ['oil_level_percent'], 'Six gauge percentage points added over 2.5 h during hypothetical maintenance.', 'Synthetic top-up and leak repair; no automatic application feedback is fabricated.'),
    (0, 'A-LEVEL-MISSING', 'DATA_QUALITY', 361, 376, ['oil_level_percent'], 'Level channel absent for 16 frames while all other channels remain current.', 'No imputation; last available level can become stale according to application policy.'),
    (0, 'A-PHASE-2', 'PHYSICAL_CONDITION', 401, 465, ['current_l1','current_l2','current_l3','neutral_current'], 'New uneven phase demand; neutral current is calculated from the fundamental phasor sum.', 'Rebalancing from frame 451 to 465.'),
    (1, 'B-PHASE-1', 'PHYSICAL_CONDITION', 51, 200, ['current_l1','current_l2','current_l3','neutral_current'], 'Phase demand imbalance grows, persists and subsequently recovers.', 'Phase load redistribution between frames 151 and 200.'),
    (1, 'B-PRESSURE-1', 'PHYSICAL_CONDITION', 51, 200, ['x_pressure_kpa_g'], 'Temperature-aware pressure baseline plus a smooth, sustained synthetic accommodation offset.', 'Offset relaxation represents a simplified construction-specific scenario, not a diagnosed internal fault.'),
    (1, 'B-PRESSURE-PULSE', 'PHYSICAL_CONDITION', 224, 226, ['x_pressure_kpa_g'], 'Short smooth pressure pulse peaking at +9 kPa above baseline.', 'No contact operation; transient versus sustained classification is runtime-dependent.'),
    (1, 'B-PRESSURE-2', 'PHYSICAL_CONDITION', 251, 315, ['x_pressure_kpa_g'], 'Sustained pressure offset preceding an independent protective trip; then gradual relaxation.', 'Synthetic pressure-source removal at trip and hypothetical engineering intervention; no universal threshold is asserted.'),
    (1, 'B-TRIP', 'DISCRETE_PROTECTION', 278, 300, ['breaker_trip','current_l1','current_l2','current_l3','active_power_total','reactive_power_total','apparent_power_total'], 'LV protective trip indication held true; downstream currents and powers are zero.', 'Inspection and physical contact reset at frame 301 followed by gradual re-energization. Application latch clearance still requires actual authorized feedback.'),
    (1, 'B-PRESSURE-BAD', 'DATA_QUALITY', 361, 364, ['x_pressure_kpa_g'], 'Pressure sensor value fixed at +999 kPa and marked BAD/OUT_OF_RANGE.', 'Only the pressure channel is unusable; other measurements are preserved.'),
    (1, 'B-PRESSURE-MISSING', 'DATA_QUALITY', 365, 376, ['x_pressure_kpa_g'], 'Pressure channel absent for 12 frames following sensor malfunction.', 'Sensor returns at frame 377 without filling the missing history.'),
    (1, 'B-SUPPLY-2', 'PHYSICAL_CONDITION', 401, 465, ['voltage_l1_n','voltage_l2_n','voltage_l3_n','power_factor_total','reactive_power_total'], 'New balanced supply-voltage reduction and lower PF; temperature remains governed by phase-current losses.', 'Synthetic feeder voltage restoration and downstream reactive-demand improvement between frames 451 and 465.'),
]

def generate_frames():
    events, raw, truth = [], [], []
    for ai, asset in enumerate(ASSETS):
        profile = PROFILES[asset]
        rng = random.Random(SEED + 1009 * ai)
        nz = {name: ar_noise(rng, 500, sd, rho) for name, sd, rho in
              [('load',.006,.87),('ambient',.16,.94),('voltage',.001,.85),
               ('pf',.002,.91),('sensor',.045,.77),('oil',.025,.87),('pressure',.07,.85)]}
        top, bulk = None, None
        reference_level = 67.0
        for j in range(500):
            frame = j + 1
            hour = j / 2
            ambient = (29.0 if ai == 0 else 27.5) + (3.7 if ai == 0 else 4.2) * math.sin(2*math.pi*(hour-8)/24) + nz['ambient'][j]
            trip = ai == 1 and 278 <= frame <= 300
            u = interp(frame, KNOTS_A if ai == 0 else KNOTS_B)
            if not trip:
                u += .025 * math.sin(2*math.pi*(hour-4)/24 + ai) + nz['load'][j]
            else:
                u = 0.0
            imbalance = interp(frame, IMB_A if ai == 0 else IMB_B)
            nominal_phase = 433 / math.sqrt(3)
            sag = interp(frame, [(1,0),(400,0),(415,.075),(445,.075),(465,0),(500,0)]) if ai else 0
            vbase = nominal_phase * (1 - .017*max(u-.6,0) - sag + nz['voltage'][j])
            voltages = [vbase*(1 + .0012*math.sin(hour/4+p)) for p in range(3)]
            imultipliers = [1+imbalance, 1-.30*imbalance, 1-.70*imbalance]
            i_mean = u*profile['rated_kva']*1000 / sum(v*mul for v,mul in zip(voltages,imultipliers)) if u else 0
            currents = [i_mean*mul for mul in imultipliers]
            pf_drop = interp(frame, [(1,0),(400,0),(415,.12),(445,.12),(465,0),(500,0)]) if ai else 0
            pf = .94 - pf_drop + .006*math.sin(hour/7+ai) + nz['pf'][j]
            pf = min(.97,max(.79,pf))
            apparent = sum(v*i for v,i in zip(voltages,currents))/1000
            active = apparent*pf
            reactive = apparent*math.sqrt(1-pf*pf)
            neutral = abs(sum(complex(math.cos(p*2*math.pi/3),math.sin(p*2*math.pi/3))*i for p,i in enumerate(currents)))
            rated_current = profile['rated_kva']*1000/(math.sqrt(3)*433)
            heating = sum((i/rated_current)**2 for i in currents)/3
            def equilibrium(par):
                # Breaker is on LV: core remains energized and beta_0 persists during trip.
                return ambient + par['beta_0_c'] + par['beta_1_c']*heating
            top_target, bulk_target = equilibrium(profile['thermal']), equilibrium(profile['bulk_oil'])
            if top is None:
                top, bulk = top_target, bulk_target
            else:
                top += -math.expm1(-.5/profile['thermal']['tau_hours'])*(top_target-top)
                bulk += -math.expm1(-.5/profile['bulk_oil']['tau_hours'])*(bulk_target-bulk)
            observed = {
                **{f'voltage_l{p+1}_n': v for p,v in enumerate(voltages)},
                **{f'current_l{p+1}': i for p,i in enumerate(currents)},
                'neutral_current':neutral, 'active_power_total':active, 'reactive_power_total':reactive,
                'apparent_power_total':apparent, 'frequency':50+.018*math.sin(hour/9+ai),
                'ambient_temperature':ambient, 'top_oil_temperature':top+nz['sensor'][j], 'breaker_trip':trip,
            }
            if apparent > 0:
                observed['power_factor_total'] = pf
            oil_raw, pressure_normal, pressure_total = None, None, None
            if ai == 0:
                if 101 <= frame <= 300:
                    reference_level -= (1.0 if frame < 221 else 1.8)*.5/24
                if 301 <= frame <= 306:
                    reference_level += 1.0
                oil_raw = reference_level + .23*(bulk-40) + nz['oil'][j]
                if not 361 <= frame <= 376:
                    observed['oil_level_percent'] = oil_raw
            else:
                pressure_normal = 4+.35*(bulk-40)
                pulse = {224:4.5,225:9.0,226:4.5}.get(frame,0)
                pressure_total = pressure_normal + interp(frame,PRESSURE_OFFSET) + pulse + nz['pressure'][j]
                if not 365 <= frame <= 376:
                    observed['x_pressure_kpa_g'] = 999.0 if 361 <= frame <= 364 else pressure_total
            observed = {k:(v if isinstance(v,bool) else round(v,6)) for k,v in observed.items()}
            qualities = {k: {'severity':'GOOD','flags':[],'source_code':None} for k in observed}
            if ai == 1 and 361 <= frame <= 364:
                qualities['x_pressure_kpa_g'] = {'severity':'BAD','flags':['OUT_OF_RANGE'],'source_code':'SENSOR_RANGE_ERROR'}
            source_time = stamp(frame)
            source_record_id = f'{asset}:{source_time}'
            raw_row = {'asset_id':asset,'event_time_utc':source_time,'observations':observed,'qualities':qualities}
            raw.append(raw_row)
            source = {'system':'gridpulse_backup_synthetic','adapter_id':'canonical_document_export_v1',
                      'source_record_id':source_record_id,'source_uri':f'raw_frames.jsonl#record={source_record_id}',
                      'raw_sha256':hashlib.sha256(dumps(raw_row).encode()).hexdigest()}
            measurements = []
            for k in sorted(observed):
                unit, phase, _, _ = SIGNALS[k]
                value = observed[k]
                measurements.append({'signal_id':k,'phase':phase,'value':value,
                                     'value_type':'boolean' if isinstance(value,bool) else 'float',
                                     'unit_ucum':unit,'original_name':k,'original_value':dumps(value),
                                     'original_unit':unit,'quality':qualities[k]})
            events.append({'schema_version':'1.0.0','event_id':str(uuid.uuid5(NS,f'{DATASET}:{source_record_id}')),
                           'asset_id':asset,'event_time_utc':source_time,
                           'received_time_utc':iso(START+timedelta(minutes=30*j,seconds=2)),
                           'source':source,'measurements':measurements,'event_quality_flags':[],
                           'mapping_version':'gridpulse-backup-canonical-map-1.0.0'})
            truth.append({'asset_id':asset,'frame_1based':frame,'event_time_utc':source_time,
                          'load_pu_truth':round(apparent/profile['rated_kva'],8),
                          'current_magnitude_imbalance_pct_truth':round(imbalance*100,8),
                          'top_oil_state_c_truth':round(top,8),'bulk_oil_c_truth':round(bulk,8),
                          'oil_level_at_40c_pct_truth':round(reference_level,8) if ai == 0 else '',
                          'oil_level_raw_no_missing_pct_truth':round(oil_raw,8) if ai == 0 else '',
                          'pressure_baseline_kpa_g_truth':round(pressure_normal,8) if ai else '',
                          'pressure_physical_kpa_g_truth':round(pressure_total,8) if ai else ''})
    # Stable cross-asset interleaving; each asset remains strictly chronological.
    events.sort(key=lambda e:(e['event_time_utc'], e['asset_id']))
    raw.sort(key=lambda e:(e['event_time_utc'], e['asset_id']))
    truth.sort(key=lambda e:(e['event_time_utc'], e['asset_id']))
    return events, raw, truth

def ledger():
    rows=[]
    for ai, sid, category, first, last, affected, description, intervention in EVENTS:
        rows.append({'asset_id':ASSETS[ai],'event_id':str(uuid.uuid5(NS, DATASET+':'+sid)),
                     'scenario_id':sid,'synthetic':True,'category':category,
                     'start_frame_1based':first,'end_frame_1based_inclusive':last,
                     'start_timestamp_utc':stamp(first),'end_timestamp_utc_inclusive':stamp(last),
                     'end_timestamp_utc_exclusive':iso(START+timedelta(minutes=30*last)),
                     'affected_signals':dumps(affected),'description':description,
                     'synthetic_intervention_assumption':intervention,
                     'expected_observable_evidence':description,
                     'runtime_outcome_status':'NOT-RUNTIME-VERIFIED'})
    return rows

def coverage_rows():
    return [
      ('Integrity/replay','Both','Canonical identity, timestamps, units, quality, provenance','DOCUMENT-VERIFIED / FILE-VALIDATED','Runtime replay and schema acceptance NOT-RUNTIME-VERIFIED'),
      ('Loading/electrical','Both','Phase V/I, P/Q/S, PF and declared synthetic rating','DOCUMENT-VERIFIED / FILE-VALIDATED','Configured thresholds and asset-profile registration required'),
      ('Thermal trends/exposure','Both','Ambient and lagged top-oil observations','DOCUMENT-VERIFIED / FILE-VALIDATED','Direct limit/exposure bands depend on actual asset settings'),
      ('Oil trend / suspected loss','A','Raw oil level, reference metadata, temperature-aware bulk-oil generation','INFERRED / FILE-VALIDATED','Exact correction, bulk estimator and multi-day warm-up BLOCKED-MISSING-SOURCE'),
      ('Phase/neutral','A late; B early','Three phase-current magnitudes and fundamental neutral RMS','DOCUMENT-VERIFIED / FILE-VALIDATED','MNT-PHASE-004 is documented; firing/timing NOT-RUNTIME-VERIFIED'),
      ('Pressure transient/sustained','B','x_pressure_kpa_g; declared sealed construction and range','DOCUMENT-VERIFIED extension / FILE-VALIDATED','Active pressure alias, baseline and thresholds BLOCKED-MISSING-SOURCE'),
      ('Direct protective trip','B','Boolean breaker_trip; zero downstream currents and power','DOCUMENT-VERIFIED / FILE-VALIDATED','MNT-PROT-001 is documented; application latch remains until actual authorized resolution'),
      ('Missing/BAD observability','Both','A missing oil; B BAD then missing pressure; unrelated signals preserved','DOCUMENT-VERIFIED / FILE-VALIDATED','Staleness display and suppression NOT-RUNTIME-VERIFIED'),
      ('OTHI/episodes/advisories','Both','Distinct condition inputs, recovery, recurrence, protection','INFERRED','No score/state/advisory is supplied; runtime policy decides all results'),
      ('Forecast/what-if/residual/CUSUM','Neither newly qualified','Thermal inputs available; no applicable promoted artifact','NOT-RUNTIME-VERIFIED','Disabled unless separately qualified; no borrowed parameters or TEST tuning'),
      ('RUL/insulation ageing/DGA','Neither','No hotspot, insulation class, DGA or degradation history','DOCUMENT-VERIFIED exclusion','Unavailable; generator latent states do not establish capability'),
      ('Pressure-relief contact / short-circuit','Neither','Exact current contact schema/verified impedance unavailable','BLOCKED-MISSING-SOURCE','Omitted instead of inventing aliases or waveform evidence'),
    ]

def write_docs(out, events, truth, provenance):
    (out/'README.md').write_text('''# GridPulse backup story dataset v1.0.0

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
''')
    sources = '\n'.join(f"- `{r['filename']}` — SHA-256 `{r['sha256']}`" for r in provenance['documents'])
    (out/'schema_and_integration_notes.md').write_text('''# Contract and later integration

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

'''+sources+'\n\nPrimary public references (scope/design grounding, not numerical parameter validation):\n- IEC 60076-7:2018 public scope: https://webstore.iec.ch/en/publication/34351\n- Hitachi Energy distribution transformer construction: https://www.hitachienergy.com/in/en/products-and-solutions/transformers/distribution-transformers/liquid-filled-distribution-transformers/medium-distribution-transformers-316-2-499-kva\n- Hitachi Energy breather/thermal contraction context: https://www.hitachienergy.com/products-and-solutions/insulation-and-components/transformer-insulation-components/measurement-and-safety-devices/dehydrating-breathers/conventional\n\nThese primary sources support general loading/temperature and construction context only. The gauge/pressure coefficients and schedules below are declared simulation assumptions; no IEC/IEEE compliance or field calibration is asserted.\n')
    rows = coverage_rows()
    (out/'capability_coverage_matrix.md').write_text('# Capability coverage before generation\n\nThis design matrix describes inputs and gates, not executed detector outcomes.\n\n| Capability | Asset | Required signals/metadata | Support | Gate/limitation |\n|---|---|---|---|---|\n'+'\n'.join('| '+' | '.join(row)+' |' for row in rows)+'\n')
    phases = ['Healthy baseline','Early warning','Developing incident','Partial recovery','Recurrence or secondary stress',
              'Sustained abnormal operation','Intervention and improvement','Data-quality challenge','New operating stress','Final stabilization']
    timeline = '# Scenario timeline\n\nAll indices are one-based inclusive. Evidence responses are hypotheses until actual runtime testing. No intended health scores or episode states are encoded.\n'
    for ai, asset in enumerate(ASSETS):
        timeline += f'\n## {asset}\n\n| Frames | UTC endpoints | Narrative | Signals/mechanism |\n|---|---|---|---|\n'
        mechanisms = (['Normal daily load and thermal/gauge expansion.','Smooth load increase; no point impulse.',
                       'Sustained loading plus synthetic oil inventory decline.','Load falls and oil temperature cools with inertia; inventory loss continues.',
                       'Recurring load growth; oil inventory loss increases from 221.','Elevated loading persists; oil inventory keeps declining.',
                       'Load redistribution plus six-point top-up at 301–306; simulated leak source removed.',
                       'Mostly stable physics; oil observations absent 361–376 only.',
                       'Phase demand imbalance grows and produces neutral current.','Phase rebalancing by 465; stable load/oil thereafter.'] if ai == 0 else
                      ['Different daily load and thermal profile; sealed pressure baseline.',
                       'Growing phase imbalance and small pressure offset.','Sustained unequal phase demand plus pressure offset.',
                       'Load/phase and pressure gradually return toward baseline.',
                       'Milder loading plus a brief pressure pulse at 224–226.',
                       'Pressure offset grows; separate trip at 278 removes downstream power/current.',
                       'Physical contact reset at 301 and gradual re-energization; backend latch not auto-resolved.',
                       'Pressure BAD/OUT_OF_RANGE 361–364, absent 365–376; unrelated channels current.',
                       'Balanced supply sag and lower PF create a different electrical story.',
                       'Supply/PF restored by 465; stable physical state, possible unresolved backend trip.'])
        for q, (phase, mechanism) in enumerate(zip(phases,mechanisms)):
            first,last=50*q+1,50*(q+1)
            timeline += f'| {first}–{last} | {stamp(first)} → {stamp(last)} | {phase} | {mechanism} |\n'
    timeline += '\n## Precise event windows and intervention assumptions\n\n'
    for r in ledger():
        timeline += f"- **{r['scenario_id']}** ({r['category']}): frames {r['start_frame_1based']}–{r['end_frame_1based_inclusive']}, {r['start_timestamp_utc']} through {r['end_timestamp_utc_inclusive']}. {r['description']} {r['synthetic_intervention_assumption']}\n"
    timeline += '\nFinal physical conditions have stabilized, but runtime incident closure is unverified. A has no ongoing generator oil loss and a restored gauge reference; B has no active contact indication and re-energized load. The backend trip may remain latched. End of a scenario window is not an instruction to close an episode.\n'
    (out/'scenario_timeline.md').write_text(timeline)
    ranges = {k:[] for k in SIGNALS}
    for e in events:
        for m in e['measurements']:
            if m['quality']['severity'] == 'GOOD' and not isinstance(m['value'],bool):
                ranges[m['signal_id']].append(m['value'])
    dictionary = '# Signal dictionary\n\nAll listed signals are **simulated sensor-equivalent observations**, not field measurements. Generator calculations create coherent observations; runtime must still label derived features separately. Every scalar is tied to immutable raw observation bytes. Pressure is the documented current extension with unverified runtime alias; no static nameplate fields are streamed.\n\n| Field/signal_id | Meaning | Unit | Phase | Applicability | Delivered GOOD range | Generation |\n|---|---|---|---|---|---|---|\n'
    for k,(unit,phase,meaning,applicability) in SIGNALS.items():
        rr = f'{min(ranges[k]):.4f} to {max(ranges[k]):.4f}' if ranges[k] else 'false/true'
        if k.startswith('voltage'): method='Nominal 433/√3 with smooth load drop, small correlated variation; B late balanced sag'
        elif k.startswith('current'): method='Coherent phase load allocation; exact zero during LV trip'
        elif k=='neutral_current': method='Fundamental phasor sum of unequal currents; no harmonic neutral components'
        elif 'power' in k: method='S=sum(Vphase Iphase)/1000; P=S PF; Q=S sqrt(1−PF²); common sinusoidal phase angle'
        elif k=='frequency': method='50 Hz plus small smooth upstream variation'
        elif k=='ambient_temperature': method='Diurnal sinusoid with correlated meteorological variation'
        elif k=='top_oil_temperature': method='First-order state, current-squared heating, correlated 0.045°C sensor noise'
        elif k=='oil_level_percent': method='Reference inventory +0.23 percentage points/°C ×(bulk−40°C), small correlated noise'
        elif k=='x_pressure_kpa_g': method='4+0.35×(bulk−40) kPa plus smooth offsets and pulse; four BAD +999 kPa values excluded from range'
        else: method='Discrete physical protective-trip indication; true at B frames 278–300 only'
        dictionary += f'| {k} | {meaning} | {unit} | {phase or "asset"} | {applicability} | {rr} | {method} |\n'
    dictionary += '\nGOOD denotes declared usable synthetic observations. BAD/OUT_OF_RANGE is limited to B pressure frames 361–364. Missing signals are absent, with no fictitious source timestamp/value; age-based STALE is to be computed by the application using the last observation. A oil is absent 361–376; B pressure absent 365–376. PF is absent throughout B trip because 0/0 is undefined. B has no oil gauge; A has no pressure sensor. No unrelated signal is invalidated. No UNCERTAIN or frame-level partition-quality flag is manufactured.\n\nCSV nested-cell interpretation, transport timestamp and Boolean type-tag assumptions are described in schema_and_integration_notes.md. raw_sha256 hashes canonical compact sorted JSON bytes for the corresponding raw record, excluding the trailing newline.\n'
    (out/'signal_dictionary.md').write_text(dictionary)
    (out/'DEMO_SCRIPT.md').write_text('''# Backup replay guide

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
''')

def make_plots(out, events, truth):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    for ai,asset in enumerate(ASSETS):
        ee=[e for e in events if e['asset_id']==asset]
        tt=[t for t in truth if t['asset_id']==asset]
        frames=np.arange(1,501)
        def vals(k):
            result=[]
            for e in ee:
                mm=next((m for m in e['measurements'] if m['signal_id']==k),None)
                result.append(mm['value'] if mm and mm['quality']['severity']=='GOOD' else np.nan)
            return result
        fig,axs=plt.subplots(5,1,figsize=(13,12),sharex=True,layout='constrained')
        fig.suptitle(f'{asset} | Synthetic backup observations | 30-minute cadence',fontsize=15)
        axs[0].plot(frames,[t['load_pu_truth'] for t in tt],label='S / declared synthetic kVA',color='#2563eb')
        axs[0].set_ylabel('Load ratio');axs[0].axhline(1,color='#8b8b8b',ls=':',label='Declared rating reference')
        for p,c in zip(range(1,4),['#2563eb','#d97706','#059669']):
            axs[1].plot(frames,vals(f'current_l{p}'),label=f'I L{p}',color=c,linewidth=1.2)
        axs[1].plot(frames,vals('neutral_current'),label='Neutral',color='#dc2626',lw=1)
        axs[1].set_ylabel('Current (A)')
        axs[2].plot(frames,vals('ambient_temperature'),label='Ambient',color='#059669')
        axs[2].plot(frames,vals('top_oil_temperature'),label='Top oil',color='#dc2626')
        axs[2].set_ylabel('Temperature (°C)')
        if ai == 0:
            axs[3].plot(frames,vals('oil_level_percent'),label='Raw gauge (missing interval omitted)',color='#2563eb')
            axs[3].plot(frames,[t['oil_level_at_40c_pct_truth'] for t in tt],label='Reference inventory (OFFLINE TRUTH)',color='#d97706',ls='--')
            axs[3].set_ylabel('Gauge scale (%)')
            for f in (301,306):axs[3].axvline(f,color='#059669',ls=':')
        else:
            axs[3].plot(frames,vals('x_pressure_kpa_g'),label='GOOD gauge pressure',color='#2563eb')
            axs[3].plot(frames,[t['pressure_baseline_kpa_g_truth'] for t in tt],label='Baseline (OFFLINE TRUTH)',color='#d97706',ls='--')
            axs[3].set_ylabel('Gauge pressure (kPa)')
            axs[3].axvspan(278,300,color='#dc2626',alpha=.14,label='Discrete LV trip, no load')
            axs[3].axvspan(361,376,color='#6b7280',alpha=.14,label='BAD / missing pressure')
        for p,c in zip(range(1,4),['#2563eb','#d97706','#059669']):
            axs[4].plot(frames,vals(f'voltage_l{p}_n'),label=f'V L{p}-N',color=c,lw=1)
        axs[4].set_ylabel('Voltage (V)');axs[4].set_xlabel('One-based asset frame (50 observations = 25-hour scheduling block)')
        for ax in axs:
            for boundary in range(51,500,50):ax.axvline(boundary,color='#9ca3af',alpha=.25,lw=.8)
            ax.grid(alpha=.17);ax.legend(loc='upper right',fontsize=8,ncol=3);ax.set_xlim(1,500)
        fig.savefig(out/'plots'/f'{"A" if ai==0 else "B"}_story.png',dpi=140,metadata={'Software':'GridPulse backup generator 1.0.0'})
        plt.close(fig)

def build(out, source_dir=None):
    src_root=Path(__file__).resolve().parent.parent
    if (out/'dataset_manifest.json').exists():
        raise SystemExit('Refusing an existing dataset bundle. Choose a fresh output directory.')
    out.mkdir(parents=True,exist_ok=True)
    (out/'scripts').mkdir(exist_ok=True);(out/'plots').mkdir(exist_ok=True)
    for script in src_root.joinpath('scripts').glob('*.py'):
        if script.resolve() != out.joinpath('scripts',script.name).resolve():
            shutil.copyfile(script,out/'scripts'/script.name)
    if source_dir:
        docs=[{'filename':p.name,'sha256':sha(p),'size_bytes':p.stat().st_size}
              for p in sorted(Path(source_dir).iterdir()) if p.is_file()]
        provenance={'documents':docs,'register_role':'Source identities only; no source files redistributed'}
    else:
        provenance=json.loads((src_root/'source_document_register.json').read_text())
    write_json(out/'source_document_register.json',provenance)
    events,raw,truth=generate_frames()
    for name,objects in [('canonical_events.jsonl',events),('raw_frames.jsonl',raw)]:
        (out/name).write_text(''.join(dumps(o)+'\n' for o in objects))
    csv_events=[];flat=[]
    for e in events:
        csv_events.append({k:dumps(e[k]) if k in ['source','measurements','event_quality_flags'] else e[k] for k in ENVELOPE})
        row={k:e[k] for k in ['asset_id','event_id','event_time_utc']}
        measurements={m['signal_id']:m for m in e['measurements']}
        for k in SIGNALS:
            mm=measurements.get(k)
            row[k]=dumps(mm['value']) if mm else ''
            row[k+'__quality']=mm['quality']['severity'] if mm else 'ABSENT'
        flat.append(row)
    write_csv(out/'telemetry.csv',csv_events,ENVELOPE)
    write_csv(out/'telemetry_flat_view.csv',flat,list(flat[0]))
    write_csv(out/'latent_truth.csv',truth,list(truth[0]))
    labels=ledger();write_csv(out/'fault_events.csv',labels,list(labels[0]))
    assets=[]
    for ai,a in enumerate(ASSETS):
        p=PROFILES[a]
        available=[k for k in SIGNALS if not (ai==0 and k=='x_pressure_kpa_g') and not (ai==1 and k=='oil_level_percent')]
        assets.append({'asset_id':a,'profile_version':'backup-assumed-1.0.0','synthetic':True,
                       'provenance':'DECLARED_SYNTHETIC_DESIGN_NOT_MANUFACTURER_VERIFIED',
                       'electrical_side':'LV','rated_kva':p['rated_kva'],'rated_hv_line_line_v':11000,
                       'rated_lv_line_line_v':433,'rated_lv_phase_neutral_v':433/math.sqrt(3),
                       'rated_lv_current_a':p['rated_kva']*1000/(math.sqrt(3)*433),
                       'frequency_hz':50,'cooling_class':'ONAN','tank_construction':p['tank_construction'],
                       'oil_gauge_type':p['oil_gauge_type'],'sensor_inventory':available,
                       'pressure_sensor_fitted':ai==1,'oil_level_sensor_fitted':ai==0,
                       'insulation_profile':'UNKNOWN','hotspot_sensor_fitted':False,
                       'operating_thresholds':None,'impedance_percent':None,
                       'generator_assumptions':p,
                       'runtime_model_artifact':None,'qualification_status':'NOT_QUALIFIED_FOR_NEW_BACKUP_ASSET',
                       'signal_temporal_support':'SYNCHRONIZED_SNAPSHOT_OF_QUASI_STEADY_RMS_STATE',
                       'voltage_meter_location':'LV_BUS_UPSTREAM_OF_LV_BREAKER',
                       'current_power_meter_location':'LV_LOAD_DOWNSTREAM_OF_LV_BREAKER'})
    write_json(out/'asset_metadata.json',{'metadata_schema':'PROPOSED_BACKUP_METADATA_1.0.0',
               'not_actual_assetprofile_schema':True,'assets':assets,
               'electrical_assumptions':{'voltage_phase_angles_deg':[0,-120,120],'common_lagging_pf':True,
                                       'harmonics':'Negligible by simulation assumption','power_sign':'Import positive; inductive Q positive'},
               'assumptions':['All ratings/designs/sensor ranges are declared synthetic equipment assumptions.',
                              'Thermal coefficients are generator constants, not calibrated application parameters.',
                              'Bulk oil is an offline latent state, not equated with top oil.',
                              'Gauge sensitivity is 0.23 gauge percentage points/C, not a universal oil expansion coefficient.',
                              'Pressure uses a simplified linear compliant-tank reference plus scenario offsets; not a universal gas law.',
                              'No actual manufacturer limits, trip thresholds, fluid data or verified impedance were provided.']})
    write_docs(out,events,truth,provenance)
    make_plots(out,events,truth)
    (out/'requirements.txt').write_text('matplotlib==3.10.8\n')
    inventory=[]
    for p in sorted(out.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            inventory.append({'path':p.relative_to(out).as_posix(),'sha256':sha(p),'size_bytes':p.stat().st_size})
    write_json(out/'dataset_manifest.json',{
      'manifest_schema':'PROPOSED_BACKUP_MANIFEST_1.0.0','dataset_id':DATASET,'dataset_version':VERSION,
      'synthetic':True,'purpose':'Isolated backup demo and integration test','registration_status':'UNREGISTERED',
      'partition_assignment':'DEMO_ONLY_NO_FIT_CAL_TEST','generator_version':VERSION,'random_seed':SEED,
      'generator_runtime':{'python':platform.python_version(),'matplotlib':'3.10.8'},
      'sampling_interval_seconds':1800,'start_timestamp_utc':stamp(1),'end_timestamp_utc':stamp(500),
      'elapsed_hours_per_asset':249.5,'frame_count':1000,'per_asset_counts':{a:500 for a in ASSETS},
      'asset_ids':ASSETS,'measurement_count':sum(len(e['measurements']) for e in events),
      'primary_telemetry':'canonical_events.jsonl','frame_csv':'telemetry.csv','raw_observations':'raw_frames.jsonl',
      'ground_truth_file':'fault_events.csv','truth_only_files':['fault_events.csv','latent_truth.csv'],
      'file_inventory':inventory,'hash_scope':'Every bundle file except this manifest; no self-referential hash',
      'signal_availability':{p['asset_id']:p['sensor_inventory'] for p in assets},
      'compatibility':{'canonical_envelope':'DOCUMENT-VERIFIED','internal_files':'FILE-VALIDATED after validate.py',
                       'actual_adapter_runtime':'NOT-RUNTIME-VERIFIED','metadata_fault_csv_manifest_layouts':'Proposed; BLOCKED-MISSING-SOURCE'},
      'limitations':['No source/runtime or original synthetic schema supplied; no adapter/UI/detector verification.',
                     'No exact OTHI, severity, advisory, closure or detection-delay claims.',
                     'New assets have no promoted model; no CUSUM/forecast/RUL/ageing qualification.',
                     'Existing datasets/configuration/model artifacts were not accessed or changed.']})
    return {'frames':len(events),'measurements':sum(len(e['measurements']) for e in events),'events':len(labels),'output':str(out)}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-dir',type=Path)
    args=parser.parse_args()
    print(json.dumps(build(args.output.resolve(),args.source_dir),indent=2))
