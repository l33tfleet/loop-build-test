import itertools
import re

EXPECTED_KM = {"Mercury": 4879, "Venus": 12104, "Earth": 12756, "Mars": 6792,
               "Jupiter": 142984, "Saturn": 120536, "Uranus": 51118, "Neptune": 49528}
SMALL = {"Mercury", "Venus", "Earth", "Mars"}
SECTION = re.compile(r'<section class="diameter-scale"[^>]*>(.*?)</section>', re.DOTALL)
ROW = re.compile(r'<li class="scale-row"([^>]*)>(.*?)</li>', re.DOTALL)
BARS = "#scale-view-bars:checked ~ .scale-rows"


def _section(client):
    return SECTION.search(client.get("/").text).group(1)


def _rows(client):
    rows = {}
    for attrs, body in ROW.findall(_section(client)):
        name = re.search(r'class="scale-name"[^>]*>([^<]*)<', body).group(1).strip()
        rows[name] = (attrs, body)
    return rows


def _rules(css, selector):
    return " ".join(re.findall(re.escape(selector) + r"\s*\{([^}]*)\}", css))


def test_toggle_defaults_to_circles_and_offers_bar_graph(client):
    section = _section(client)
    radios = re.findall(r'<input[^>]*type="radio"[^>]*>', section)
    assert len(radios) == 2
    assert all('name="scale-view"' in r for r in radios)
    circles = next(r for r in radios if 'id="scale-view-circles"' in r)
    bars = next(r for r in radios if 'id="scale-view-bars"' in r)
    assert "checked" in circles and "checked" not in bars
    assert re.search(r'<label[^>]*for="scale-view-bars"[^>]*>\s*Bar graph\s*</label>', section)
    # The CSS switches views with the sibling combinator, so the radios must precede the list.
    assert section.index('id="scale-view-bars"') < section.index('class="scale-rows"')


def test_circles_overlap_on_a_common_baseline(client):
    css = client.get("/static/arcade.css").text
    frame = _rules(css, ".scale-rows")
    assert re.search(r"position:\s*relative", frame)
    assert re.search(r"aspect-ratio:\s*1\b", frame)
    track = _rules(css, ".scale-track")
    # Every track fills the same frame, so the circles stack on top of one another.
    assert re.search(r"position:\s*absolute", track)
    assert re.search(r"inset:\s*0", track)
    assert re.search(r"align-items:\s*flex-end", track), "circles should sit on one shared baseline"
    assert re.search(r"justify-content:\s*center", track)


def test_larger_circles_are_drawn_behind_smaller_ones(client):
    rows = _rows(client)
    z = {name: int(re.search(r"--z:\s*(\d+)", attrs).group(1)) for name, (attrs, _) in rows.items()}
    by_size = sorted(EXPECTED_KM, key=EXPECTED_KM.get, reverse=True)
    assert [z[name] for name in by_size] == sorted(z.values())
    css = client.get("/static/arcade.css").text
    assert "z-index: var(--z)" in _rules(css, ".scale-track")


def test_small_planets_get_leader_lines_from_their_circle_top(client):
    rows = _rows(client)
    largest = max(EXPECTED_KM.values())
    ends = []
    for name, (_, body) in rows.items():
        line = re.search(r'<svg class="scale-leader".*?<line ([^>]*)>', body, re.DOTALL)
        if name not in SMALL:
            assert line is None, name
            continue
        assert line, name
        coords = {k: float(v) for k, v in re.findall(r'(x1|y1|x2|y2)="([\d.]+)"', line.group(1))}
        assert coords["x1"] == 50
        assert abs(coords["y1"] - (100 - 100 * EXPECTED_KM[name] / largest)) < 0.01, name
        assert 'class="scale-label scale-label--leader"' in body
        ends.append(coords["y2"])
    ends.sort()
    assert len(ends) == 4
    assert all(b - a >= 8 for a, b in itertools.pairwise(ends)), "leader labels must not overlap"


def test_near_equal_large_planets_are_labelled_apart(client):
    rows = _rows(client)
    def mode(name):
        return re.search(r'class="scale-label scale-label--(\w+)"', rows[name][1]).group(1)
    assert {mode("Uranus"), mode("Neptune")} == {"above", "inside"}
    assert mode("Jupiter") == "inside"


def test_bar_view_flattens_circles_into_bars(client):
    css = client.get("/static/arcade.css").text
    bar = _rules(css, f"{BARS} .scale-bar")
    assert re.search(r"aspect-ratio:\s*auto", bar)
    assert "50%" not in bar
    assert re.search(r"display:\s*none", _rules(css, f"{BARS} .scale-leader"))
    assert re.search(r"position:\s*static", _rules(css, f"{BARS} .scale-track"))
