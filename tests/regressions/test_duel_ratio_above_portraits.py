import os
import re
import socket
import threading
import time
from pathlib import Path

import pytest

NOTE = "Drawn to scale for this pair only: the larger planet always fills the same circle."
BUTTON = '<button type="submit">Compare</button>'


def duel(html):
    match = re.search(r'<section class="planet-duel"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "duel panel missing"
    return match.group(1)


@pytest.mark.parametrize(("left", "right", "sentence"), [
    ("saturn", "mercury", "Saturn is <strong>24.7</strong> times as wide as Mercury."),
    ("mercury", "saturn", "Saturn is <strong>24.7</strong> times as wide as Mercury."),
    ("earth", "earth", "Both picks are Earth, so they are <strong>exactly the same size</strong>."),
])
def test_ratio_sits_right_under_compare_and_caption_under_portraits(client, left, right, sentence):
    section = duel(client.get("/", params={"left": left, "right": right}).text)
    button = section.index(BUTTON)
    ratio = section.index('<p class="duel-ratio" aria-live="polite">')
    portraits = section.index('<div class="duel-portraits">')
    note = section.index(f'<p class="duel-scale-note">{NOTE}</p>')
    assert button < ratio < portraits < note
    assert section[button + len(BUTTON):ratio].strip() == "</form>"
    assert sentence in section[ratio:portraits]
    assert section.count('class="duel-ratio"') == 1
    assert section.count("duel-scale-note") == 1
    closing = section.rindex("</div>", portraits, note)
    assert section[closing + len("</div>"):note].strip() == ""


def test_error_path_has_no_ratio_or_caption(client):
    section = duel(client.get("/", params={"left": "pluto", "right": "earth"}).text)
    assert 'id="duel-error"' in section
    assert "duel-ratio" not in section
    assert "duel-scale-note" not in section


def test_scale_note_styled_like_quiz_note():
    css = Path("static/arcade.css").read_text(encoding="utf-8")
    quiz = re.search(r"\.quiz-scale-note \{([^}]*)\}", css).group(1)
    note = re.search(r"\.duel-scale-note \{([^}]*)\}", css)
    assert note, ".duel-scale-note rule missing"
    for decl in ("color: var(--muted)", "font-size: 0.9rem"):
        assert decl in quiz and decl in note.group(1)


browser_only = pytest.mark.skipif(
    not os.environ.get("ARCADE_BROWSER_TESTS"),
    reason="set ARCADE_BROWSER_TESTS=1 with a launchable Chromium to measure the ratio on screen",
)


@pytest.fixture(scope="module")
def base_url():
    import uvicorn

    from app.main import app

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@browser_only
@pytest.mark.parametrize(("width", "height", "javascript"), [(390, 844, True), (1280, 800, True), (390, 844, False)])
def test_ratio_fully_visible_after_compare(base_url, width, height, javascript):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": height}, java_script_enabled=javascript)
        page = context.new_page()
        page.goto(base_url + "/")
        page.check("#duel-left-saturn")
        page.check("#duel-right-mercury")
        page.click(".duel-form button[type=submit]")
        page.locator(".duel-ratio", has_text="as wide as Mercury").wait_for()
        page.wait_for_timeout(300)
        box = page.locator(".duel-ratio").bounding_box()
        button = page.locator(".duel-form button[type=submit]").bounding_box()
        scroll = page.evaluate("window.scrollY")
        print(f"{width}x{height} js={javascript} scrollY={scroll} ratio={box} button={button}")
        browser.close()
    top = box["y"] + scroll
    assert top >= button["y"] + scroll + button["height"]
    assert top + box["height"] <= height, (box, scroll, height)
