#!/usr/bin/env bash
# scripts/frontend_health.sh
# Non-destructive health / discovery script for Paper-KB frontend
# Writes a timestamped log to scripts/logs/frontend_health_YYYYMMDD_HHMMSS.log
#
# Usage:
#   chmod +x scripts/frontend_health.sh
#   ./scripts/frontend_health.sh
#
# The script will not delete or modify files. It only inspects and logs info.

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
LOGDIR="$ROOT/scripts/logs"
mkdir -p "$LOGDIR"
TS="$(date +%Y%m%d_%H%M%S)"
LOGFILE="$LOGDIR/frontend_health_${TS}.log"

# helper: run a command and append header + output (stdout+stderr) to log
run_cmd() {
  local title="$1"
  shift
  echo "================================================================" >> "$LOGFILE"
  echo "== $title" | tee -a "$LOGFILE"
  echo "----------------------------------------------------------------" >> "$LOGFILE"
  { echo "\$ $*"; "$@" ; } >> "$LOGFILE" 2>&1 || echo "[error running: $*] (see log)" >> "$LOGFILE"
  echo "" >> "$LOGFILE"
}

# start logging
echo "Frontend health check for repo: $ROOT" > "$LOGFILE"
echo "Started: $(date --rfc-3339=seconds)" >> "$LOGFILE"
echo "" >> "$LOGFILE"

# Basic system info
run_cmd "uname -a" uname -a
run_cmd "whoami" whoami
run_cmd "pwd" pwd

# Node / npm environment
run_cmd "node -v (if installed, else blank)" node -v || true
run_cmd "npm -v (if installed)" npm -v || true
run_cmd "npx -v (if installed)" npx -v || true

# Project frontend path
FRONTEND="$ROOT/frontend"
echo "Frontend folder: $FRONTEND" >> "$LOGFILE"
echo "" >> "$LOGFILE"

# show frontend top-level files (exclude node_modules)
run_cmd "ls -la frontend/ (top-level)" ls -la "$FRONTEND" 2>/dev/null || true

# tree or fallback listing
if command -v tree >/dev/null 2>&1; then
  run_cmd "tree frontend/ -I node_modules -L 2" tree "$FRONTEND" -I node_modules -L 2
else
  run_cmd "find frontend/ -maxdepth 2 -type d -printf '%p\n' | sort" find "$FRONTEND" -maxdepth 2 -type d -printf '%p\n' | sort
fi

# Use ripgrep if available, otherwise fallback to grep
RG=""
if command -v rg >/dev/null 2>&1; then
  RG="rg --hidden --glob '!node_modules' --glob '!.git'"
else
  RG="grep -RIn --exclude-dir=node_modules --exclude-dir=.git"
fi

# 1) Next app routes (page.tsx)
echo "### Routes (page.tsx files)" >> "$LOGFILE"
if [ -d "$FRONTEND" ]; then
  if command -v rg >/dev/null 2>&1; then
    $RG "src/app/.*/page.tsx" -n "$FRONTEND" >> "$LOGFILE" 2>&1 || true
  else
    $RG "page.tsx" "$FRONTEND" | sed -n '1,200p' >> "$LOGFILE" 2>&1 || true
  fi
fi
echo "" >> "$LOGFILE"

# 2) Components export/function signatures (quick scan)
run_cmd "scan for component exports and top-level functions in src/components" bash -lc "$RG \"^export default function|export function|const .* = \\(|function .*\\(\" -n $FRONTEND/src/components || true"

# 3) List containers/presentational/ui files
run_cmd "ls frontend/src/components/containers" ls -1 "$FRONTEND/src/components/containers" 2>/dev/null || true
run_cmd "ls frontend/src/components/presentational" ls -1 "$FRONTEND/src/components/presentational" 2>/dev/null || true
run_cmd "ls frontend/src/components/ui" ls -1 "$FRONTEND/src/components/ui" 2>/dev/null || true

# 4) Hooks & state usage
run_cmd "search for hooks and state usages (usePapers, usePaperChunks, useState, useContext, useSWR, react-query)" bash -lc "$RG \"usePapers|usePaperChunks|useQuery|useSWR|useState|createContext|useContext|useReducer\" -n $FRONTEND/src || true"

# 5) API calls & api wrapper
run_cmd "show frontend/src/lib/api.ts (if exists)" bash -lc "if [ -f $FRONTEND/src/lib/api.ts ]; then sed -n '1,240p' $FRONTEND/src/lib/api.ts; else echo 'frontend/src/lib/api.ts not found'; fi"

run_cmd "search for fetch/axios usages" bash -lc "$RG \"fetch\\(|axios\\.|axios\\(\" -n $FRONTEND || true"
run_cmd "search for openapi/redoc/api-docs references" bash -lc "$RG \"openapi|redoc|api-docs\" -n $FRONTEND || true"

