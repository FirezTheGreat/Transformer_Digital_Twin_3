import httpx

r = httpx.get("http://127.0.0.1:3000/")
print("Status code:", r.status_code)
print("Title in HTML:", "<title>" in r.text)
print("HTML preview:\n", r.text[:300])

# Also test proxying through vite
r_api = httpx.get("http://127.0.0.1:3000/v1/models/cpri-evaluation")
print("Vite proxy /v1/models/cpri-evaluation status:", r_api.status_code)
assert r_api.status_code == 200
print("Proxy works seamlessly!")
