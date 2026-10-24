def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_km_to_mi(client):
    assert client.get("/convert", params={"value": 10, "src": "km", "dst": "mi"}).json()["value"] == 6.2137


def test_unsupported(client):
    assert client.get("/convert", params={"value": 1, "src": "km", "dst": "lb"}).status_code == 400
