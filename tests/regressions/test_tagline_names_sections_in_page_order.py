import re
from html import unescape

from tests.regressions.test_tagline_says_what_page_is_for import _lines, _tagline

HEADER = re.compile(r"<header>(.*?)</header>", re.DOTALL)
VIEWPORT = 390
BODY_PAD = 16
# Tagline keyword -> heading id of the section it names, in page order.
SECTIONS = (("duel", "duel-title"), ("quiz", "quiz-title"),
            ("birthday", "birthday-title"), ("scale", "scale-title"))


def test_tagline_names_duel_quiz_birthdays_and_scale_in_page_order(client):
    page = client.get("/").text
    lower = _tagline(client).lower()
    spots = [lower.find(word) for word, _ in SECTIONS]
    assert all(spot >= 0 for spot in spots), lower
    assert spots == sorted(spots), lower
    headings = [page.find(f'id="{anchor}"') for _, anchor in SECTIONS]
    assert all(spot >= 0 for spot in headings)
    assert headings == sorted(headings)


def test_tagline_only_names_features_on_the_page(client):
    page = client.get("/").text
    lower = _tagline(client).lower()
    for absent in ("game", "play", "score", "arcade", "pocket-sized"):
        assert absent not in lower
    assert "Bar graph" in page
    if "rocky" in lower:
        assert 'class="rocky-inset"' in page
