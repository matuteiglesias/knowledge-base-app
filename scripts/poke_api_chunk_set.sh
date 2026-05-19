#!/usr/bin/env bash
# Lightweight smoke for ChunkSetStorageAdapter-backed API
# Usage:
#   BASE_URL=http://127.0.0.1:9000 scripts/poke_api_chunk_set.sh

set -euo pipefail

BASE_URL=${BASE_URL:-http://127.0.0.1:9000}
OUTDIR=${OUTDIR:-./api_test_results/chunk_set_$(date +%Y%m%dT%H%M%S)}
mkdir -p "$OUTDIR"

echo "Chunk-set API smoke test"
echo "BASE_URL=$BASE_URL"
echo "OUTDIR=$OUTDIR"

req() {
  local path=$1
  local out=$2
  local code
  code=$(curl --silent --show-error --write-out "%{http_code}" --output "$out" "$BASE_URL$path")
  echo "$code" > "$out.code"
  echo "GET $path -> $code"
}

req "/" "$OUTDIR/root.json"
req "/api/_admin/papers_health" "$OUTDIR/health.json"
req "/api/papers" "$OUTDIR/papers.json"

paper_id=""
if command -v jq >/dev/null 2>&1; then
  paper_id=$(jq -r '.papers[0].paper_id // empty' "$OUTDIR/papers.json")
fi

if [[ -n "$paper_id" ]]; then
  qp=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$paper_id")
  req "/api/papers/$qp?offset=0&limit=20" "$OUTDIR/paper_${paper_id}_chunks.json"
else
  echo "No paper_id found in /api/papers response; skipping per-paper chunk endpoint"
fi

echo "Saved smoke outputs to $OUTDIR"
