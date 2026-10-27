"""#68: once a round is answered the two answer buttons lock, the pick is marked, and a miss reads "Not quite"."""
import re

PAIRS = [
    (1, "jupiter", 142984, "earth", 12756, "jupiter"),
    (2, "mercury", 4879, "mars", 6792, "mars"),
    (3, "neptune", 49528, "uranus", 51118, "uranus"),
]


def quiz(response):
    match = re.search(r'<section class="planet-quiz"[^>]*>(.*?)</section>', response.text, re.DOTALL)
    assert match, "Quiz panel missing"
    return match.group(1)


def buttons(panel):
    form = re.search(r"<form\b.*?</form>", panel, re.DOTALL)
    assert form, "Quiz form missing"
    return re.findall(r"<button\b([^>]*)>(.*?)</button>", form.group(0), re.DOTALL)


def test_answered_round_disables_both_buttons_and_marks_earth(client):
    panel = quiz(client.get("/?round=1&choice=earth"))
    found = buttons(panel)
    assert len(found) == 2
    for attrs, _ in found:
        assert re.search(r"\bdisabled\b", attrs)
    (jupiter_attrs, jupiter_body), (earth_attrs, earth_body) = found
    assert 'value="jupiter"' in jupiter_attrs and 'value="earth"' in earth_attrs
    assert 'aria-pressed="true"' in earth_attrs
    assert 'aria-pressed="false"' in jupiter_attrs
    assert "Your pick" in earth_body and "Your pick" not in jupiter_body
    assert "Earth" in earth_body


def test_unanswered_round_keeps_both_buttons_enabled(client):
    found = buttons(quiz(client.get("/?round=1")))
    assert len(found) == 2
    for attrs, body in found:
        assert "disabled" not in attrs
        assert "aria-pressed" not in attrs
        assert "Your pick" not in body

