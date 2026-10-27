"""Home page sections, discovered by convention.

Each `NN_name.py` module here exposes `context(state) -> dict` and renders with
`templates/sections/NN-name.html`; sections appear on the page in filename order.
A context may set `status_code` to ask for a non-200 response. Sections never import each other.
A new section also needs a nav link and a tagline mention in `templates/index.html`.
"""
import importlib
import pkgutil
import sys
from collections.abc import Callable
from typing import NamedTuple


class Section(NamedTuple):
    template: str
    context: Callable[[dict], dict]


def discover(package=None) -> list[Section]:
    """Every section module in the package, in filename order; names starting with _ are helpers."""
    package = package or sys.modules[__name__]
    names = sorted({m.name for m in pkgutil.iter_modules(package.__path__) if not m.name.startswith("_")})
    return [Section(f"sections/{name.replace('_', '-')}.html",
                    importlib.import_module(f"{package.__name__}.{name}").context)
            for name in names]
