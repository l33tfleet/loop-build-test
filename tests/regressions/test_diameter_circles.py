import re

EXPECTED_KM = {"Mercury": 4879, "Venus": 12104, "Earth": 12756, "Mars": 6792,
               "Jupiter": 142984, "Saturn": 120536, "Uranus": 51118, "Neptune": 49528}
SECTION = re.compile(r'<section class="diameter-scale"[^>]*>(.*?)</section>', re.DOTALL)
ROW = re.compile(r'<li class="scale-row"[^>]*>(.*?)</li>', re.DOTALL)


def _rules(css, selector):
    return " ".join(re.findall(re.escape(selector) + r"\s*\{([^}]*)\}", css))


def test_each_planet_is_a_circle_not_a_bar(client):
    css = client.get("/static/arcade.css").text
    circle = _rules(css, ".scale-bar")
    assert re.search(r"border-radius:\s*50%", circle)
    assert re.search(r"aspect-ratio:\s*1\b", circle)
    assert not re.search(r"(?<![-\w])height:", circle), "fixed height would squash the circle into a bar"


def test_circles_share_one_square_frame(client):
    css = client.get("/static/arcade.css").text
    # Every circle's width % is taken against the same square track, so diameters stay proportional.
    track = _rules(css, ".scale-track")
    assert re.search(r"aspect-ratio:\s*1\b", track)
    assert not re.search(r"(?<![-\w])height:\s*\d", track)
    assert "border-bottom" not in track


def test_circle_diameters_are_proportional(client):
    section = SECTION.search(client.get("/").text).group(1)
    rows = ROW.findall(section)
    assert len(rows) == 8
    largest = max(EXPECTED_KM.values())
    for body in rows:
        name = re.search(r'class="scale-name"[^>]*>([^<]*)<', body).group(1).strip()
        pct = float(re.search(r'class="scale-bar"[^>]*style="width:\s*([\d.]+)%', body).group(1))
        assert abs(pct - 100 * EXPECTED_KM[name] / largest) < 0.01, name


def test_note_describes_circles(client):
    section = SECTION.search(client.get("/").text).group(1)
    note = re.search(r'class="scale-note"[^>]*>(.*?)</p>', section, re.DOTALL).group(1).lower()
    assert "circle" in note and "diameter" in note
    assert "bar" not in note
