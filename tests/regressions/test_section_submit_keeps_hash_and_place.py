"""#105: submitting a section's form keeps the URL hash and scroll position, and the result shows in that section.

Reuses the Node harness from test_controls_run_in_place.py, starting from a page whose URL carries the hash the
section nav sets (/#duel-title), so a submit that drops or swaps the hash is caught.
"""
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "controls_run_in_place", Path(__file__).with_name("test_controls_run_in_place.py")
)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
BASE, SCRIPT, text = _base.BASE, _base.SCRIPT, _base.text

HASH = "#duel-title"
_LOCATION = 'location: { href: input.base + "/", origin: input.base,'
assert _LOCATION in _base.HARNESS
HARNESS = _base.HARNESS.replace(
    _LOCATION, 'location: { href: input.base + "/" + input.hash, hash: input.hash, origin: input.base,', 1
)


def run(client, steps, responses):
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is needed to run the home page script")
    payload = {
        "base": BASE,
        "hash": HASH,
        "script": str(SCRIPT),
        "page": client.get("/").text,
        "responses": {path: client.get(path).text for path in responses},
        "steps": steps,
    }
    out = subprocess.run(
        [node, "-e", HARNESS], input=json.dumps(payload), capture_output=True, text=True, timeout=30, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def ratio(html):
    match = re.search(r'<p class="duel-ratio"[^>]*>(.*?)</p>', html, re.DOTALL)
    return text(match.group(1)).strip() if match else ""


# (form's region, fields, submitter, fetched path, region the result renders in, check on that region's HTML)
CASES = {
    "duel-compare": (
        "planet-duel", [["left", "jupiter"], ["right", "mercury"]], None, "/?left=jupiter&right=mercury",
        "planet-duel", lambda html: "Jupiter" in ratio(html) and "Mercury" in ratio(html),
    ),
    "quiz-choice": (
        "planet-quiz", [["round", "1"]], ["choice", "jupiter"], "/?round=1&choice=jupiter",
        "planet-quiz", lambda html: "Correct" in text(html),
    ),
    "birthday-age": (
        "birthday-booth", [["sort", "order"], ["age", "10"]], None, "/?sort=order&age=10",
        "birthday-booth", lambda html: "10" in text(html),
    ),
    "shelf-sort": (
        "shelf-sort", [["sort", "diameter"]], None, "/?sort=diameter",
        "planet-shelf", lambda html: "Largest diameter first" in text(html),
    ),
}


@pytest.mark.parametrize("case", list(CASES))
def test_section_submit_keeps_hash_scroll_and_section(client, case):
    region, fields, submitter, path, result_region, shows_result = CASES[case]
    home = run(client, [], [])["regions"][result_region]
    step = {"do": "submit", "region": region, "fields": fields}
    if submitter:
        step["submitter"] = submitter
    log = run(client, [
        {"do": "scrollTo", "y": 600},
        {"do": "measure", "region": region, "as": "before"},
        step,
        {"do": "respond"},
        {"do": "measure", "region": region, "as": "after"},
    ], [path])
    assert log["prevented"] == [True]
    assert log["navigated"] == []
    assert log["fetched"] == [path]
    assert log["pushed"] == [BASE + path + HASH]
    # The tapped section stays where it was on screen; any scroll only undoes a height change above it.
    assert log["after"] == log["before"]
    assert log["scrollY"] == 600 + sum(log["scrolls"])
    assert len(log["scrolls"]) == 1
    assert log["regions"][result_region] != home
    assert shows_result(log["regions"][result_region])
