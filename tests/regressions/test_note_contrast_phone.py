"""#130: explanatory notes use the body --ink colour (or brighter) and reach 16px on phones."""
import re

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
