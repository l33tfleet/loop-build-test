def test_home_has_marker(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'data-marker="solar-arcade"' in r.text


def test_stylesheet_served(client):
    assert client.get("/static/arcade.css").status_code == 200
