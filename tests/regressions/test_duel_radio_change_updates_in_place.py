"""#62: tapping a duel radio updates the portraits and ratio right away, without pressing Compare.

Reuses the Node harness from test_controls_run_in_place.py and adds one step: change a radio in a form,
which the script should turn into a submit through the form's requestSubmit().
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

_HOOK = '    } else if (step.do === "respond") {'
assert _HOOK in _base.HARNESS
HARNESS = _base.HARNESS.replace(_HOOK, """    } else if (step.do === "change") {
      // A tapped radio: its form lists the fields as they are after the tap.
      const region = regionNamed(step.region);
      const form = control(region, { action: input.base + "/", method: "get", fields: step.fields, className: step.formClass,
        requestSubmit() { log.requested = (log.requested || 0) + 1; dispatch("submit", { target: form, submitter: null }); } });
      const inner = form.closest;
      form.closest = (sel) => (sel === "." + step.formClass ? form : inner.call(form, sel));
      const radio = control(region, { type: step.type || "radio", name: step.radio[0], value: step.radio[1], checked: true, form });
      const outer = radio.closest;
      radio.closest = (sel) => (sel === "." + step.formClass ? form : outer.call(radio, sel));
      dispatch("change", { target: radio });
""" + _HOOK, 1)


def run(client, steps, responses, start="/"):
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is needed to run the home page script")
    payload = {
        "base": BASE,
        "script": str(SCRIPT),
        "page": client.get(start).text,
        "responses": {path: client.get(path).text for path in responses},
        "steps": steps,
    }
    out = subprocess.run(
        [node, "-e", HARNESS], input=json.dumps(payload), capture_output=True, text=True, timeout=30, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def ratio(html):
    match = re.search(r'<p class="duel-ratio" aria-live="polite">(.*?)</p>', html, re.DOTALL)
    assert match, html
    return text(match.group(1)).strip()


def change(side, slug, left, right):
    return {"do": "change", "region": "planet-duel", "formClass": "duel-form",
            "fields": [["left", left], ["right", right]], "radio": [side, slug]}


def test_change_on_a_non_radio_does_not_submit(client):
    step = change("left", "saturn", "saturn", "mercury")
    step["type"] = "text"
    log = run(client, [step], [])
    assert log.get("requested") is None
    assert log["fetched"] == []
