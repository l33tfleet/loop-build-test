"""#101: after an answer the winning button keeps the paper fill and navy text; only the other button dims."""
import re
from pathlib import Path

import pytest

CSS = Path(__file__).resolve().parents[2] / "static" / "arcade.css"
WINNER_SELECTOR = ".planet-quiz button.quiz-winner"
DISABLED_SELECTOR = ".planet-quiz button:disabled"


def buttons(response):
    form = re.search(r'<section class="planet-quiz".*?<form\b.*?</form>', response.text, re.DOTALL)
    assert form, "Quiz form missing"
    found = re.findall(r'<button\b([^>]*)>(.*?)</button>', form.group(0), re.DOTALL)
    assert len(found) == 2
    return {re.search(r'value="([a-z]+)"', attrs).group(1): (attrs, body) for attrs, body in found}


def classes(attrs):
    match = re.search(r'class="([^"]*)"', attrs)
    return match.group(1).split() if match else []


@pytest.mark.parametrize("url,winner,picked", [
    ("/?round=1&score=0&choice=earth", "jupiter", "earth"),
    ("/?round=1&choice=jupiter", "jupiter", "jupiter"),
    ("/?round=2&choice=mercury", "mars", "mercury"),
    ("/?round=3&choice=uranus", "uranus", "uranus"),
])
def test_only_the_winner_carries_the_full_contrast_marker(client, url, winner, picked):
    found = buttons(client.get(url))
    for name, (attrs, body) in found.items():
        assert ("quiz-winner" in classes(attrs)) == (name == winner)
        # Both stay locked and aria-pressed still tracks the pick, not the winner.
        assert re.search(r"\bdisabled\b", attrs)
        assert f'aria-pressed="{"true" if name == picked else "false"}"' in attrs
    if winner == picked:
        body = found[winner][1]
        assert "Your pick" in body and "Larger ✓" in body


@pytest.mark.parametrize("number", [1, 2, 3])
def test_no_winner_marker_before_answering(client, number):
    for attrs, _ in buttons(client.get(f"/?round={number}")).values():
        assert "quiz-winner" not in classes(attrs)


def _rules(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^}]*)\}", css)]


def _resolve(css, value):
    var = re.fullmatch(r"var\((--[\w-]+)\)", value.strip())
    if var:
        value = re.search(re.escape(var.group(1)) + r":\s*(#[0-9a-fA-F]{6})", css).group(1)
    return value.strip().lower()


def _luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_winner_rule_overrides_the_dimmed_disabled_fill():
    css = CSS.read_text()
    rules = _rules(css)
    selectors = [s for s, _ in rules]
    assert DISABLED_SELECTOR in selectors and WINNER_SELECTOR in selectors
    # Same specificity (one class + one pseudo-class vs two classes), so the later rule wins the cascade.
    assert selectors.index(WINNER_SELECTOR) > selectors.index(DISABLED_SELECTOR)
    body = dict(rules)[WINNER_SELECTOR]
    background = _resolve(css, re.search(r"background:\s*([^;]+);", body).group(1))
    color = _resolve(css, re.search(r"(?<![-\w])color:\s*([^;]+);", body).group(1))
    assert background == _resolve(css, "var(--paper)") and background != "#8a96b8"
    assert color == _resolve(css, "var(--navy)")
    assert _contrast(color, background) >= 14.5  # "about 15:1"
    assert re.search(r"border:\s*\d+px solid", body)
    # Nothing later turns the winner back to the dimmed slate fill.
    for selector, later in rules[selectors.index(WINNER_SELECTOR) + 1:]:
        if "button" in selector and "planet-quiz" in selector:
            assert "#8a96b8" not in later.lower(), selector


def _matches_picked_loser(selector):
    # A wrong pick is a disabled, aria-pressed="true" quiz button without .quiz-winner.
    if not selector.startswith(".planet-quiz button") or "quiz-winner" in selector:
        return False
    rest = selector[len(".planet-quiz button"):]
    return re.fullmatch(r'(:disabled|\[aria-pressed="true"\])*', rest) is not None


@pytest.mark.parametrize("url,loser", [
    ("/?round=1&score=0&choice=earth", "earth"),
    ("/?round=2&choice=mercury", "mercury"),
])
def test_picked_non_winner_keeps_the_dimmed_fill(client, url, loser):
    attrs, _ = buttons(client.get(url))[loser]
    assert "quiz-winner" not in classes(attrs) and 'aria-pressed="true"' in attrs
    css = CSS.read_text()
    matching = [body for s, body in _rules(css)
                for sel in s.split(",") if _matches_picked_loser(sel.strip())]
    # Matching rules all tie on specificity (or lose to it), so the last background declared wins.
    backgrounds = [m.group(1) for body in matching for m in re.finditer(r"background:\s*([^;]+);", body)]
    assert backgrounds and _resolve(css, backgrounds[-1]) == "#8a96b8"
