#!/usr/bin/env bash
set -euo pipefail
# scripts/regen_docs.sh
#
# Regenerate OpenAPI + ReDoc HTML and pdoc code docs and serve them.
# Usage: from project root:
#   ./scripts/regen_docs.sh
#
# Notes:
# - Assumes uvicorn and pdoc are available in the active Python env.
# - Will use npx redoc-cli (preferred) or a globally installed redoc-cli.
# - Adjust CHROMA_DIR / CHROMA_COLLECTION if you use different paths.
# - Kills uvicorn instances started with the exact command pattern used here.
#

ROOT="$(pwd)"
UVICORN_PID_FILE="$ROOT/.uvicorn.pid"
PYDOC_PID_FILE="$ROOT/.pydoc.pid"
UVICORN_LOG="$ROOT/logs/uvicorn_regen_docs.log"
OPENAPI_JSON="$ROOT/openapi.json"
API_DOCS_HTML="$ROOT/api-docs.html"
PYDOC_DIR="$ROOT/pydoc"
PDOC_MODULES="backend pipeline shared"

# env defaults (change if needed)
: "${CHROMA_DIR:=./store/chroma}"
: "${CHROMA_COLLECTION:=chunks}"
: "${UVICORN_PORT:=9000}"
: "${PYDOC_PORT:=8000}"

echo "=== regen_docs.sh ==="
echo "ROOT = $ROOT"
echo "CHROMA_DIR = $CHROMA_DIR"
echo "CHROMA_COLLECTION = $CHROMA_COLLECTION"
echo "UVICORN_PORT = $UVICORN_PORT"
echo "PYDOC_DIR = $PYDOC_DIR"
echo

# helper: ensure logs dir exists
mkdir -p "$ROOT/logs"

# 1) stop any previous uvicorn (best-effort)
echo "> stopping previous uvicorn (pkill -f 'uvicorn backend.app.main:app')..."
if pgrep -f "uvicorn backend.app.main:app" >/dev/null 2>&1; then
  pkill -f "uvicorn backend.app.main:app" || true
  sleep 0.5
fi
if [ -f "$UVICORN_PID_FILE" ]; then
  OLDPID="$(cat "$UVICORN_PID_FILE" || true)"
  if [ -n "$OLDPID" ] && kill -0 "$OLDPID" >/dev/null 2>&1; then
    echo "Killing uvicorn pid $OLDPID"
    kill "$OLDPID" || true
    sleep 0.3
  fi
  rm -f "$UVICORN_PID_FILE"
fi

# 2) start uvicorn in background (no --reload for this short run)
echo "> starting uvicorn (background) and logging to $UVICORN_LOG ..."
# run with specified env vars so app sees the same runtime config
# note: running without --reload is more predictable for PID management
CHROMA_DIR="$CHROMA_DIR" CHROMA_COLLECTION="$CHROMA_COLLECTION" \
  uvicorn backend.app.main:app --host 127.0.0.1 --port "$UVICORN_PORT" > "$UVICORN_LOG" 2>&1 &

UVC_PID=$!
echo "$UVC_PID" > "$UVICORN_PID_FILE"
echo "uvicorn started (pid $UVC_PID). Waiting for /openapi.json..."

# 3) wait for openapi.json to be available (timeout)
MAX_WAIT=25  # seconds
SLEEP=1
i=0
while true; do
  if curl -sSf --max-time 3 "http://127.0.0.1:${UVICORN_PORT}/openapi.json" -o "$OPENAPI_JSON"; then
    echo "> got openapi.json (saved to $OPENAPI_JSON)"
    break
  fi
  i=$((i+1))
  if [ $i -ge $MAX_WAIT ]; then
    echo "ERROR: timed out waiting for openapi.json after ${MAX_WAIT}s"
    echo "---- tail of $UVICORN_LOG ----"
    tail -n 200 "$UVICORN_LOG" || true
    echo "---- end log ----"
    echo "You can inspect logs and re-run. Exiting with failure."
    exit 2
  fi
  sleep $SLEEP
done


# npx @redocly/cli build-docs 

