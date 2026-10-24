"""#76: every planet circle gets its own recognizable colour, with readable contrast and no external assets."""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "static" / "arcade.css"
SLUGS = ["mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune"]
PANELS = ["#13204a", "#101b40"]  # duel/quiz panel and scale/inset panel backgrounds
PAPER = "#f4e9d2"


def _rgb(hex_):
    hex_ = hex_.lstrip("#")
    return tuple(int(hex_[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _rule(css, selector):
    match = re.search(r"(?:^|})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css, re.MULTILINE)
    assert match, selector
    return match.group(1)


def _planet_rule(css, slug):
    return _rule(css, f'[data-planet="{slug}"]')


def _base(css, slug):
    return _rgb(re.search(r"--planet:\s*(#[0-9a-fA-F]{6})", _planet_rule(css, slug)).group(1))


def test_each_planet_has_its_own_colour():
    css = CSS.read_text()
    colours = {slug: _base(css, slug) for slug in SLUGS}
    assert len(set(colours.values())) == 8


def test_colours_suit_the_planets():
    css = CSS.read_text()
    r, g, b = _base(css, "mars")
    assert r > g + 60 and r > b + 60, "Mars is rusty red"
    r, g, b = _base(css, "earth")
    assert b > r + 60 and b > g, "Earth is blue"
    r, g, b = _base(css, "neptune")
    assert b > r + 60 and b > g + 30, "Neptune is deep blue"
    r, g, b = _base(css, "jupiter")
    assert r > g > b, "Jupiter is tan"
    jupiter = _planet_rule(css, "jupiter")
    assert re.search(r"--planet-surface:\s*repeating-linear-gradient\(", jupiter), "Jupiter is banded"


def test_colours_stand_out_from_the_panels():
    css = CSS.read_text()
    for slug in SLUGS:
        for panel in PANELS:
            assert _contrast(_base(css, slug), _rgb(panel)) >= 3, (slug, panel)


def test_every_circle_is_tagged_with_its_planet(client):
    html = client.get("/?left=mars&right=earth&round=1&choice=earth").text
    for cls in ("duel-portrait", "quiz-planet", "scale-bar", "inset-circle"):
        tags = re.findall(r'class="' + cls + r'"[^>]*?data-planet="(\w+)"', html)
        assert tags, cls
        assert set(tags) <= set(SLUGS), cls
    scale = re.findall(r'class="scale-bar" data-planet="(\w+)"', html)
    assert sorted(scale) == sorted(SLUGS)
    inset = re.findall(r'class="inset-circle" data-planet="(\w+)"', html)
    assert sorted(inset) == ["earth", "mars", "mercury", "venus"]


def test_circle_fills_use_the_planet_colour():
    css = CSS.read_text()
    for selector in (".duel-portrait", ".quiz-planet", ".scale-bar", ".inset-circle"):
        assert "var(--planet" in _rule(css, selector), selector


def test_labels_inside_scale_circles_stay_readable():
    css = CSS.read_text()
    for selector in (".scale-bar", ".inset-circle"):
        rule = _rule(css, selector)
        overlay = re.search(r"rgb\((\d+) (\d+) (\d+) / (0?\.\d+)\)", rule)
        assert overlay, f"{selector} needs a dark overlay so labels stay readable"
        *over, alpha = overlay.groups()
        alpha = float(alpha)
        for slug in SLUGS:
            surface = _planet_rule(css, slug)
            for hex_ in re.findall(r"#[0-9a-fA-F]{6}", surface):
                mixed = tuple(alpha * int(o) + (1 - alpha) * c for o, c in zip(over, _rgb(hex_)))
                assert _contrast(mixed, _rgb(PAPER)) >= 4.5, (selector, slug, hex_)


def test_no_external_assets():
    css = CSS.read_text()
    assert "url(" not in css and "@import" not in css
