import json
import re
from html import unescape
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "planets.json"
SUN_ORDER = ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]
EXPECTED_KM = {"Mercury": 4879, "Venus": 12104, "Earth": 12756, "Mars": 6792,
               "Jupiter": 142984, "Saturn": 120536, "Uranus": 51118, "Neptune": 49528}
CARD = re.compile(r'<article class="planet-card"[^>]*>(.*?)</article>', re.DOTALL)


def _cards(html):
    cards = []
    for body in CARD.findall(html):
        name = unescape(re.search(r"<h2[^>]*>(.*?)</h2>", body, re.DOTALL).group(1)).strip()
        diameter = unescape(re.search(r'class="diameter"[^>]*>(.*?)<', body, re.DOTALL).group(1)).strip()
        cards.append((name, diameter))
    return cards


def test_snapshot_has_eight_planets_in_sun_order():
    data = json.loads(SNAPSHOT.read_text())
    assert [p["name"] for p in data["planets"]] == SUN_ORDER
    assert {p["name"]: p["diameter_km"] for p in data["planets"]} == EXPECTED_KM
    assert data["source"]["url"].startswith("https://")


def test_source_link_visible(client):
    html = client.get("/").text
    url = json.loads(SNAPSHOT.read_text())["source"]["url"]
    assert re.search(rf'<a [^>]*href="{re.escape(url)}"', html)


def test_shelf_wraps_on_narrow_screens(client):
    html = client.get("/").text
    assert 'name="viewport" content="width=device-width' in html
    css = client.get("/static/arcade.css").text
    assert re.search(r"\.shelf\s*\{[^}]*display:\s*grid", css)
    assert "minmax(min(" in css
