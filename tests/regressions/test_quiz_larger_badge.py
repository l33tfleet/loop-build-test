"""#83: after an answer the winner's button carries a "Larger ✓" text badge, legible on the disabled fill."""
import re
from pathlib import Path

import pytest

CSS = Path(__file__).resolve().parents[2] / "static" / "arcade.css"
BADGE = "Larger ✓"


def buttons(response):
    form = re.search(r'<section class="planet-quiz".*?<form\b.*?</form>', response.text, re.DOTALL)
    assert form, "Quiz form missing"
    found = re.findall(r'<button\b[^>]*value="([a-z]+)"[^>]*>(.*?)</button>', form.group(0), re.DOTALL)
    assert len(found) == 2
    return dict(found)


def test_correct_pick_shows_both_badges_on_the_winner(client):
    found = buttons(client.get("/?round=1&choice=jupiter"))
    assert "Your pick" in found["jupiter"] and BADGE in found["jupiter"]
    assert "Your pick" not in found["earth"] and BADGE not in found["earth"]


def test_wrong_pick_splits_badges_across_buttons(client):
    found = buttons(client.get("/?round=1&choice=earth"))
    assert "Your pick" in found["earth"] and BADGE not in found["earth"]
    assert BADGE in found["jupiter"] and "Your pick" not in found["jupiter"]


@pytest.mark.parametrize("url,winner", [("/?round=2&choice=mercury", "mars"), ("/?round=3&choice=uranus", "uranus")])
def test_badge_follows_quiz_winner(client, url, winner):
    for name, body in buttons(client.get(url)).items():
        assert (BADGE in body) == (name == winner)
        if name == winner:
            assert re.search(r'<span class="quiz-larger">Larger ✓</span>', body)


@pytest.mark.parametrize("number", [1, 2, 3])
def test_no_badges_before_answering(client, number):
    for body in buttons(client.get(f"/?round={number}")).values():
        assert BADGE not in body and "Your pick" not in body


def _rule(css, selector):
    match = re.search(r"(?:^|})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css, re.MULTILINE)
    assert match, selector
    return match.group(1)


def _luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _resolve(css, value):
    var = re.fullmatch(r"var\((--[\w-]+)\)", value)
    if var:
        value = re.search(re.escape(var.group(1)) + r":\s*(#[0-9a-fA-F]{6})", css).group(1)
    assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), value
    return value


def test_badge_text_contrasts_with_disabled_button_and_not_by_colour_alone():
    css = CSS.read_text()
    badge = _rule(css, ".quiz-larger")
    disabled = _rule(css, ".planet-quiz button:disabled")
    text = _resolve(css, re.search(r"(?<![-\w])color:\s*([^;]+);", badge).group(1).strip())
    fill = _resolve(css, re.search(r"background:\s*([^;]+);", disabled).group(1).strip())
    # The badge has no fill of its own, so its text sits on the disabled button background.
    assert re.search(r"background:\s*transparent", badge)
    assert _contrast(text, fill) >= 4.5
    # A visible outline marks the badge shape regardless of hue.
    assert re.search(r"border:\s*\d+px solid", badge)
