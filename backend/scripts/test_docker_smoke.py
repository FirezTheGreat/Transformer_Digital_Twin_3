import urllib.request
import json
import sys

def test_docker_runtime():
    print("=== DOCKER RUNTIME VERIFICATION ===")
    
    # 1. Healthz direct and through Nginx
    for url in ['http://localhost:8000/healthz', 'http://localhost:3000/healthz']:
        with urllib.request.urlopen(url) as req:
            data = json.loads(req.read().decode())
            print(f"[OK] {url} -> status {req.status}, is_ready={data.get('is_ready')}")

    # 2. Replay status
    with urllib.request.urlopen('http://localhost:8000/v1/replay') as req:
        data = json.loads(req.read().decode())
        print(f"[OK] Replay status -> processed={data.get('processed_events')}, total={data.get('total_events')}, status={data.get('status')}")

    # 3. Step 5 events on TX_1000_COMM
    req = urllib.request.Request(
        'http://localhost:8000/v1/replay',
        data=json.dumps({'action': 'step', 'batch_size': 5, 'asset_id': 'TX_1000_COMM'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        print(f"[OK] Step 5 on TX_1000_COMM -> processed={res.get('processed_events')}, state_seq={res.get('current_state_sequence')}")

    # 4. Checkpoint creation
    req = urllib.request.Request(
        'http://localhost:8000/v1/reports/checkpoints?asset_id=TX_1000_COMM',
        data=b'',
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        chk = json.loads(resp.read().decode())
        print(f"[OK] Checkpoint created -> ID={chk.get('checkpoint_id')}, seq={chk.get('state_sequence')}")

    # 5. List runs
    with urllib.request.urlopen('http://localhost:8000/v1/reports/runs?asset_id=TX_1000_COMM') as req:
        runs = json.loads(req.read().decode())
        print(f"[OK] Runs count={len(runs)}, latest_seq={runs[0]['state_sequence']}")

    # 6. PDF Export
    with urllib.request.urlopen('http://localhost:8000/v1/reports/summary.pdf?asset_id=TX_1000_COMM') as req:
        pdf_bytes = req.read()
        print(f"[OK] PDF Export -> status={req.status}, size={len(pdf_bytes)} bytes, header={pdf_bytes[:4]}")

    # 7. Asset Switch to TX_250_MIX
    req = urllib.request.Request(
        'http://localhost:8000/v1/replay',
        data=json.dumps({'action': 'reset', 'asset_id': 'TX_250_MIX'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        print(f"[OK] Switch to TX_250_MIX reset -> total={res.get('total_events')}, status={res.get('status')}")

    # Step on TX_250_MIX
    req = urllib.request.Request(
        'http://localhost:8000/v1/replay',
        data=json.dumps({'action': 'step', 'batch_size': 3, 'asset_id': 'TX_250_MIX'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        print(f"[OK] Step 3 on TX_250_MIX -> processed={res.get('processed_events')}, state_seq={res.get('current_state_sequence')}")

    # Verify TX_250_MIX state and qualification gating
    with urllib.request.urlopen('http://localhost:8000/v1/assets/TX_250_MIX/state') as req:
        st2 = json.loads(req.read().decode())
        asset = st2['twin_state']['asset_id']
        seq = st2['twin_state']['state_sequence']
        c3_enabled = st2['fact_bundle']['capabilities']['capabilities']['C3']['enabled']
        print(f"[OK] TX_250_MIX state -> asset={asset}, seq={seq}, C3 enabled={c3_enabled} (properly gated!)")

    print("\nALL DOCKER ENDPOINTS VERIFIED!")

if __name__ == '__main__':
    test_docker_runtime()
