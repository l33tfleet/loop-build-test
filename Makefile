UV ?= uv
BASE_URL ?= http://127.0.0.1:8002

.PHONY: check smoke serve
check:
	$(UV) run ruff check .
	$(UV) run pytest -q

smoke:
	curl -fsS $(BASE_URL)/healthz
	curl -fsS "$(BASE_URL)/convert?value=1&src=km&dst=mi"

serve:
	$(UV) run uvicorn app.main:app --host 127.0.0.1 --port 8002
