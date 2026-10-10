import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))

import pandas as pd
from app.adapters.cpri_v3 import CPRIv3SourceAdapter
from app.api.deps import build_runtime_reducer
from app.core.config import Settings
from app.engine.feedback import OperatorFeedbackLedger

cal_parquet = "data/processed/cpri_v3_calibration.parquet"
asset_id = "TX_1000_COMM"

df = pd.read_parquet(cal_parquet, filters=[("meta_transformer_id", "==", asset_id)])
df = df.drop(columns=[c for c in df.columns if c.startswith("y_")])
adapter = CPRIv3SourceAdapter()
records = df.to_dict("records")

settings = Settings()
settings.default_asset_id = asset_id
feedback_ledger = OperatorFeedbackLedger()
reducer = build_runtime_reducer(settings, feedback_ledger)

state = None
for i in [0, 1, 2, 3]:
    rec = records[i]
    event = adapter.transform_record(rec, asset_id=asset_id, source_uri=cal_parquet, source_record_id=f"cal_{asset_id}_{i}")
    state = reducer.reduce(state, event)

print("--- Frame 3 Details ---")
print("Event measurements:")
for m in event.measurements:
    print(f"  {m.signal_id}: {m.value}")

print("\nDerived Electrical:")
print(state.derived_electrical)

print("\nOpen Episodes:")
for ep in state.open_episodes:
    print(f"  {ep.episode_id}: cat={ep.category.value}, sev={ep.peak_severity}, state={ep.state.value}, rule={ep.rule_id}, summary={ep.summary}")

print("\nActive Recommendations:")
for r in state.active_recommendations:
    print(f"  {r.rec_id}: prio={r.priority.value}, rule={r.rule_id}, action={r.action_title}")
