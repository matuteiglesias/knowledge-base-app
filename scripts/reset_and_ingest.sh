#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"
LOGDIR="$ROOT/logs"
INGEST_LOG="$LOGDIR/ingest_log.txt"
API_LOG="$LOGDIR/api_debug_logs.txt"
RUNNER_DIR="$ROOT/pipeline/runner"

# Defaults
export PYTHONPATH="${PYTHONPATH:-$ROOT}"
export CHUNKS_DIR="${CHUNKS_DIR:-$ROOT/store/chunks}"
export PAPERS_DIR="${PAPERS_DIR:-$ROOT/store/papers}"
export CHROMA_DIR="${CHROMA_DIR:-$ROOT/store/chroma}"
export EMBED_CACHE_DB="${EMBED_CACHE_DB:-$ROOT/store/emb_cache.sqlite}"
export SUMMARY_DB="${SUMMARY_DB:-$ROOT/store/summary_jobs.sqlite}"
export CHROMA_COLLECTION="${CHROMA_COLLECTION:-chunks}"
export EMBED_ADAPTER="${EMBED_ADAPTER:-placeholder}"
export EMBED_DIM="${EMBED_DIM:-128}"
export FASTAPI_MODULE="${FASTAPI_MODULE:-backend.app.main:app}"
export FASTAPI_HOST="${FASTAPI_HOST:-0.0.0.0}"
export FASTAPI_PORT="${FASTAPI_PORT:-9000}"
export PYTHON_BIN="${PYTHON_BIN:-python3}"

RESET_RUN="${RESET_RUN:-true}"
DRY_RUN="${DRY_RUN:-false}"

mkdir -p "$LOGDIR"
: > "$INGEST_LOG"
: > "$API_LOG"

echo "[run] ROOT=$ROOT" | tee -a "$INGEST_LOG"
if [[ -f "$ENV_FILE" ]]; then
  echo "[run] loading .env from $ENV_FILE" | tee -a "$INGEST_LOG"
  set -o allexport
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +o allexport
fi

cat >> "$INGEST_LOG" <<EOF
[run] Using env (summary)
  PYTHONPATH=$PYTHONPATH
  CHUNKS_DIR=$CHUNKS_DIR
  PAPERS_DIR=$PAPERS_DIR
  CHROMA_DIR=$CHROMA_DIR
  EMBED_CACHE_DB=$EMBED_CACHE_DB
  CHROMA_COLLECTION=$CHROMA_COLLECTION
  RESET_RUN=$RESET_RUN
  DRY_RUN=$DRY_RUN
EOF

# kill any existing server on port
echo "[run] checking for process listening on :$FASTAPI_PORT" | tee -a "$INGEST_LOG"
if command -v lsof >/dev/null 2>&1; then
  OLD_PID=$(lsof -iTCP:"$FASTAPI_PORT" -sTCP:LISTEN -t || true)
  if [[ -n "$OLD_PID" ]]; then
    echo "[run] killing old FASTAPI pid: $OLD_PID" | tee -a "$INGEST_LOG"
    kill "$OLD_PID" || true
    sleep 0.5
  fi
fi

# # ---------- backup state (move only if RESET_RUN=true) ----------
# BACKUP="$ROOT/.backup_run_$(date -u +%Y%m%dT%H%M%SZ)"
# mkdir -p "$BACKUP"
# echo "[run] backup dir: $BACKUP" | tee -a "$INGEST_LOG"

# TO_BACKUP=( "$EMBED_CACHE_DB" "$CHUNKS_DIR" "$PAPERS_DIR" "$SUMMARY_DB" )

# # If RESET_RUN true, we also rotate the CHROMA_DIR (this avoids accidental deletion)
# if [[ "${RESET_RUN}" = "true" ]]; then
#   TO_BACKUP=( "$CHROMA_DIR" "${TO_BACKUP[@]}" )
#   echo "[run] RESET_RUN=true: CHROMA_DIR will be rotated" | tee -a "$INGEST_LOG"
# else
#   echo "[run] RESET_RUN=false: preserving CHROMA_DIR (no rotation)" | tee -a "$INGEST_LOG"
# fi

# for P in "${TO_BACKUP[@]}"; do
#   if [[ -e "$P" ]]; then
#     echo "[run] mv $P -> $BACKUP/" | tee -a "$INGEST_LOG"
#     mv "$P" "$BACKUP/" || true
#   fi
# done

# # recreate fresh directories
# mkdir -p "$CHUNKS_DIR" "$PAPERS_DIR" "$CHROMA_DIR"

# ---------- TEI ingestion ----------
TEI_RUNNER="$RUNNER_DIR/tei_runner.py"
TEI_IN_DIR="${TEI_IN_DIR:-$ROOT/downloads/data/xmls}"
TEI_OUT_DIR="${TEI_OUT_DIR:-$CHUNKS_DIR}"
PDF_SRC_DIR="${PDF_SRC_DIR:-$ROOT/downloads/data/pdfs}"
MIN_LEN="${MIN_LEN:-50}"

echo "[tei] expecting TEI input dir: $TEI_IN_DIR (PDF source: $PDF_SRC_DIR)" | tee -a "$INGEST_LOG"
mkdir -p "$TEI_IN_DIR"

