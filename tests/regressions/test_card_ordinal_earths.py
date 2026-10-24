import json
import re
from html import unescape
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "planets.json"
CARD = re.compile(r'<article class="planet-card"[^>]*>(.*?)</article>', re.DOTALL)
ORDINALS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]


def _cards(client):
    """Map each planet name to its card's visible text."""
    cards = {}
    for body in CARD.findall(client.get("/").text):
        name = unescape(re.search(r"<h2[^>]*>(.*?)</h2>", body, re.DOTALL).group(1)).strip()
        cards[name] = " ".join(unescape(re.sub(r"<[^>]+>", " ", body)).split())
    return cards


def test_cards_show_ordinal_from_the_sun_not_hash_rank(client):
    planets = json.loads(SNAPSHOT.read_text())["planets"]
    cards = _cards(client)
    for p in planets:
        assert f"{ORDINALS[p['order'] - 1]} from the Sun" in cards[p["name"]]
        assert not re.search(r"#\d", cards[p["name"]])
    assert "1st from the Sun" in cards["Mercury"]
    assert "8th from the Sun" in cards["Neptune"]


def test_jupiter_and_mercury_say_how_many_earths_wide(client):
    cards = _cards(client)
    assert "About 11 Earths wide" in cards["Jupiter"]
    assert "About 0.38 Earths wide" in cards["Mercury"]
    assert re.search(r"\b1 Earths? wide", cards["Earth"])


def test_earths_wide_follows_the_snapshot(client, monkeypatch):
    from app import main

    planets = [{**p, "diameter_km": p["diameter_km"] * 2} if p["name"] == "Mercury" else p
               for p in main.SNAPSHOT["planets"]]
    monkeypatch.setitem(main.SNAPSHOT, "planets", planets)
    assert "About 0.76 Earths wide" in _cards(client)["Mercury"]
