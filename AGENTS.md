# loop-build-test

A toy unit-converter app used to exercise an autonomous build loop: writer, reviewer, merge window and deploy.

- Stack: FastAPI, run with uv. `make check` (ruff + pytest) must pass before you commit.
- App code lives in `app/`. New regression tests go in `tests/regressions/` as new files; never edit existing ones.
- Keep changes small. Don't touch `tests/conftest.py`, `.github/`, `Makefile` or `pyproject.toml` unless the issue says so.
