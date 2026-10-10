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
print(f"Total CAL records for {asset_id}: {len(records)}")

for i in range(15):
    rec = records[i]
    event = adapter.transform_record(
        rec,
        asset_id=asset_id,
        source_uri=cal_parquet,
        source_record_id=f"cal_{asset_id}_{i}"
    )
    state = reducer.reduce(state, event)
    hb = state.health_bundle
    print(f"Frame {i}: time={event.event_time_utc}, OTHI={hb.othi_score if hb else 'None'}, raw_othi={hb.raw_othi if hb else 'None'}, grade={hb.evidence_grade.value if hb else 'None'}, gated={hb.is_gated if hb else 'None'}, gate_reason={hb.gate_reason if hb else 'None'}")
    if hb:
        for dname, dval in hb.domains.items():
            if dval.severity > 0:
                print(f"   Domain {dname}: sev={dval.severity}, status={dval.status.value}, details={dval.details}")
