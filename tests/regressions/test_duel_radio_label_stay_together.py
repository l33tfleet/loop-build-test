"""#60: each duel radio and its planet name wrap as one unit, so a 390px row never splits them."""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "static" / "arcade.css"
NAMES = ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]
CHOICE = re.compile(r'<span class="duel-radio-pair">\s*(<input [^>]*>)\s*(<label [^>]*>[^<]*</label>)\s*</span>')


def _rules(css, selector):
    return " ".join(re.findall(r"(?:^|[},])\s*" + re.escape(selector) + r"\s*(?:,[^{]*)?\{([^}]*)\}", css, re.MULTILINE))


def test_each_radio_and_its_label_share_one_wrapper_in_both_fieldsets(client):
    html = client.get("/", params={"left": "mars", "right": "uranus"}).text
    section = re.search(r'<section class="planet-duel"[^>]*>(.*?)</section>', html, re.DOTALL).group(1)
    groups = re.findall(r'<fieldset class="duel-field"[^>]*>(.*?)</fieldset>', section, re.DOTALL)
    assert len(groups) == 2
    for group, side in zip(groups, ("left", "right")):
        pairs = CHOICE.findall(group)
        assert len(pairs) == len(NAMES), "every radio needs its own wrapper with its label"
        # Nothing but the legend and the wrapped pairs sits in the fieldset.
        assert re.sub(r"\s+", "", CHOICE.sub("", re.sub(r"<legend>[^<]*</legend>", "", group))) == ""
        for (radio, label), name in zip(pairs, NAMES):
            slug = name.lower()
            assert f'id="duel-{side}-{slug}"' in radio and f'name="{side}"' in radio
            assert label == f'<label for="duel-{side}-{slug}">{name}</label>'
        checked = [name for (radio, _), name in zip(pairs, NAMES) if " checked" in radio]
        assert checked == (["Mars"] if side == "left" else ["Uranus"])


def test_wrapper_is_an_inline_flex_nowrap_unit():
    css = CSS.read_text()
    rule = _rules(css, ".duel-radio-pair")
    assert re.search(r"display:\s*inline-flex", rule)
    assert re.search(r"white-space:\s*nowrap", rule)
    assert re.search(r"align-items:\s*center", rule)
    assert not re.search(r"flex-wrap:\s*wrap", rule)


def test_checked_style_and_focus_ring_still_reach_the_pair():
    css = CSS.read_text()
    assert re.search(r"font-weight:\s*600", _rules(css, ".duel-field input:checked + label"))
    assert re.search(r"outline:\s*3px solid", _rules(css, ".duel-form :focus-visible"))
