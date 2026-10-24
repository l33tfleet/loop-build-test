import re

TRY_LINK = re.compile(r'<a\b[^>]*class="birthday-try"[^>]*>([^<]*)</a>')
RESULT = re.compile(r'<li class="birthday-result"[^>]*>\s*<span>([^<]+)</span>\s*<strong>([0-9]+\.[0-9])</strong>')


def _booth(html):
    return re.search(r'<section class="birthday-booth".*?</section>', html, re.DOTALL).group()


def test_booth_offers_try_age_ten_link_after_submit_button(client):
    booth = _booth(client.get("/").text)
    link = TRY_LINK.search(booth)
    assert link, "no 'try age 10' link in the birthday booth"
    assert 'href="/?age=10"' in link.group()
    assert link.group(1).strip() == "or try age 10"
    assert "tabindex=\"-1\"" not in link.group()
    assert booth.index("Find my planet ages") < link.start()


def test_link_has_visible_focus_style_and_wraps(client):
    css = client.get("/static/arcade.css").text
    focus = re.search(r"\.birthday-try:focus-visible\s*\{([^}]*)\}", css)
    assert focus and re.search(r"outline:\s*\d+px solid", focus.group(1))
    rule = re.search(r"(?<![-\w:])\.birthday-try\s*\{([^}]*)\}", css)
    assert rule, "no base .birthday-try rule"
    assert "nowrap" not in rule.group(1)
    assert "overflow-wrap: anywhere" in rule.group(1) or "display: inline-block" in rule.group(1)
