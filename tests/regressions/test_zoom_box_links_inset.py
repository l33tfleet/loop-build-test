"""#120: a dashed 'Zoomed below' box around the rocky-planet speck in the circle chart links to the rocky inset."""
import re
from hashlib import sha256
from pathlib import Path

import pytest

BASE = "http://arcade.test"
ROCKY = ["mercury", "venus", "earth", "mars"]


def _css():
    return Path("static/arcade.css").read_text(encoding="utf-8")


def _rules(css, selector):
    return " ".join(re.findall(re.escape(selector) + r"\s*(?:,[^{]*)?\{([^}]*)\}", css))


SECTION = re.compile(r'<section class="diameter-scale"[^>]*>(.*?)</section>', re.DOTALL)
LINK = re.compile(r'<a class="scale-zoom"([^>]*)>(.*?)</a>', re.DOTALL)


def _section(client):
    match = SECTION.search(client.get("/").text)
    assert match, "diameter scale section missing"
    return match.group(1)


def test_zoom_link_is_a_sibling_after_the_circle_list(client):
    section = _section(client)
    links = LINK.findall(section)
    assert len(links) == 1
    attrs, body = links[0]
    assert re.search(r'\bhref="#inset-title"', attrs)
    # Direct child of the section, straight after the circle list closes: not inside the <ol>.
    assert re.search(r'</ol>\s*<a class="scale-zoom"[^>]*>.*?</a>\s*$', section, re.DOTALL)
    assert section.index("</ol>") < section.index('<a class="scale-zoom"')
    assert len(re.findall(r"<li\b", section)) == 8
    assert len(re.findall(r"<label\b", section)) == 2
    text = " ".join(re.sub(r"<[^>]+>", " ", body).split())
    assert text == "Zoomed below ↓"
    # The accessible name is the words only; the arrow is decoration hidden from screen readers.
    assert re.search(r'<span aria-hidden="true">↓</span>', body)
    spoken = re.sub(r'<span aria-hidden="true">[^<]*</span>', "", body)
    assert " ".join(re.sub(r"<[^>]+>", " ", spoken).split()) == "Zoomed below"


def test_inset_target_exists(client):
    html = client.get("/").text
    inset = re.search(r'<section class="rocky-inset"[^>]*>(.*?)</section>', html, re.DOTALL).group(1)
    assert 'id="inset-title"' in inset


def test_zoom_box_is_hidden_in_bars_view_with_both_switches():
    css = _css()
    assert re.search(
        r"\.diameter-scale:has\(#scale-view-bars:checked\) \.scale-zoom,\s*"
        r"#scale-view-bars:checked ~ \.scale-zoom\s*\{\s*display:\s*none;?\s*\}",
        css,
    ), "bars view must hide .scale-zoom"


def test_zoom_box_is_dashed_and_focus_visible():
    css = _css()
    box = _rules(css, ".scale-zoom::before")
    assert re.search(r"border:[^;]*dashed", box)
    assert re.search(r"position:\s*absolute", box) and re.search(r"bottom:\s*0", box)
    assert re.search(r"outline:", _rules(css, ".scale-zoom:focus-visible::before"))
    assert re.search(r"position:\s*relative", _rules(css, ".diameter-scale "))


ZOOM_BLOCK = re.compile(r'\n *<a class="scale-zoom".*?</a>(?=\n)', re.DOTALL)
COUNT_BLOCK = re.compile(r'\n *\n *<div class="duel-count".*?</div>\n *(?=\n)', re.DOTALL)


# Supersedes test_duel_counting_row.py::test_page_is_unchanged_apart_from_the_row: same pages and digests, so
# everything except the duel counting row and the one new zoom link stays byte-for-byte what that test pinned.
@pytest.mark.parametrize(("url", "status", "zooms", "blocks", "digest"), [
    ("/", 200, 1, 1, "8a3828c60cf98b247ef920341a0b49347a756f13e6284047320accb8eefc2d4f"),
    ("/?left=mars&right=neptune", 200, 1, 1, "b40575cda9a95d103dbe420300255d1a58c2367d0cb84c1d1e21ffa20687982b"),
    ("/?left=mars&right=earth", 200, 1, 1, "d2d635e5603c175605df376f27a26f04f69236a513ad6b7c19430ca2399e29ec"),
    ("/?round=1&choice=earth", 200, 1, 1, "0848700c8eef150b43c93e2163d873ba84caba8f011bd05baf2ffbcaacad2465"),
    ("/?left=pluto", 422, 1, 0, "66553c68e4b191a5e080fedb98374bc297b1e9c80fff6d6b2da929f4a7a8adb5"),
])
def test_page_is_unchanged_apart_from_the_row_and_zoom_box(client, url, status, zooms, blocks, digest):
    response = client.get(url)
    assert response.status_code == status
    rest, found_zoom = ZOOM_BLOCK.subn("", response.text)
    assert found_zoom == zooms
    rest, found = COUNT_BLOCK.subn("", rest)
    assert found == blocks
    assert sha256(rest.encode()).hexdigest() == digest


