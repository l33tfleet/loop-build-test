"""#81: tapping either 'View as' pill switches the chart without moving the Diameter scale's top.

A switch can only move the section's top if something above it changes size, or a script scrolls.
So every rule keyed on a checked radio must style only things after the section's title, and the
script must ignore taps and changes on the pills.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

CSS = Path(__file__).resolve().parents[2] / "static" / "arcade.css"
SCRIPT = Path(__file__).resolve().parents[2] / "static" / "arcade.js"
SECTION = re.compile(r'<section class="diameter-scale".*?</section>', re.DOTALL)


def _checked_selectors(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    for selectors in re.findall(r"([^{}]+)\{[^}]*\}", css):
        for selector in selectors.split(","):
            if "scale-view" in selector and ":checked" in selector:
                yield " ".join(selector.split())


def _subject_classes(selector):
    # The styled element is the last compound; drop any :has(...) and pseudo parts from it.
    last = re.split(r"\s*[ >+~]\s*(?![^(]*\))", selector)[-1]
    last = re.sub(r":[\w-]+(\([^)]*\))?", "", last)
    return re.findall(r"\.([\w-]+)", last)


def test_view_switch_styles_only_what_sits_below_the_scale_title(client):
    page = client.get("/").text
    section = SECTION.search(page)
    title_at = page.index('id="scale-title"')
    inset = re.search(r'<section class="rocky-inset".*?</section>', page, re.DOTALL)
    selectors = list(_checked_selectors(CSS.read_text()))
    assert any("scale-rows" in s for s in selectors), selectors
    for selector in selectors:
        classes = _subject_classes(selector)
        assert classes, selector
        for name in classes:
            hits = [m.start() for m in re.finditer(r'class="(?:[^"]*\s)?' + re.escape(name) + r'[\s"]', page)]
            assert hits, (selector, name)
            for at in hits:
                in_scale = section.start() <= at < section.end() and at > title_at
                in_inset = inset is not None and inset.start() <= at < inset.end() and inset.start() > section.end()
                assert in_scale or in_inset, (selector, name)


HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const log = { scrolled: 0, prevented: 0, fetched: 0 };
const listeners = {};
const node = (props) => Object.assign({
  closest: () => null, contains: () => false, scrollIntoView() { log.scrolled++; }, focus() { log.scrolled++; },
}, props);
const win = {
  location: { href: input.base + "/#scale-title", origin: input.base, pathname: "/", hash: "#scale-title" },
  addEventListener(type, fn) { (listeners["window:" + type] ||= []).push(fn); },
  scrollBy() { log.scrolled++; }, scrollTo() { log.scrolled++; },
};
const document = {
  addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
  getElementById: () => null, querySelector: () => null, querySelectorAll: () => [],
};
const context = vm.createContext({
  window: win, location: win.location, document, history: { pushState() {} }, URL, URLSearchParams,
  fetch() { log.fetched++; return new Promise(() => {}); }, CSS: { escape: (s) => s },
});
vm.runInContext(fs.readFileSync(input.script, "utf8"), context);
for (const id of ["scale-view-bars", "scale-view-circles"]) {
  const radio = node({ id, type: "radio", name: "scale-view", checked: true, form: null });
  const label = node({ tagName: "LABEL", htmlFor: id });
  for (const [type, target] of [["click", label], ["click", radio], ["change", radio]]) {
    const event = { type, button: 0, target, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
    for (const fn of listeners[type] || []) fn(event);
    if (event.defaultPrevented) log.prevented++;
  }
}
process.stdout.write(JSON.stringify(log));
"""


def test_script_leaves_pill_taps_to_the_browser():
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is needed to run the home page script")
    payload = {"base": "http://testserver", "script": str(SCRIPT)}
    out = subprocess.run(
        [node, "-e", HARNESS], input=json.dumps(payload), capture_output=True, text=True, timeout=30, check=False
    )
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == {"scrolled": 0, "prevented": 0, "fetched": 0}
