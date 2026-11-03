"""#130: explanatory notes use the body --ink colour (or brighter) and reach 16px on phones."""
import re
from html.parser import HTMLParser

import pytest

NOTES = [".duel-scale-note", ".scale-note", ".inset-note", ".quiz-scale-note", ".shelf-note", ".tagline", ".source"]
PHONE = re.compile(r"@media\s*\(max-width:\s*420px\)\s*\{(.*?)\n\}", re.DOTALL)
BASE = "http://testserver"
# Pages that between them render every note class.
PAGES = ["/", "/?a=earth&b=mars", "/?set=0&round=1&score=0&choice=earth"]


def _css(client):
    return client.get("/static/arcade.css").text


def _hex(css, name):
    return re.search(r":root\s*\{[^}]*" + re.escape(name) + r":\s*#([0-9a-fA-F]{6})", css).group(1)


def _luminance(hex6):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(int(hex6[i:i + 2], 16)) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _decls(css, selector):
    """Declarations of every top-level rule whose selector list names `selector` exactly."""
    out = []
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", PHONE.sub("", css)):
        if selector in [s.strip() for s in sel.split(",")]:
            out.append(body)
    return " ".join(out)


def _last(decls, prop):
    found = re.findall(r"(?<![-\w])" + prop + r":\s*([^;}]+)", decls)
    return found[-1].strip() if found else None


@pytest.mark.parametrize("selector", NOTES)
def test_note_colour_is_at_least_as_bright_as_ink(client, selector):
    css = _css(client)
    colour = _last(_decls(css, selector), "color")
    assert colour and colour != "var(--muted)", (selector, colour)
    var = re.fullmatch(r"var\((--[\w-]+)\)", colour)
    assert var, (selector, colour)
    navy, ink = _hex(css, "--navy"), _hex(css, "--ink")
    assert _contrast(_hex(css, var.group(1)), navy) >= _contrast(ink, navy), (selector, colour)


@pytest.mark.parametrize("selector", NOTES)
def test_note_is_at_least_1rem_under_phone_query(client, selector):
    css = _css(client)
    base_at = [m.start() for m in re.finditer(r"(?:^|[,}])\s*" + re.escape(selector) + r"\s*[,{]", PHONE.sub(
        lambda m: " " * len(m.group(0)), css))]
    base = re.findall(r"font-size:\s*([\d.]+)rem", _decls(css, selector))
    size = float(base[-1]) if base else 1.0
    for block in PHONE.finditer(css):
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", block.group(1)):
            sizes = re.findall(r"font-size:\s*([\d.]+)rem", body)
            if sizes and selector in [s.strip() for s in sel.split(",")]:
                # Equal specificity: the phone rule only wins if it comes after the base rule.
                assert block.start() > max(base_at, default=-1), (selector, "phone rule precedes base rule")
                size = float(sizes[-1])
    assert size >= 1.0, (selector, size)


def test_chart_labels_inside_circles_unchanged(client):
    css = _css(client)
    for block in PHONE.finditer(css):
        assert not re.search(r"\.(scale|inset)-label", block.group(1))
    assert re.search(r"font-size:\s*0\.875rem", _decls(css, ".scale-label"))
    assert re.search(r"font-size:\s*0\.875rem", _decls(css, ".inset-label"))
    assert _last(_decls(css, ".inset-name"), "color") == "var(--paper)"
    for selector in (".scale-label", ".inset-label"):
        assert _last(_decls(css, selector), "color") is None, selector


VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"})


class _NoteBackdrops(HTMLParser):
    """For each note element, the classes of it and its ancestors, innermost first."""

    def __init__(self):
        super().__init__()
        self.stack, self.found = [], []

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get("class") or "").split()
        if tag in VOID:
            return
        self.stack.append(classes)
        for selector in NOTES:
            if selector[1:] in classes:
                self.found.append((selector, [c for level in reversed(self.stack) for c in level]))

    def handle_endtag(self, tag):
        if tag not in VOID and self.stack:
            self.stack.pop()


def _colour(css, value):
    var = re.fullmatch(r"var\((--[\w-]+)\)", value.strip())
    if var:
        return _hex(css, var.group(1))
    plain = re.fullmatch(r"#([0-9a-fA-F]{6})", value.strip())
    return plain.group(1) if plain else None


def test_offline_axe_color_contrast_for_notes(client):
    """axe's color-contrast rule (WCAG AA, 4.5:1 for normal text) for every rendered note.

    axe-core is not installed and tests run offline, so this applies the same check from the
    stylesheet: each note's text colour against the nearest ancestor panel's solid background.
    """
    css = _css(client)
    checked = set()
    for path in PAGES:
        parser = _NoteBackdrops()
        parser.feed(client.get(path).text)
        for selector, ancestry in parser.found:
            fg = _colour(css, _last(_decls(css, selector), "color") or "var(--ink)")
            bg = _hex(css, "--navy")  # body background
            for cls in ancestry:
                found = _last(_decls(css, "." + cls), "background")
                if found and _colour(css, found):
                    bg = _colour(css, found)
                    break
            assert fg, selector
            assert _contrast(fg, bg) >= 4.5, (path, selector, fg, bg, round(_contrast(fg, bg), 2))
            checked.add(selector)
    assert checked == set(NOTES), set(NOTES) - checked


def _computed(client, width):
    sync_api = pytest.importorskip("playwright.sync_api")

    def serve(route):
        response = client.get(route.request.url[len(BASE):])
        route.fulfill(status=response.status_code, body=response.content,
                      content_type=response.headers.get("content-type"))

    seen = {}
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": width, "height": 800})
            page.route("**/*", serve)
            for path in PAGES:
                page.goto(BASE + path)
                for selector in NOTES:
                    got = page.evaluate(
                        """s => [...document.querySelectorAll(s)].map(e => {
                               const c = getComputedStyle(e); return [c.fontSize, c.color]; })""", selector)
                    seen.setdefault(selector, []).extend(got)
                ink = page.evaluate("""() => { const p = document.createElement('p');
                    p.style.color = 'var(--ink)'; document.body.append(p);
                    const c = getComputedStyle(p).color; p.remove(); return c; }""")
        finally:
            browser.close()
    return seen, ink


def _rgb_hex(rgb):
    return "".join(f"{int(n):02x}" for n in re.findall(r"\d+", rgb)[:3])


def test_notes_compute_to_16px_and_ink_contrast_on_a_phone(client):
    css = _css(client)
    navy = _hex(css, "--navy")
    seen, ink = _computed(client, 390)
    for selector in NOTES:
        assert seen[selector], f"{selector} not rendered on {PAGES}"
        for size, colour in seen[selector]:
            assert float(size.rstrip("px")) >= 16, (selector, size)
            assert _contrast(_rgb_hex(colour), navy) >= _contrast(_rgb_hex(ink), navy), (selector, colour)
