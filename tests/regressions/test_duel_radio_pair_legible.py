"""#60: the radio-and-name pill must stand out from the fieldset, not blend into its border and fill."""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "static" / "arcade.css"


def _rule(css, selector):
    match = re.search(r"(?:^|})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css, re.MULTILINE)
    assert match, selector
    return match.group(1)


def test_pill_border_differs_from_fieldset_border():
    css = CSS.read_text()
    pill = _rule(css, ".duel-radio-pair")
    assert re.search(r"border:\s*1px solid var\(--muted\)", pill)
    assert "#536694" not in pill


def test_pill_fill_is_a_paper_tint():
    pill = _rule(CSS.read_text(), ".duel-radio-pair")
    assert re.search(r"background:\s*rgb\(244 233 210 / 0?\.\d+\)", pill)
