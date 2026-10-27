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


def test_snapshot_planet_names_render_as_h3(client):
    names = [planet["name"] for planet in json.loads(SNAPSHOT.read_text())["planets"]]
    cards = CARD.findall(client.get("/").text)
    assert len(cards) == len(names) == 8
    assert [re.findall(r"<h3\b[^>]*>(.*?)</h3>", body) for body in cards] == [
        [name] for name in names
    ]


