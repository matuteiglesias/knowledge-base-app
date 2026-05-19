
# Auto-generated stub Makefile.
# Purpose: provide a stable interface for portfolio governance.
# Replace placeholder targets with real commands when ready.


PYTHONPATH=/home/matias/Documents/KB.


PROJECT := $(notdir $(CURDIR))

.PHONY: help smoke smoke-chunk-set api-chunk-set run run_all

help:
	@echo "Project: $(PROJECT)"
	@echo ""
	@echo "Targets:"
	@echo "  make smoke    - cheap, offline, bounded checks (placeholder by default)"
	@echo "  make run_all  - full run pipeline (placeholder by default)"
	@echo "  make run      - alias for run_all"

smoke:
	@echo "[SMOKE][$(PROJECT)] not implemented"
	@echo "Define a minimal, offline, fixture-driven smoke check."
	@exit 2

run_all:
	@echo "[RUN_ALL][$(PROJECT)] not implemented"
	@echo "Define the full run (may require network, secrets, longer compute)."
	@exit 2

run: run_all




api-chunk-set:
	PAPER_KB_CHUNK_SETS_DIR=$${PAPER_KB_CHUNK_SETS_DIR:-artifacts/chunk_sets} \
	STORAGE_BACKEND=chunk_set \
	uvicorn backend.app.main:app --reload --port 9000

smoke-chunk-set:
	BASE_URL=$${BASE_URL:-http://127.0.0.1:9000} ./scripts/poke_api_chunk_set.sh
