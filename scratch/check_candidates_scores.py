import sys
sys.path.insert(0, 'backend')
from collections import Counter
import pandas as pd
from app.adapters.gridpulse_synthetic import GridPulseSyntheticAdapter
from app.api.deps import build_runtime_reducer
from app.core.config import Settings

df = pd.read_csv('data/candidates/gridpulse_synthetic_v1/gridpulse_synthetic_30min.csv', low_memory=False)
adapter = GridPulseSyntheticAdapter()

for asset_id in ['DT-01', 'DT-02', 'DT-03', 'DT-04']:
    df_asset = df[(df['asset_id'] == asset_id) & (df['partition'] == 'CAL')].sort_values('timestamp_utc').reset_index(drop=True)
    events = [adapter.transform_record(r, asset_id=asset_id, source_uri='test', source_record_id=f'{asset_id}_{i}') for i, r in enumerate(df_asset.to_dict('records'))]
    reducer = build_runtime_reducer(settings=Settings(default_asset_id=asset_id))
    state = None
    scores = []
    jump_info = []
    prev_s = 100
    for i, ev in enumerate(events):
        state = reducer.reduce(state, ev)
        s = state.health_bundle.othi_score if state.health_bundle else None
        scores.append(s)
        if prev_s == 100 and s is not None and s <= 30:
            doms = {d.domain_name: d.severity for d in state.health_bundle.domains.values()}
            evs = [e.detector_id for e in reducer.latest_emitted_evidence]
            jump_info.append((i, ev.event_time_utc, prev_s, s, state.health_bundle.driving_domain, doms, evs))
        if s is not None:
            prev_s = s
            
    print(f"\n================ ASSET {asset_id} (CAL: {len(events)} frames) ================")
    print("Unique scores and counts:", Counter(scores).most_common(10))
    print(f"Jumps from 100 to <= 30: {len(jump_info)}")
    for j in jump_info[:5]:
        print(f" Jump at frame {j[0]} ({j[1]}): {j[2]} -> {j[3]} (driving: {j[4]})")
        print(f"   doms: {j[5]}")
        print(f"   detectors: {j[6]}")