# 4) bundle reDoc HTML (prefer npx redoc-cli bundle ./openapi.json -o api-docs.html)
echo "> bundling ReDoc HTML -> $API_DOCS_HTML"
if command -v npx >/dev/null 2>&1; then
  npx @redocly/cli build-docs "$OPENAPI_JSON" -o "$API_DOCS_HTML"
elif command -v redoc-cli >/dev/null 2>&1; then
  redoc-cli bundle "$OPENAPI_JSON" -o "$API_DOCS_HTML"
else
  echo "WARNING: neither npx nor redoc-cli found. Skipping ReDoc bundle step."
  echo "Install with: npm i -g redoc-cli  OR use npx (internet required)."
fi
echo "> ReDoc bundle done (if available)."

# 5) generate pdoc HTML for Python packages
echo "> regenerating pdoc HTML for modules: $PDOC_MODULES"
# ensure importability from project root
export PYTHONPATH="$ROOT"
mkdir -p "$PYDOC_DIR"

# pdoc usage: pdoc -o <outdir> <module>...
if ! command -v pdoc >/dev/null 2>&1; then
  echo "ERROR: pdoc not found in PATH. Install it in your Python env: pip install pdoc"
  echo "Terminating."
  # cleanup: kill uvicorn started above
  kill "$UVC_PID" || true
  rm -f "$UVICORN_PID_FILE"
  exit 3
fi

# run pdoc (it will rewrite the pydoc dir)
pdoc -o "$PYDOC_DIR" $PDOC_MODULES || {
  echo "pdoc failed. See output above. Tail of uvicorn log:"
  tail -n 200 "$UVICORN_LOG" || true
  kill "$UVC_PID" || true
  rm -f "$UVICORN_PID_FILE"
  exit 4
}

# 6) copy api-docs.html into pydoc (so the static site contains both)
if [ -f "$API_DOCS_HTML" ]; then
  cp -f "$API_DOCS_HTML" "$PYDOC_DIR/api-docs.html"
  echo "> copied $API_DOCS_HTML -> $PYDOC_DIR/api-docs.html"
fi

# 7) serve pydoc directory with python http.server (background)
echo "> stopping any existing pydoc http.server"
if pgrep -f "python -m http.server --directory $PYDOC_DIR $PYDOC_PORT" >/dev/null 2>&1; then
  pkill -f "python -m http.server --directory $PYDOC_DIR $PYDOC_PORT" || true
fi
if [ -f "$PYDOC_PID_FILE" ]; then
  OLD="$(cat "$PYDOC_PID_FILE" || true)"
  if [ -n "$OLD" ] && kill -0 "$OLD" >/dev/null 2>&1; then
    kill "$OLD" || true
  fi
  rm -f "$PYDOC_PID_FILE"
fi

echo "> starting static server on http://127.0.0.1:${PYDOC_PORT} (serving $PYDOC_DIR)"
python -m http.server --directory "$PYDOC_DIR" "$PYDOC_PORT" > "$ROOT/logs/pydoc_server.log" 2>&1 &
PYDOC_PID=$!
echo "$PYDOC_PID" > "$PYDOC_PID_FILE"
echo "pydoc server started (pid $PYDOC_PID)"

# 8) done: print summary + useful tail of logs
echo
echo "=== regen_docs.sh finished ==="
if [ -f "$API_DOCS_HTML" ]; then
  echo "API docs (ReDoc): file://$API_DOCS_HTML  (also copied to pydoc/api-docs.html)"
else
  echo "API docs (ReDoc) not generated (redoc-cli unavailable). You can still open /openapi.json at backend."
fi
echo "Static docs served at: http://127.0.0.1:${PYDOC_PORT}/"
echo "OpenAPI JSON saved: $OPENAPI_JSON"
echo "uvicorn pid: $UVC_PID (log: $UVICORN_LOG)"
echo "pydoc server pid: $PYDOC_PID (log: $ROOT/logs/pydoc_server.log)"
echo
echo "To stop the servers:"
echo "  pkill -f 'uvicorn backend.app.main:app' || true"
echo "  pkill -f \"python -m http.server --directory $PYDOC_DIR $PYDOC_PORT\" || true"
echo
echo "If you want this to run in CI, remove the background http.server and instead upload ./pydoc somewhere."
