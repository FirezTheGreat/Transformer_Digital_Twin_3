import sys
sys.path.insert(0, 'backend')
from app.core.config import Settings
from app.api.deps import build_runtime_reducer
from app.core.storage import StorageEngine
from app.engine.replay import ReplayEngine
from app.api.routers.replay import ensure_dataset_loaded
from collections import Counter

def check_asset(asset_id: str, n_events: int = 100):
    print(f"\n=======================================================")
    print(f"ASSET: {asset_id}")
    storage = StorageEngine(db_path=":memory:")
    replay = ReplayEngine(storage=storage, asset_id=asset_id)
    ensure_dataset_loaded(storage, replay, asset_id)
    events = replay._events
    print(f"Total events in replay: {len(events)}")
    if not events:
        return
    
    settings = Settings(default_asset_id=asset_id)
    reducer = build_runtime_reducer(settings=settings)
    
    state = None
    scores = []
    frames_info = []
    
    for i, ev in enumerate(events[:n_events]):
        state = reducer.reduce(state, ev)
        hb = state.health_bundle
        score = hb.othi_score if hb else None
        raw = hb.raw_othi if hb else None
        dom_sevs = {d.domain_name: d.severity for d in hb.domains.values()} if hb and hb.domains else {}
        max_d = max(dom_sevs.values()) if dom_sevs else 0.0
        scores.append(score)
        if score is not None and score < 100:
            evidence_ids = [e.detector_id for e in reducer.latest_emitted_evidence]
            frames_info.append((i, ev.event_time_utc, score, raw, hb.driving_domain, max_d, dom_sevs, evidence_ids))
            
    print(f"Scores distribution in first {min(len(events), n_events)} frames: {Counter(scores)}")
    print(f"Frames with OTHI < 100: {len(frames_info)}")
    for f in frames_info[:15]:
        print(f" Frame {f[0]} ({f[1]}): OTHI={f[2]}, raw={f[3]}, driving={f[4]}, max_sev={f[5]:.2f}")
        print(f"   dom_sevs={f[6]}")
        print(f"   detectors={f[7]}")

if __name__ == '__main__':
    for aid in ['TX_1000_COMM', 'TX_250_MIX', 'DT-01', 'DT-02']:
        try:
            check_asset(aid, 100)
        except Exception as e:
            print(f"Error checking {aid}: {e}")
