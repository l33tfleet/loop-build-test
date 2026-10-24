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


def test_scale_and_inset_fills_show_the_full_planet_colour():
    # #76 feedback: a navy veil over the fills turned Jupiter and Saturn grey and Venus taupe.
    css = CSS.read_text()
    for selector in (".scale-bar", ".inset-circle"):
        rule = _rule(css, selector)
        assert re.search(r"background:\s*var\(--planet-surface\)\s*;", rule), selector
        assert not re.search(r"rgb\([^)]*/", rule), f"{selector} must not dull the colour with a translucent layer"


def test_labels_on_the_circles_keep_readable_contrast():
    # The labels sit on the coloured fills, so each gets its own solid navy backing: paper on it is >= 4.5:1.
    css = CSS.read_text()
    for selector in (".scale-label", ".inset-label"):
        rule = _rule(css, selector)
        backing = re.search(r"background:\s*var\(--navy\)\s*;", rule)
        assert backing, f"{selector} needs a solid navy backing"
        assert _contrast(_rgb("#0b1530"), _rgb(PAPER)) >= 4.5
        assert _contrast(_rgb("#0b1530"), _rgb("#d9deea")) >= 4.5  # --ink, the km value colour


def test_bar_view_labels_drop_the_backing():
    css = CSS.read_text()
    bar_label = re.search(r"#scale-view-bars:checked ~ \.scale-rows \.scale-label\s*\{([^}]*)\}", css).group(1)
    assert re.search(r"background:\s*none", bar_label)


def test_no_external_assets():
    css = CSS.read_text()
    assert "url(" not in css and "@import" not in css