if [[ -z "$(ls -A "$TEI_IN_DIR" 2>/dev/null || true)" ]]; then
  if [[ -d "$PDF_SRC_DIR" && "$(find "$PDF_SRC_DIR" -maxdepth 1 -type f -name '*.pdf' | wc -l | tr -d ' ')" -gt 0 ]]; then
    echo "[tei] generating TEI from PDFs in $PDF_SRC_DIR" | tee -a "$INGEST_LOG"
    if ! "$PYTHON_BIN" "$ROOT/pipeline/ingestion/grobid_ingest.py" "$PDF_SRC_DIR" --out-tei "$TEI_IN_DIR" --recursive 2>&1 | tee -a "$INGEST_LOG"; then
      echo "[run] grobid_ingest returned nonzero status; continuing (maybe partial TEIs exist)" | tee -a "$INGEST_LOG"
    fi
  else
    echo "[tei] no TEI files and no PDFs found at $PDF_SRC_DIR; skipping grobid step" | tee -a "$INGEST_LOG"
  fi
fi

echo "[tei] parsing TEI input $TEI_IN_DIR -> $TEI_OUT_DIR" | tee -a "$INGEST_LOG"
if [[ -d "$TEI_IN_DIR" ]]; then
  TEI_CMD=( "$PYTHON_BIN" "$TEI_RUNNER" "$TEI_IN_DIR" "$TEI_OUT_DIR" --min-len "$MIN_LEN" )
  if [[ "$DRY_RUN" = "true" ]]; then TEI_CMD+=( --dry-run ); fi
  if [[ "${FORCE_PARSE:-true}" = "true" ]]; then TEI_CMD+=( --force ); fi

  "${TEI_CMD[@]}" 2>&1 | tee -a "$INGEST_LOG" || {
    echo "[run] tei parsing failed" | tee -a "$INGEST_LOG"
    exit 2
  }
else
  echo "[tei] WARNING: TEI input dir not found: $TEI_IN_DIR" | tee -a "$INGEST_LOG"
fi

# count chunk files safely
if [[ -d "$CHUNKS_DIR" ]]; then
  CHUNK_FILES_COUNT=$(find "$CHUNKS_DIR" -maxdepth 1 -type f -name "*_chunks.jsonl" | wc -l | tr -d ' ')
else
  CHUNK_FILES_COUNT=0
fi
echo "[run] chunk files found: $CHUNK_FILES_COUNT" | tee -a "$INGEST_LOG"

# ---------- Embedding + upsert ----------
EMBED_RUNNER="$RUNNER_DIR/embed_runner.py"
echo "[engine] running embedding + upsert into collection '$CHROMA_COLLECTION' (chroma-dir: $CHROMA_DIR)" | tee -a "$INGEST_LOG"

EMBED_CMD=( "$PYTHON_BIN" "$EMBED_RUNNER" --mode bulk --input "$CHUNKS_DIR" --chroma-dir "$CHROMA_DIR" --cache-db "$EMBED_CACHE_DB" --collection "$CHROMA_COLLECTION" --adapter "$EMBED_ADAPTER" --dim "$EMBED_DIM" --batch 64 )
if [[ "${RESET_RUN:-true}" = "true" ]]; then EMBED_CMD+=( --reset ); fi
if [[ "$DRY_RUN" = "true" ]]; then EMBED_CMD+=( --dry-run ); fi

if ! "${EMBED_CMD[@]}" 2>&1 | tee -a "$INGEST_LOG"; then
  echo "[run] embedding/upsert failed (see $INGEST_LOG)" | tee -a "$INGEST_LOG"
  if [[ -f "/tmp/chroma_failed_batch.json" ]]; then
    cp /tmp/chroma_failed_batch.json "$LOGDIR/" || true
    echo "[run] copied /tmp/chroma_failed_batch.json -> $LOGDIR/" | tee -a "$INGEST_LOG"
  fi
  exit 3
fi

# right after embed_runner finishes successfully
python3 - <<'PY' >> "$INGEST_LOG" 2>&1
from shared.chroma_client import get_client
, maybe_persist
from pathlib import Path
c = get_client(persist_directory=Path("${CHROMA_DIR}"))
print("post-run persist attempt:", maybe_persist(c))
PY


# ---------- post-run diagnostics: safe listing + python state-check ----------
echo "[run] post-run listing CHROMA_DIR contents" | tee -a "$INGEST_LOG"
if [[ -d "$CHROMA_DIR" ]]; then
  ls -la "$CHROMA_DIR" | tee -a "$INGEST_LOG" || true
  du -sh "$CHROMA_DIR" 2>/dev/null | tee -a "$INGEST_LOG" || true
else
  echo "[run] CHROMA_DIR missing: $CHROMA_DIR (not fatal)" | tee -a "$INGEST_LOG"
fi

# call a small python diagnostic that:
# - imports shared.check_chroma_state.py (or uses your shared helpers)
# - prints state and tries maybe_persist()
# if [[ -f "$ROOT/shared/check_chroma_state.py" ]]; then
#   echo "[run] running python chroma state check" | tee -a "$INGEST_LOG"
#   "$PYTHON_BIN" "$ROOT/shared/check_chroma_state.py" 2>&1 | sed 's/^/[check_chroma_state] /' | tee -a "$INGEST_LOG" || true
# else
#   echo "[run] no shared/check_chroma_state.py found; skipping python health check" | tee -a "$INGEST_LOG"
# fi

# ---------- start FastAPI ----------
echo "[run] starting FastAPI on :$FASTAPI_PORT (logs -> $API_LOG)" | tee -a "$INGEST_LOG"
nohup "$PYTHON_BIN" -m uvicorn "$FASTAPI_MODULE" --host "$FASTAPI_HOST" --port "$FASTAPI_PORT" --reload >> "$API_LOG" 2>&1 &
sleep 1
echo "[run] uvicorn started (tail $API_LOG to follow logs)" | tee -a "$INGEST_LOG"

echo "[run] done. See $INGEST_LOG and $API_LOG for details." | tee -a "$INGEST_LOG"
exit 0
