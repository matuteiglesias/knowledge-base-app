#!/usr/bin/env bash
# tools/test_api.sh
# Lightweight API smoke tester for Paper-KB
# Requirements: curl, jq
# Usage: BASE_URL=http://localhost:9000 ./tools/test_api.sh

set -uo pipefail

BASE_URL=${BASE_URL:-http://localhost:9000}
OUTDIR=${OUTDIR:-./api_test_results/$(date +%Y%m%dT%H%M%S)}
mkdir -p "$OUTDIR"

echo "Paper-KB API smoke test"
echo "BASE_URL = $BASE_URL"
echo "Outputs -> $OUTDIR"
echo

# helper to run a request and save response + status
# args: method path out_filename [data]
req() {
  local method=$1
  local path=$2
  local out=$3
  local data=${4:-}
  local hdrs=("-H" "Accept: application/json")
  local curl_opts=("--silent" "--show-error" "--write-out" "%{http_code}" "--output" "$out.tmp")
  if [[ -n "$data" ]]; then
    hdrs+=("-H" "Content-Type: application/json")
    curl_opts+=("-d" "$data")
  fi

  echo -n "-> $method $path ... "
  http_code=$(curl "${curl_opts[@]}" "${hdrs[@]}" -X "$method" "$BASE_URL$path" 2>&1) || {
    echo "curl-failed"
    echo "<<curl error>>" > "$out"
    return 1
  }

  # move tmp to final file and write code to separate .code file
  mv "$out.tmp" "$out" 2>/dev/null || true
  echo "$http_code" > "$out.code"
  echo "$http_code"
  return 0
}

# summary_record() {
#   printf "%-36s %s\n" "$1" "$2"
# }

# collect summary
declare -a SUMMARY=()

# 1) Root
req "GET" "/" "$OUTDIR/root.json"
SUMMARY+=("GET / -> $(cat $OUTDIR/root.json.code 2>/dev/null || echo 'err')")

# 2) Admin health
req "GET" "/api/_admin/papers_health" "$OUTDIR/health.json"
SUMMARY+=("GET /api/_admin/papers_health -> $(cat $OUTDIR/health.json.code 2>/dev/null || echo 'err')")

# 3) list papers
req "GET" "/api/papers" "$OUTDIR/papers.json"
papers_code=$(cat "$OUTDIR/papers.json.code" 2>/dev/null || echo '')
SUMMARY+=("GET /api/papers -> $papers_code")

# extract first paper_id if available
paper_id=""
if [[ -s "$OUTDIR/papers.json" && -x "$(command -v jq)" ]]; then
  paper_id=$(jq -r '.papers[0].paper_id // empty' "$OUTDIR/papers.json")
fi

# If no paper found, try seeding a small fixture then re-query
if [[ -z "$paper_id" ]]; then
  echo "No paper found in /api/papers — attempting dev seed (/fixture/papers?n_papers=3) and re-query"
  req "POST" "/fixture/papers?n_papers=3&min_chunks=2&max_chunks=4" "$OUTDIR/seed.json"
  SUMMARY+=("POST /fixture/papers -> $(cat $OUTDIR/seed.json.code 2>/dev/null || echo 'err')")
  # re-query papers
  req "GET" "/api/papers" "$OUTDIR/papers_after_seed.json"
  SUMMARY+=("GET /api/papers (after seed) -> $(cat $OUTDIR/papers_after_seed.json.code 2>/dev/null || echo 'err')")
  if [[ -s "$OUTDIR/papers_after_seed.json" && -x "$(command -v jq)" ]]; then
    paper_id=$(jq -r '.papers[0].paper_id // empty' "$OUTDIR/papers_after_seed.json")
    # copy to canonical path for later usage
    cp "$OUTDIR/papers_after_seed.json" "$OUTDIR/papers.json" 2>/dev/null || true
  fi
fi

echo "picked paper_id: '$paper_id'"

if [[ -n "$paper_id" ]]; then
  # 4) get paginated chunks for paper
  req "GET" "/api/papers/$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$paper_id")?offset=0&limit=6" "$OUTDIR/paper_${paper_id}_chunks.json"
  SUMMARY+=("GET /api/papers/$paper_id -> $(cat $OUTDIR/paper_${paper_id}_chunks.json.code 2>/dev/null || echo 'err')")

  # 5) try to extract a chunk id
  chunk_id=""
  if [[ -s "$OUTDIR/paper_${paper_id}_chunks.json" && -x "$(command -v jq)" ]]; then
    chunk_id=$(jq -r '.chunks[0].chunk_id // empty' "$OUTDIR/paper_${paper_id}_chunks.json")
  fi
  echo "picked chunk_id: '$chunk_id'"

  if [[ -n "$chunk_id" ]]; then
    # 6) get single chunk
    # quote chunk id
    q_chunk_id=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$chunk_id")
    req "GET" "/api/papers/$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$paper_id")/chunks/$q_chunk_id" "$OUTDIR/paper_${paper_id}_chunk_${chunk_id}.json"
    SUMMARY+=("GET /api/papers/$paper_id/chunks/$chunk_id -> $(cat $OUTDIR/paper_${paper_id}_chunk_${chunk_id}.json.code 2>/dev/null || echo 'err')")

    # 7) filtered chunks: use first few words of the chunk text (if available) as q
    snippet=$(jq -r '.text // empty' "$OUTDIR/paper_${paper_id}_chunk_${chunk_id}.json" | head -c 200)
    if [[ -n "$snippet" ]]; then
      # take first token-ish search term
      qterm=$(echo "$snippet" | tr -s '[:space:]' ' ' | awk '{print $1}' | tr -d '\r\n' | sed 's/[^a-zA-Z0-9_-]//g')
      if [[ -n "$qterm" ]]; then
        req "GET" "/api/papers/$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$paper_id")/chunks?q=$qterm&offset=0&limit=5" "$OUTDIR/paper_${paper_id}_chunks_filtered_q_${qterm}.json"
        SUMMARY+=("GET /api/papers/$paper_id/chunks?q=$qterm -> $(cat $OUTDIR/paper_${paper_id}_chunks_filtered_q_${qterm}.json.code 2>/dev/null || echo 'err')")
      fi
    fi

    # 8) paginated slice (offset + limit)
    req "GET" "/api/papers/$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$paper_id")/chunks?offset=1&limit=2" "$OUTDIR/paper_${paper_id}_chunks_offset1_limit2.json"
    SUMMARY+=("GET /api/papers/$paper_id/chunks?offset=1&limit=2 -> $(cat $OUTDIR/paper_${paper_id}_chunks_offset1_limit2.json.code 2>/dev/null || echo 'err')")
  else
    echo "no chunk id found for paper; skipping chunk-level tests"
  fi
else
  echo "no paper_id found; skipping per-paper endpoints"
fi

# optional: try admin refresh endpoints (safe dev-only)
req "POST" "/api/_admin/refresh_chunks_cache" "$OUTDIR/refresh_chunks_cache.json" || true
SUMMARY+=("POST /api/_admin/refresh_chunks_cache -> $(cat $OUTDIR/refresh_chunks_cache.json.code 2>/dev/null || echo 'err')")
req "POST" "/api/_admin/refresh_papers_cache" "$OUTDIR/refresh_papers_cache.json" || true
SUMMARY+=("POST /api/_admin/refresh_papers_cache -> $(cat $OUTDIR/refresh_papers_cache.json.code 2>/dev/null || echo 'err')")

# print compact summary
echo
echo "==== SUMMARY ===="
for s in "${SUMMARY[@]}"; do
  summary_record "$s"
done

echo
echo "Saved responses in: $OUTDIR"
echo "Sample files:"
ls -l "$OUTDIR" | sed -n '1,200p'
echo
echo "Notes:"
echo "- If jq is missing, some JSON parsing will not run; install jq to enable smarter selection."
echo "- This script is non-destructive except for the dev-seed endpoint which writes fixture files. Run on local dev only."
