"""#60: each duel radio and its name sit inside one visible outlined pill, so the pairing shows at any width."""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "static" / "arcade.css"


def _rules(css, selector):
    return " ".join(re.findall(r"(?:^|[},])\s*" + re.escape(selector) + r"\s*(?:,[^{]*)?\{([^}]*)\}", css, re.MULTILINE))


def test_pair_is_drawn_as_one_outlined_pill():
    rule = _rules(CSS.read_text(), ".duel-radio-pair")
    assert re.search(r"display:\s*inline-flex", rule)
    assert re.search(r"white-space:\s*nowrap", rule)
    assert re.search(r"border:\s*1px solid", rule)
    assert re.search(r"border-radius:\s*\d+px", rule)
    assert re.search(r"padding-left:\s*\d+px", rule), "the radio circle needs room inside the pill"


def test_checked_pair_outline_is_highlighted():
    rule = _rules(CSS.read_text(), ".duel-radio-pair:has(input:checked)")
    assert re.search(r"border-color:\s*var\(--paper\)", rule)