MEASURE = """() => {
  const r = (n) => { const b = n.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
  const link = document.querySelector("a.scale-zoom");
  const before = getComputedStyle(link, "::before");
  const lr = link.getBoundingClientRect();
  const left = lr.left + parseFloat(before.left), w = parseFloat(before.width), h = parseFloat(before.height);
  const box = [left, lr.bottom - h, left + w, lr.bottom];
  const text = link.querySelector(".scale-zoom-text");
  return {
    box, border: before.borderTopStyle, display: getComputedStyle(link).display,
    text: text ? r(text) : null, textVisible: text ? text.checkVisibility() : false,
    frame: r(document.querySelector(".scale-rows")),
    circles: Object.fromEntries([...document.querySelectorAll(".scale-rows .scale-bar")]
      .map((n) => [n.dataset.planet, r(n)])),
    labels: [...document.querySelectorAll(".scale-rows .scale-label")].map(r),
    leaders: [...document.querySelectorAll(".scale-rows .scale-leader")].map(r),
  };
}"""


def _browse(client, width, steps):
    sync_api = pytest.importorskip("playwright.sync_api")

    def serve(route):
        response = client.get(route.request.url[len(BASE):])
        route.fulfill(status=response.status_code, body=response.content,
                      content_type=response.headers.get("content-type"))

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.route("**/*", serve)
            page.goto(f"{BASE}/#scale-title")
            return steps(page)
        finally:
            browser.close()


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


@pytest.mark.parametrize("width", [390, 1024])
def test_box_encloses_rocky_circles_without_moving_anything(client, width):
    def steps(page):
        got = page.evaluate(MEASURE)
        page.evaluate("() => document.querySelector('a.scale-zoom').remove()")
        got["without"] = page.evaluate("""() => {
          const r = (n) => { const b = n.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
          return {
            circles: Object.fromEntries([...document.querySelectorAll(".scale-rows .scale-bar")]
              .map((n) => [n.dataset.planet, r(n)])),
            labels: [...document.querySelectorAll(".scale-rows .scale-label")].map(r),
            leaders: [...document.querySelectorAll(".scale-rows .scale-leader")].map(r),
          };
        }""")
        return got

    got = _browse(client, width, steps)
    assert got["border"] == "dashed"
    box = got["box"]
    assert box[3] == pytest.approx(got["frame"][3], abs=0.5), "box sits on the chart's baseline"
    for name in ROCKY:
        c = got["circles"][name]
        assert box[0] <= c[0] and c[2] <= box[2] and box[1] <= c[1] and c[3] <= box[3] + 0.5, name
    for name, c in got["circles"].items():
        if name not in ROCKY:
            assert c[2] - c[0] > box[2] - box[0], f"{name} should be bigger than the box"
    assert got["textVisible"]
    text = got["text"]
    assert text[2] <= box[0] and text[0] >= got["frame"][0] - 0.5, "label sits left of the box, inside the frame"
    assert not any(_overlap(text, label) for label in got["labels"]), "label must not cover planet labels"
    for key in ("circles", "labels", "leaders"):
        assert got[key] == got["without"][key], f"{key} moved when the box was added"


def test_box_hidden_in_bar_graph_view(client):
    def steps(page):
        page.click("label[for=scale-view-bars]")
        assert page.is_checked("#scale-view-bars")
        return page.evaluate("() => getComputedStyle(document.querySelector('a.scale-zoom')).display")

    assert _browse(client, 1024, steps) == "none"


def test_label_is_a_keyboard_reachable_link_to_the_inset(client):
    def steps(page):
        link = page.locator("a.scale-zoom")
        link.focus()
        focused = page.evaluate("() => document.activeElement.matches('a.scale-zoom')")
        outline = page.evaluate(
            "() => getComputedStyle(document.querySelector('a.scale-zoom'), '::before').outlineStyle")
        name = page.get_by_role("link", name="Zoomed below", exact=True).count()
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)
        return focused, outline, name, page.evaluate("() => location.hash")

    focused, outline, name, hash_ = _browse(client, 1024, steps)
    assert focused and outline != "none"
    assert name == 1
    assert hash_ == "#inset-title"
