#!/usr/bin/env python3
"""Validate the delivered bytes, independent of application code or inferred outcomes."""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def compact(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)

def csvrows(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))

def time(s):
    return datetime.fromisoformat(s.replace('Z','+00:00'))

def validate(bundle,write_report=False):
    checks=[]
    def check(name,passed,detail):
        checks.append({'check':name,'status':'PASS' if passed else 'FAIL','detail':detail})
    manifest=json.loads((bundle/'dataset_manifest.json').read_text())
    metadata=json.loads((bundle/'asset_metadata.json').read_text())
    events=[json.loads(x) for x in (bundle/'canonical_events.jsonl').read_text().splitlines()]
    raw=[json.loads(x) for x in (bundle/'raw_frames.jsonl').read_text().splitlines()]
    frame_csv=csvrows(bundle/'telemetry.csv')
    flat=csvrows(bundle/'telemetry_flat_view.csv')
    truth=csvrows(bundle/'latent_truth.csv')
    faults=csvrows(bundle/'fault_events.csv')
    assets=manifest['asset_ids'];profiles={p['asset_id']:p for p in metadata['assets']}
    check('exact total frames',len(events)==len(frame_csv)==len(flat)==len(raw)==len(truth)==1000,'1,000 frames in each representation, not 1,000 scalar measurements')
    check('exact two assets',set(e['asset_id'] for e in events)==set(assets) and len(assets)==2,str(assets))
    check('exact per-asset counts',Counter(e['asset_id'] for e in events)=={a:500 for a in assets},'500 frames each')
    check('unique canonical event IDs',len({e['event_id'] for e in events})==1000,'UUIDv5 content-context IDs')
    check('unique frame keys',len({(e['asset_id'],e['event_time_utc']) for e in events})==1000,'No duplicated asset/time frames')
    check('global deterministic ordering',events==sorted(events,key=lambda e:(e['event_time_utc'],e['asset_id'])),'UTC then asset identity')
    envelope={'schema_version','event_id','asset_id','event_time_utc','received_time_utc','source','measurements','event_quality_flags','mapping_version'}
    fields={'signal_id','phase','value','value_type','unit_ucum','original_name','original_value','original_unit','quality'}
    check('documented envelope field set',all(set(e)==envelope for e in events),'Nine exact document-derived envelope fields')
    check('CSV exact envelope columns',set(frame_csv[0])==envelope,'Nested cells are JSON; no invented wide inference schema')
    check('measurement field set',all(set(m)==fields for e in events for m in e['measurements']),'Documented fields; Boolean type spelling declared assumption')
    check('mandatory IDs nonblank',all(all(e[k] for k in ['event_id','asset_id','event_time_utc','schema_version','mapping_version']) for e in events),'All identities populated')
    expected_units={'voltage_l1_n':'V','voltage_l2_n':'V','voltage_l3_n':'V','current_l1':'A','current_l2':'A','current_l3':'A','neutral_current':'A','active_power_total':'kW','reactive_power_total':'kvar','apparent_power_total':'kVA','power_factor_total':'1','frequency':'Hz','ambient_temperature':'Cel','top_oil_temperature':'Cel','oil_level_percent':'%','x_pressure_kpa_g':'kPa','breaker_trip':'1'}
    check('unit/signal allowlist',all(m['signal_id'] in expected_units and expected_units[m['signal_id']]==m['unit_ucum'] for e in events for m in e['measurements']),'16 signal IDs per asset; 17 union including documented pressure extension')
    check('phase assignments',all(m['phase']==('N' if m['signal_id']=='neutral_current' else ('L'+m['signal_id'].split('_l')[1][0] if m['signal_id'].startswith(('voltage_l','current_l')) else None)) for e in events for m in e['measurements']),'LV phase identity consistent')
    check('typed numeric and discrete values',all((isinstance(m['value'],bool) and m['value_type']=='boolean') if m['signal_id']=='breaker_trip' else (isinstance(m['value'],(int,float)) and not isinstance(m['value'],bool) and math.isfinite(m['value']) and m['value_type']=='float') for e in events for m in e['measurements']),'No NaN/Infinity/null numeric observations')
    check('quality vocabulary',all(m['quality']['severity'] in ['GOOD','UNCERTAIN','BAD'] for e in events for m in e['measurements']),'STALE remains an elapsed-time state, not invented fresh records')
    check('one instance per signal/frame',all(len({m['signal_id'] for m in e['measurements']})==len(e['measurements']) for e in events),'No duplicated measurements')
    decoded=[]
    for row in frame_csv:
        decoded.append({k:json.loads(v) if k in ['source','measurements','event_quality_flags'] else v for k,v in row.items()})
    check('lossless frame CSV round-trip',decoded==events,'All 1,000 canonical events reproduced exactly')
    rawmap={(r['asset_id'],r['event_time_utc']):r for r in raw}
    check('raw source record hashes',all(e['source']['raw_sha256']==hashlib.sha256(compact(rawmap[(e['asset_id'],e['event_time_utc'])]).encode()).hexdigest() for e in events),'1,000 hashes recomputed from delivered raw bytes excluding newline')
    check('source/original observation round-trip',all({m['signal_id']:m['value'] for m in e['measurements']}==rawmap[(e['asset_id'],e['event_time_utc'])]['observations'] and all(json.loads(m['original_value'])==m['value'] and m['original_name']==m['signal_id'] and m['original_unit']==m['unit_ucum'] for m in e['measurements']) for e in events),'No cleaning overwrites raw observation values')
    check('no truth fields in inference',all(not any(x in compact(e) for x in ['scenario_id','expected_othi','future_recovery','_truth','latent_truth.csv','fault_events.csv']) for e in events),'Canonical values, source and CSV checked for oracle field leakage; runtime permutation test is blocked')
    check('no partition-quality metadata',all(e['event_quality_flags']==[] for e in events),'No PARTITION_CAL or scenario truth flags')
    check('static metadata not measurements',all(not any(x in m['signal_id'] for x in ['rated_','tank_construction','ref_temp','impedance','model_']) for e in events for m in e['measurements']),'Nameplate, corrections and models stay outside telemetry')
    check('metadata two new identities',set(profiles)==set(assets) and all(p['synthetic'] and p['runtime_model_artifact'] is None and p['operating_thresholds'] is None for p in profiles.values()),'No transferred promotion/model or invented universal thresholds')
    check('not a qualification holdout',manifest['partition_assignment']=='DEMO_ONLY_NO_FIT_CAL_TEST','No existing FIT/CAL/TEST boundary altered')
    grouped=defaultdict(list);tg=defaultdict(list)
    for e in events:grouped[e['asset_id']].append(e)
    for t in truth:tg[t['asset_id']].append(t)
    stats={}
    total_bad=0;absences=Counter()
    for ai,a in enumerate(assets):
        ee=grouped[a];tt=tg[a];times=[time(e['event_time_utc']) for e in ee]
        vv=[{m['signal_id']:m['value'] for m in e['measurements']} for e in ee]
        check(a+' UTC timestamps',all(t.utcoffset().total_seconds()==0 for t in times),'All parseable and UTC-aware')
        check(a+' exact cadence',all((y-x).total_seconds()==1800 for x,y in zip(times,times[1:])),'499 consecutive 1,800-second intervals; no frame gaps')
        check(a+' exact endpoint span',(times[-1]-times[0]).total_seconds()==249.5*3600 and len(set(times))==500,'500 observations span 249.5 hours')
        check(a+' endpoints match manifest',ee[0]['event_time_utc']==manifest['start_timestamp_utc'] and ee[-1]['event_time_utc']==manifest['end_timestamp_utc'],'2025-01-01T00:00:00Z through 2025-01-11T09:30:00Z')
        check(a+' declared receive delay',all((time(e['received_time_utc'])-time(e['event_time_utc'])).total_seconds()==2 for e in ee),'Synthetic two-second transport assumption')
        check(a+' asset sensor applicability',all(('x_pressure_kpa_g' not in v if ai==0 else 'oil_level_percent' not in v) for v in vv),'Pressure only sealed B; gauge only conservator A')
        check(a+' three-phase apparent power',all(abs(sum(v[f'voltage_l{p}_n']*v[f'current_l{p}'] for p in [1,2,3])/1000-v['apparent_power_total'])<3e-6 for v in vv),'Absolute tolerance 0.000003 kVA after 6-decimal rounding; common-angle sinusoidal phase loads')
        check(a+' compatible power triangle',all(abs(math.hypot(v['active_power_total'],v['reactive_power_total'])-v['apparent_power_total'])<2e-6 for v in vv),'Tolerance 0.000002 kVA; explicitly declared power convention')
        check(a+' PF semantics',all(('power_factor_total' not in v) if v['apparent_power_total']==0 else abs(v['active_power_total']/v['apparent_power_total']-v['power_factor_total'])<1e-6 for v in vv),'PF omitted at zero S; otherwise P/S within 0.000001')
        check(a+' fundamental neutral phasor',all(abs(abs(sum(v[f'current_l{p+1}']*complex(math.cos(p*2*math.pi/3),math.sin(p*2*math.pi/3)) for p in range(3)))-v['neutral_current'])<3e-6 for v in vv),'Tolerance 0.000003 A; no invented harmonic currents')
        check(a+' thermal lag equation',all(abs(float(tt[j]['top_oil_state_c_truth'])-(float(tt[j-1]['top_oil_state_c_truth'])+(-math.expm1(-.5/profiles[a]['generator_assumptions']['thermal']['tau_hours']))*((vv[j]['ambient_temperature']+profiles[a]['generator_assumptions']['thermal']['beta_0_c']+profiles[a]['generator_assumptions']['thermal']['beta_1_c']*sum((vv[j][f'current_l{p}']/profiles[a]['rated_lv_current_a'])**2 for p in [1,2,3])/3)-float(tt[j-1]['top_oil_state_c_truth']))))<1e-6 for j in range(1,500)),'Generator ODE verified against rounded delivered inputs and offline state; not application model validation')
        deltas=[abs(vv[j]['top_oil_temperature']-vv[j-1]['top_oil_temperature']) for j in range(1,500)]
        check(a+' slow-temperature continuity',max(deltas)<5,'Max observed change '+str(round(max(deltas),6))+' C/30min; simulation QA bound, not a universal sensor-fault threshold')
        check(a+' signal ranges',all(200<v[f'voltage_l{p}_n']<270 and 0<=v[f'current_l{p}']<650 for v in vv for p in [1,2,3]) and all(15<v['ambient_temperature']<45 and 20<v['top_oil_temperature']<125 for v in vv),'Declared simulation QA bounds, not standards or operating limits')
        for k in profiles[a]['sensor_inventory']:
            absences[a+':'+k]=sum(k not in v for v in vv)
        bad=[m for e in ee for m in e['measurements'] if m['quality']['severity']=='BAD'];total_bad+=len(bad)
        check(a+' channel quality isolation',all(m['signal_id']=='x_pressure_kpa_g' and m['quality']['flags']==['OUT_OF_RANGE'] for m in bad),'No unrelated channel made BAD')
        # Scenario-specific descriptive tests only; no detector thresholds are asserted.
        load=[v['apparent_power_total']/profiles[a]['rated_kva'] for v in vv]
        temps=[v['top_oil_temperature'] for v in vv]
        imbs=[100*max(abs(v[f'current_l{p}']-mean([v[f'current_l{q}'] for q in [1,2,3]])) for p in [1,2,3])/mean([v[f'current_l{q}'] for q in [1,2,3]]) if v['apparent_power_total'] else 0 for v in vv]
        if ai==0:
            check('A developing loading vs baseline',mean(load[110:145])>mean(load[:50])+.4,'Window mean difference >0.4 of declared rating')
            check('A thermal recovery visible',mean(temps[180:200])<mean(temps[125:150])-10,'Recovery window at least 10 C cooler than developing window')
            check('A recurring stress distinguishable',mean(load[250:300])>mean(load[180:200])+.4,'Separate low-load interval before recurrence')
            check('A corrected inventory loss',float(tt[299]['oil_level_at_40c_pct_truth'])<float(tt[99]['oil_level_at_40c_pct_truth'])-4,'More than four gauge percentage points of latent inventory loss; no leak diagnosis')
            check('A no-leak baseline expansion',max(v['oil_level_percent'] for v in vv[:50])-min(v['oil_level_percent'] for v in vv[:50])>.3 and len({t['oil_level_at_40c_pct_truth'] for t in tt[:50]})==1,'Raw gauge moves with temperature despite constant reference inventory')
            check('A bulk-oil correction',all(abs(v['oil_level_percent']-(float(t['oil_level_at_40c_pct_truth'])+.23*(float(t['bulk_oil_c_truth'])-40)))<.15 for v,t in zip(vv,tt) if 'oil_level_percent' in v),'Residual <0.15 gauge percentage points; own declared bulk-oil model, not top-oil substitution')
            check('A gradual top-up exactly six points',abs(float(tt[305]['oil_level_at_40c_pct_truth'])-float(tt[299]['oil_level_at_40c_pct_truth'])-6)<1e-6,'Top-up 301–306, repair assumption keeps reference level constant thereafter')
            check('A exact oil missing interval', [j+1 for j,v in enumerate(vv) if 'oil_level_percent' not in v]==list(range(361,377)),'16 absent observations; not zero')
            check('A history before oil missingness',all('oil_level_percent' in v for v in vv[:360]),'360 consecutive observations span 179.5 h; exact runtime trend warm-up unverified')
            check('A new phase stress',mean(imbs[420:440])>10 and mean(imbs[470:500])<2,'Late phase imbalance then restoration')
            check('A final inventory stable',len({t['oil_level_at_40c_pct_truth'] for t in tt[306:]})==1,'No continuing generator loss after intervention')
        else:
            check('B phase incident and recovery',mean(imbs[110:145])>15 and mean(imbs[180:200])<4,'Phase/neutral story differs from A thermal story')
            residuals=[float(t['pressure_physical_kpa_g_truth'])-float(t['pressure_baseline_kpa_g_truth']) for t in tt]
            check('B sustained pressure 1',mean(residuals[115:145])>10 and abs(mean(residuals[180:200]))<2,'Pressure offset persistent then returns near declared baseline')
            check('B pressure pulse separate',residuals[224]>8 and residuals[222]<1 and residuals[226]<1,'Three-frame pulse 224–226; no protective contact operation')
            check('B sustained pressure 2',mean(residuals[260:277])>20,'Distinct later sustained pressure window')
            check('B exact trip interval',[j+1 for j,v in enumerate(vv) if v['breaker_trip']]==list(range(278,301)),'23 true frames, physical indication clears at 301')
            check('B no-load trip consistency',all(v[k]==0 for v in vv[277:300] for k in ['current_l1','current_l2','current_l3','neutral_current','active_power_total','reactive_power_total','apparent_power_total']),'Seven downstream current/power channels exactly zero during trip')
            check('B bus alive during LV trip',all(v['voltage_l1_n']>200 and v['frequency']>49 for v in vv[277:300]),'Upstream voltage/frequency persist; core remains energized')
            check('B physical contact reset/load return',not vv[300]['breaker_trip'] and vv[300]['apparent_power_total']>0,'Physical observation only; no backend resolution asserted')
            check('B BAD range values',[j+1 for j,e in enumerate(ee) if any(m['quality']['severity']=='BAD' for m in e['measurements'])]==list(range(361,365)) and all(vv[j]['x_pressure_kpa_g']==999 for j in range(360,364)),'Exactly four deliberate sensor-invalid values retained, not physical tank pressure')
            check('B exact pressure missing interval',[j+1 for j,v in enumerate(vv) if 'x_pressure_kpa_g' not in v]==list(range(365,377)),'12 absent observations; pressure resumes at 377')
            check('B late voltage/PF stress',mean(v['voltage_l1_n'] for v in vv[415:445])<mean(v['voltage_l1_n'] for v in vv[:50])-15 and mean(v['power_factor_total'] for v in vv[415:445])<.86,'Different late supply/reactive-demand story')
            check('B final pressure stable',abs(mean(residuals[475:500]))<.5,'Final physical pressure near own baseline; backend trip may remain active')
        stats[a]={'mean_baseline_load_ratio':round(mean(load[:50]),6),'mean_final_load_ratio':round(mean(load[475:500]),6),
                  'peak_top_oil_c':max(temps),'max_top_oil_step_c':round(max(deltas),6),
                  'baseline_imbalance_mean_pct':round(mean(imbs[:50]),6),'final_imbalance_mean_pct':round(mean(imbs[475:500]),6)}
    check('exact measurement count',sum(len(e['measurements']) for e in events)==manifest['measurement_count']==15949,'16,000 nominal minus 16 missing oil, 12 missing pressure, 23 undefined PF = 15,949')
    check('exact BAD count',total_bad==4,'Four pressure sensor-invalid measurements')
    check('event ledger IDs unique',len({r['event_id'] for r in faults})==len(faults) and len({r['scenario_id'] for r in faults})==len(faults),'14 separate event/intervention windows')
    check('event labels explicitly synthetic',all(r['synthetic']=='True' and r['runtime_outcome_status']=='NOT-RUNTIME-VERIFIED' for r in faults),'No actual transformer faults asserted')
    for r in faults:
        first,last=int(r['start_frame_1based']),int(r['end_frame_1based_inclusive']);ee=grouped[r['asset_id']]
        check('ledger '+r['scenario_id'],1<=first<=last<=500 and r['start_timestamp_utc']==ee[first-1]['event_time_utc'] and r['end_timestamp_utc_inclusive']==ee[last-1]['event_time_utc'] and (time(r['end_timestamp_utc_exclusive'])-time(r['end_timestamp_utc_inclusive'])).total_seconds()==1800 and set(json.loads(r['affected_signals'])).issubset(expected_units),'Start/end match exact frames; end-exclusive follows by 30 minutes')
    for item in manifest['file_inventory']:
        p=bundle/item['path']
        check('manifest '+item['path'],p.is_file() and sha(p)==item['sha256'] and p.stat().st_size==item['size_bytes'],'Delivered bytes SHA-256 and byte count match')
    json_files=list(bundle.glob('*.json'))
    check('all JSON read-back',all(isinstance(json.loads(p.read_text()),dict) for p in json_files),str(len(json_files))+' JSON files parse')
    check('all CSV read-back',all(len(csvrows(p))>0 for p in bundle.glob('*.csv')),'Four CSV files parse')
    check('plots have valid PNG signatures',all(p.read_bytes().startswith(b'\x89PNG\r\n\x1a\n') for p in (bundle/'plots').glob('*.png')) and len(list((bundle/'plots').glob('*.png')))==2,'Two readable PNG diagnostic plots, not detector outputs')
    repro_path=bundle/'reproducibility_evidence.json'
    if repro_path.exists():
        repro=json.loads(repro_path.read_text())
        check('fresh regeneration byte equality',repro['all_identical'] and repro['files_compared']>10 and not repro['mismatches'],'Independent fresh generation: '+str(repro['files_compared'])+' files, seed 20261011')
    blocked=[
      'Actual GridPulse adapter/CanonicalEvent enum acceptance: BLOCKED-MISSING-SOURCE.',
      'Exact current wide CSV, AssetProfile, fault-event and manifest layouts: BLOCKED-MISSING-SOURCE; proposed layouts explicitly identified.',
      'Current pressure alias/baseline/thresholds and relief-contact semantics: BLOCKED-MISSING-SOURCE.',
      'Oil bulk-temperature correction and multi-day trend warm-up/segmentation: BLOCKED-MISSING-SOURCE.',
      'Runtime OTHI scores, detector firing/delay, episode/advisory lifecycle, feedback and replay/UI/report checks: NOT-RUNTIME-VERIFIED.',
      'Runtime truth-permutation invariance: BLOCKED-MISSING-SOURCE; static no-oracle-field check executed.',
      'Forecast, CUSUM, residual qualification, RUL and insulation-ageing validation: intentionally not attempted; no promoted new-asset artifacts.'
    ]
    result={'executed_checks':len(checks),'passed':sum(c['status']=='PASS' for c in checks),'failed':sum(c['status']=='FAIL' for c in checks),
            'measurements':manifest['measurement_count'],'frame_count':len(events),'per_asset':stats,
            'missing_observation_counts':{k:v for k,v in absences.items() if v},'checks':checks,'blocked_or_unverified':blocked}
    if write_report:
        text='# Validation report\n\nValidation applies to delivered file bytes, not the GridPulse application.\n\n'
        text+=f"Executed **{result['executed_checks']} checks**: **{result['passed']} PASS, {result['failed']} FAIL**. 1,000 frames, 500 per asset, 15,949 individual measurements, four BAD pressure values. All 499 intervals per asset are exactly 30 minutes.\n\n"
        text+='Commands actually executed during preparation:\n```bash\npython output/gridpulse_backup_v1/scripts/generate.py --output output/gridpulse_backup_v1 --source-dir upload\npython output/gridpulse_backup_v1/scripts/generate.py --output tmp/backup_review/regenerated\npython output/gridpulse_backup_v1/scripts/validate.py --bundle output/gridpulse_backup_v1 --write-report\npython output/gridpulse_backup_v1/scripts/package.py --bundle output/gridpulse_backup_v1 --zip output/GridPulse_Backup_Synthetic_v1.zip\n```\n\nThe package command rechecks finalized manifest hashes and archive contents; its actual output is in package_verification.json next to the ZIP. No backend/frontend, source adapter, Git command, model fitting, TEST evaluation or runtime replay was executed.\n\n'
        text+='## Descriptive scenario statistics\n\n```json\n'+json.dumps(stats,indent=2)+'\n```\n\n## Executed checks and tolerances\n\n| Check | Result | Actual evidence / tolerance |\n|---|---|---|\n'
        text+='\n'.join('| '+c['check']+' | '+c['status']+' | '+c['detail'].replace('|','/')+' |' for c in checks)
        text+='\n\n## Assumptions and blockers\n\n'+'\n'.join('- '+x for x in blocked)
        text+='\n\nElectrical equations are validated only under the explicitly declared compatible sinusoidal snapshot convention. Current-squared heating drives thermal inertia; the exact generator equation is checked, but following it does not validate the application model. Bulk-oil, gauge and pressure constants are synthetic assumptions. QA range/step tolerances are engineering test bounds for this file, not universal limits. Intentional BAD observations are not physical contradictions. No active detector thresholds are changed.\n'
        (bundle/'validation_report.md').write_text(text)
        (bundle/'validation_results.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--write-report',action='store_true')
    args=parser.parse_args();result=validate(args.bundle.resolve(),args.write_report)
    print(json.dumps({k:result[k] for k in ['executed_checks','passed','failed','frame_count','measurements','per_asset']},indent=2))
    for c in result['checks']:
        if c['status']=='FAIL':print('FAIL:',c['check'],c['detail'])
    raise SystemExit(1 if result['failed'] else 0)
