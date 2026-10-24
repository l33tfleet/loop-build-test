def test_km_mi_roundtrip(client):
    mi = client.get("/convert", params={"value": 5, "src": "km", "dst": "mi"}).json()["value"]
    km = client.get("/convert", params={"value": mi, "src": "mi", "dst": "km"}).json()["value"]
    assert abs(km - 5) < 0.001

# Diagnostic (Issue #8): existing regression files are append-only; this edit must fail CI.
