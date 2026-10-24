# Solar Arcade

A toy planet playground used to exercise an autonomous build loop: writer, reviewer, merge window and deploy.

- Stack: FastAPI with Jinja templates, run with uv. `make check` (ruff + pytest) must pass before you commit.
- App code lives in `app/`, pages in `templates/`, CSS and assets in `static/`, data in `data/`, notes in `docs/`.
- Keep `/healthz` and `/convert` working: they anchor the smoke test.
- New regression tests go in `tests/regressions/` as new, uniquely named files; never edit existing ones.
- Tests run offline: no network calls. Use local CSS and assets only (no CDNs, external fonts or chart libraries).
- Keep changes small. Don't touch `tests/conftest.py`, `.github/`, `Makefile` or `pyproject.toml` unless the issue says so.
