import sys
sys.path.insert(0, 'backend')
import pandas as pd
from app.adapters.gridpulse_synthetic import GridPulseSyntheticAdapter
from app.api.deps import build_runtime_reducer
from app.core.config import Settings

df = pd.read_csv('data/candidates/gridpulse_synthetic_v1/gridpulse_synthetic_30min.csv', low_memory=False)
adapter = GridPulseSyntheticAdapter()
df_asset = df[(df['asset_id'] == 'DT-02') & (df['partition'] == 'CAL')].sort_values('timestamp_utc').reset_index(drop=True)
events = [adapter.transform_record(r, asset_id='DT-02', source_uri='test', source_record_id=f'DT-02_{i}') for i, r in enumerate(df_asset.to_dict('records'))]
reducer = build_runtime_reducer(settings=Settings(default_asset_id='DT-02'))

zero_frames = []
state = None
for i, ev in enumerate(events):
    state = reducer.reduce(state, ev)
    hb = state.health_bundle
    if hb and hb.othi_score == 0:
        zero_frames.append((i, ev.event_time_utc, hb.driving_domain, hb.driving_condition_family, reducer.othi_engine.latched_protection_trip))

print(f"Total zero frames: {len(zero_frames)}")
if zero_frames:
    print(f"First zero frame: {zero_frames[0]}")
    print(f"Last zero frame: {zero_frames[-1]}")
    # inspect the first zero frame event
    first_idx = zero_frames[0][0]
    ev = events[first_idx]
    print("Measurements in first zero event:")
    for m in ev.measurements:
        if m.signal_id in ('breaker_trip', 'lv_breaker_closed', 'lv_breaker_trip', 'top_oil_temp_trip', 'oil_level_percent', 'top_oil_temperature'):
            print(f"  {m.signal_id} = {m.value} (flags: {m.quality.flags if m.quality else []})")
    print(f"Quality flags on event: {ev.event_quality_flags}")