# 6) Normalizers and types
run_cmd "show frontend/src/lib/normalizers.ts (if exists)" bash -lc "if [ -f $FRONTEND/src/lib/normalizers.ts ]; then sed -n '1,240p' $FRONTEND/src/lib/normalizers.ts; else echo 'frontend/src/lib/normalizers.ts not found'; fi"
run_cmd "show frontend/src/types.ts (if exists)" bash -lc "if [ -f $FRONTEND/src/types.ts ]; then sed -n '1,240p' $FRONTEND/src/types.ts; else echo 'frontend/src/types.ts not found'; fi"

# 7) Search for key fields we care about (paper_id, chunk_id, n_chunks, preview)
run_cmd "search for keys: paper_id, chunk_id, n_chunks, preview" bash -lc "$RG \"paper_id|chunk_id|n_chunks|preview\" -n $FRONTEND || true"

# 8) Storybook & stories
run_cmd "list .storybook files" ls -la "$FRONTEND/.storybook" 2>/dev/null || true
run_cmd "grep storybook config / package" bash -lc "$RG \"@storybook|storybook\" -n $FRONTEND || true"
run_cmd "list stories directory (src/stories and components/__stories__)" ls -la "$FRONTEND/src/stories" 2>/dev/null || true
run_cmd "ls components __stories__" ls -la "$FRONTEND/src/components/__stories__" 2>/dev/null || true

# 9) Tests (Playwright / smoke)
run_cmd "list frontend/src/tests" ls -la "$FRONTEND/src/tests" 2>/dev/null || true
run_cmd "search for playwright / test patterns" bash -lc "$RG \"@playwright/test|playwright|test\\(|describe\\(|expect\\(\" -n $FRONTEND || true"

# 10) package.json & deps
if command -v jq >/dev/null 2>&1; then
  run_cmd "package.json dependencies (jq formatted)" jq -r '.dependencies, .devDependencies' "$FRONTEND/package.json" 2>/dev/null || true
else
  run_cmd "cat frontend/package.json (first 240 lines)" sed -n '1,240p' "$FRONTEND/package.json" 2>/dev/null || true
fi

# 11) show key config files if present (next.config, storybook main, preview)
run_cmd "show frontend/next.config.ts (if exists)" bash -lc "if [ -f $FRONTEND/next.config.ts ]; then sed -n '1,240p' $FRONTEND/next.config.ts; else echo 'frontend/next.config.ts not found'; fi"
run_cmd "show frontend/.storybook/main.ts (if exists)" bash -lc "if [ -f $FRONTEND/.storybook/main.ts ]; then sed -n '1,240p' $FRONTEND/.storybook/main.ts; else echo '.storybook/main.ts not found'; fi"
run_cmd "show frontend/.storybook/preview.ts (if exists)" bash -lc "if [ -f $FRONTEND/.storybook/preview.ts ]; then sed -n '1,240p' $FRONTEND/.storybook/preview.ts; else echo '.storybook/preview.ts not found'; fi"

# 12) public dev-data preview
run_cmd "list public/dev-data files" ls -la "$FRONTEND/public/dev-data" 2>/dev/null || true
run_cmd "head public/dev-data/papers.json (if exists)" bash -lc "if [ -f $FRONTEND/public/dev-data/papers.json ]; then sed -n '1,200p' $FRONTEND/public/dev-data/papers.json; else echo 'public/dev-data/papers.json not found'; fi"

# 13) search for data-testid usage
run_cmd "search for data-testid usages (Playwright helpers)" bash -lc "$RG \"data-testid|dataTestId|data_testid\" -n $FRONTEND || true"

# 14) repeated imports & heavy libs scan
run_cmd "scan for common imports (react, next, charting libs)" bash -lc "$RG \"from 'react'|from 'next'|from 'react-dom'|from 'recharts'|from 'lucide-react'\" -n $FRONTEND || true"

# 15) grep for any TODOs or FIXMEs that hint at fragile parts
run_cmd "search for TODO/FIXME/XXX in frontend source" bash -lc "$RG \"TODO|FIXME|XXX\" -n $FRONTEND || true"

# wrap up
echo "" >> "$LOGFILE"
echo "Completed: $(date --rfc-3339=seconds)" >> "$LOGFILE"
echo "Logfile: $LOGFILE" >> "$LOGFILE"
echo "" >> "$LOGFILE"

# print path for user
cat <<EOF

Frontend health scan finished.
Logfile created: $LOGFILE

To view it:
  less "$LOGFILE"
or
  tail -n +1 "$LOGFILE" | sed -n '1,240p'

If you want, you can commit this script into scripts/ and run it in CI (adjust paths).
EOF
