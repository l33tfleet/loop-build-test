import re
from html import unescape

HEADER = re.compile(r"<header>(.*?)</header>", re.DOTALL)
TAGLINE = re.compile(r'<p class="tagline">(.*?)</p>', re.DOTALL)
VIEWPORT = 390
BODY_PAD = 16  # px each side, body padding
FONT = 16  # px, body font-size; .tagline inherits it
# Helvetica/Arial advance widths in 1/1000 em; system-ui faces run a little wider, so FUDGE adds headroom.
WIDTHS = dict(zip("abcdefghijklmnopqrstuvwxyz",
                  [556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833,
                   556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500]))
WIDTHS |= dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                   [667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833,
                    722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611]))
WIDTHS |= {d: 556 for d in "0123456789"} | {" ": 278, ",": 278, ".": 278, "-": 333, "?": 556, "'": 191}
FUDGE = 1.08


def _tagline(client):
    header = HEADER.search(client.get("/").text).group(1)
    assert 'data-marker="solar-arcade"' in header
    match = TAGLINE.search(header)
    assert match, "no tagline under the title"
    return " ".join(unescape(match.group(1)).split())


def _lines(text, width):
    """Greedy word wrap with estimated glyph widths; returns the line count."""
    space = WIDTHS[" "] * FONT / 1000 * FUDGE
    lines, used = 1, 0.0
    for word in text.split():
        w = sum(WIDTHS.get(c, 1000) for c in word) * FONT / 1000 * FUDGE
        if used and used + space + w > width:
            lines, used = lines + 1, w
        else:
            used += (space if used else 0) + w
    return lines


def test_tagline_is_one_sentence_about_size_and_view_toggle(client):
    text = _tagline(client)
    assert "pocket-sized" not in text.lower()
    # One sentence: a single terminal mark, at the end.
    assert len(re.findall(r"[.!?]", text)) == 1 and text[-1] in ".!?"
    lower = text.lower()
    assert "eight" in lower and ("size" in lower or "how big" in lower)
    assert "bar graph" in lower  # the "View as" toggle's second option


def test_tagline_wraps_to_at_most_three_lines_on_a_phone(client):
    assert _lines(_tagline(client), VIEWPORT - 2 * BODY_PAD) <= 3
