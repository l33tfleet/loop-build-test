"""#81: in a real browser at 390px, the View as pills and the tagline's "bar graph" switch the chart in place.

Runs the app on a local port and taps with a touch-enabled Chromium. Skips when Playwright or a
launchable Chromium is not available (make check does not install either).
"""
import socket
import threading
import time

import pytest
import uvicorn

from app.main import app

TOP = "document.getElementById('scale-title').getBoundingClientRect().top"
STATE = """() => ({
  bars: document.getElementById('scale-view-bars').checked,
  circles: document.getElementById('scale-view-circles').checked,
  barsNote: getComputedStyle(document.querySelector('.scale-note[data-view="bars"]')).display,
  circlesNote: getComputedStyle(document.querySelector('.scale-note[data-view="circles"]')).display,
  rows: getComputedStyle(document.querySelector('.scale-rows')).display,
  barHeights: [...document.querySelectorAll('.scale-bar')].map(b => b.getBoundingClientRect().height),
  scrollY: window.scrollY,
})"""


@pytest.fixture(scope="module")
def base_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def phone(base_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except sync_api.Error as error:  # missing browser or its system libraries
            pytest.skip(f"Chromium cannot start here: {str(error).splitlines()[0]}")
        context = browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=3
        )
        page = context.new_page()
        yield page
        browser.close()


def _settle(page):
    page.wait_for_timeout(300)


def test_pills_switch_the_chart_without_moving_the_scale_top(phone, base_url):
    phone.goto(f"{base_url}/#scale-title")
    _settle(phone)
    start = phone.evaluate(TOP)
    assert phone.evaluate(STATE)["circles"]

    phone.tap("label[for=scale-view-bars]")
    _settle(phone)
    state = phone.evaluate(STATE)
    assert state["bars"] and not state["circles"], state
    assert state["barsNote"] == "block" and state["circlesNote"] == "none", state
    assert state["rows"] == "grid", state
    assert len(state["barHeights"]) == 8 and all(h > 0 for h in state["barHeights"]), state
    assert abs(phone.evaluate(TOP) - start) < 3, (start, phone.evaluate(TOP), state)

    phone.tap("label[for=scale-view-circles]")
    _settle(phone)
    state = phone.evaluate(STATE)
    assert state["circles"] and not state["bars"], state
    assert state["circlesNote"] == "block" and state["barsNote"] == "none", state
    assert state["rows"] == "block", state
    assert abs(phone.evaluate(TOP) - start) < 3, (start, phone.evaluate(TOP), state)


def test_tagline_bar_graph_jumps_to_the_scale_with_bars_showing(phone, base_url):
    phone.goto(f"{base_url}/")
    _settle(phone)
    assert phone.evaluate("window.scrollY") == 0
    phone.tap(".tagline a")
    _settle(phone)
    state = phone.evaluate(STATE)
    assert phone.url.endswith("#scale-title"), phone.url
    assert state["bars"] and state["barsNote"] == "block" and state["rows"] == "grid", state
    assert state["scrollY"] > 0, state
    assert abs(phone.evaluate(TOP)) < 3, phone.evaluate(TOP)
