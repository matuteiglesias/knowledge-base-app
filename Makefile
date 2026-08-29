SHELL := /bin/bash

CORPUS ?= tesislcd
PORT ?= 9000
MAX_FILES ?=
MIN_LEN ?= 50
CHUNK_SET_DIR ?=

DOCTOR_CMD = python3 -m pipeline.adapter.manager doctor --corpus $(CORPUS)
GROBID_CMD = python3 -m pipeline.adapter.manager grobid --corpus $(CORPUS) --recursive $(if $(MAX_FILES),--max-files $(MAX_FILES),)
PARSE_CMD = python3 -m pipeline.adapter.manager parse --corpus $(CORPUS) --min-len $(MIN_LEN) $(if $(CHUNK_SET_DIR),--chunk-set-dir $(CHUNK_SET_DIR),)
VALIDATE_CMD = python3 -m pipeline.adapter.manager doctor --corpus $(CORPUS) --strict --json
EXPORT_REVIEW_CMD = python3 -m backend.exports.export_review_csv --corpus $(CORPUS)
API_CORPUS_CMD = PAPER_KB_CORPUS=$(CORPUS) PAPER_KB_CHUNK_SETS_DIR=corpora/$(CORPUS)/chunk_sets STORAGE_BACKEND=chunk_set uvicorn backend.app.main:app --reload --port $(PORT)

.PHONY: help corpus-doctor corpus-grobid corpus-parse corpus-validate contract-review-record api-corpus export-review frontend-dev kill-port legacy-smoke legacy-run-all legacy-run

help:
	@echo "Operator targets (run from repo root):"
	@echo "  make corpus-doctor CORPUS=tesislcd"
	@echo "  make corpus-grobid CORPUS=tesislcd MAX_FILES=2"
	@echo "  make corpus-parse CORPUS=tesislcd"
	@echo "  make corpus-validate CORPUS=tesislcd"
	@echo "  make contract-review-record"
	@echo "  make api-corpus CORPUS=tesislcd PORT=9000"
	@echo "  make export-review CORPUS=tesislcd"
	@echo "  make frontend-dev"
	@echo "  make kill-port PORT=9000"
	@echo ""
	@echo "Legacy placeholders retained as explicit legacy-* targets."

corpus-doctor:
	echo $(DOCTOR_CMD)
	$(DOCTOR_CMD)

corpus-grobid:
	echo $(GROBID_CMD)
	$(GROBID_CMD)

corpus-parse:
	echo $(PARSE_CMD)
	$(PARSE_CMD)

corpus-validate:
	echo $(VALIDATE_CMD)
	$(VALIDATE_CMD)

contract-review-record:
	python3 tests/test_review_record_contract.py

api-corpus:
	python3 -c "import socket; s=socket.socket(); s.settimeout(0.2); busy=(s.connect_ex(('127.0.0.1', int('$(PORT)')))==0); s.close(); import sys; sys.exit(1 if busy else 0)" || { echo "Port $(PORT) is occupied. Run: make kill-port PORT=$(PORT)"; exit 2; }
	echo $(API_CORPUS_CMD)
	$(API_CORPUS_CMD)

export-review:
	echo $(EXPORT_REVIEW_CMD)
	$(EXPORT_REVIEW_CMD)

frontend-dev:
	echo "cd frontend && NEXT_PUBLIC_API_BASE=http://127.0.0.1:$(PORT) npm run dev"
	cd frontend && NEXT_PUBLIC_API_BASE=http://127.0.0.1:$(PORT) npm run dev

kill-port:
	echo "Killing listeners on port $(PORT)"
	pids=$$(lsof -ti tcp:$(PORT) 2>/dev/null || true); \
	if [ -z "$$pids" ]; then echo "No process is listening on port $(PORT)"; exit 0; fi; \
	echo "kill $$pids"; \
	kill $$pids

legacy-smoke:
	echo "[LEGACY] smoke placeholder removed; use corpus-doctor/corpus-validate instead."
	exit 2

legacy-run-all:
	echo "[LEGACY] run_all placeholder removed; use corpus-grobid + corpus-parse + api-corpus." 
	exit 2

legacy-run: legacy-run-all
