Nice progress. Here’s a compact, action-ready memo that captures the milestone, the earlier phases, what exists now, how to start next time, and a prioritized checklist for follow ups. I kept it practical and strict so you can pick up work immediately.

# Milestone memo — Papers UI MVP, local dev working

## Current status (what we achieved)

1. Local Next.js app scaffolded with TypeScript, App Router, Tailwind and shadcn components, SWR/axios utilities.
2. Static fixture data added under `public/dev-data`, and a small mock API adapter to fetch them.
3. Four main pages implemented and wired to fixtures:

   1. Papers list: `src/app/page.tsx`
   2. Paper detail / reader: `src/app/papers/[paperId]/page.tsx`
   3. Semantic search: `src/app/search/page.tsx`
   4. Topics: `src/app/topics/page.tsx`
4. Small reusable components created: `src/components/PapersCard.tsx`, `src/components/SnippetList.tsx`.
5. Debugged App Router client/server boundaries, fixed stray cache references to trashed copy, and confirmed `npm run dev` boots and serves the app.

## Key artifacts and locations

1. Fixtures

   1. `public/dev-data/papers.json`
   2. `public/dev-data/papers/paper-001.json` (and other paper files)
   3. `public/dev-data/search-results.json`
   4. `public/dev-data/topics.json`
2. Types

   1. `src/types.ts`
3. Mock adapter

   1. `src/lib/mockApi.ts` (exports `apiGet(path)`)
4. Pages and components

   1. `src/app/page.tsx` — Papers list
   2. `src/app/papers/[paperId]/page.tsx` — Paper reader
   3. `src/app/search/page.tsx` — Semantic search
   4. `src/app/topics/page.tsx` — Topics UI
   5. `src/components/PapersCard.tsx`, `src/components/SnippetList.tsx`

## How to run (quick start)

1. From project root

```bash
cd ~/Documents/paper-kb/frontend
rm -rf .next
npm run dev
```

2. Visit:

   1. [http://localhost:3000/](http://localhost:3000/) for Papers list
   2. [http://localhost:3000/papers/paper-001](http://localhost:3000/papers/paper-001) for reader
   3. [http://localhost:3000/search](http://localhost:3000/search) for Semantic search
   4. [http://localhost:3000/topics](http://localhost:3000/topics) for Topics

If you see errors about server paths or Trash references, kill stray processes and remove the trashed frontend copy at `~/.local/share/Trash/files/frontend`, then retry.

## Decisions made, so you know why

1. Fixtures served from `public/dev-data` so Next dev serves them via fetch without adding a mock server. That keeps iteration fast.
2. For now, client code calls `apiGet`, not the real API. One toggle point is `src/lib/mockApi.ts`, so we swap to the real `fetcher` later.
3. Pages are client components where needed (`'use client'`), to keep interaction simple. Later we can move logic into small client components while keeping pages as server components for better SSR.
4. RAG and summarization are stubbed. Real model calls are kept server-side to avoid exposing keys.

## Short prioritized roadmap (next work)

1. UX polish, highest impact first

   1. Make PapersCard, SnippetList use shadcn primitives for consistent look and spacing.
   2. Add skeletons and loading states for lists and reader.
   3. Implement chunk anchor linking from search results (router push to `#chunk-...`).
2. Data wiring

   1. Swap `apiGet` to `fetcher` for lists and metadata; keep chunk text lazy loaded.
   2. Implement a minimal backend stub `/api/summary` (FastAPI) that returns cached text for a paper. Wire Summarize button to it.
3. Performance and caching

   1. Use SWR for caching lists and metadata, with `revalidateOnFocus: false`.
   2. Add a small sqlite or JSON cache for summaries on backend.
4. Small but important features

   1. Search result highlighting and "open in reader" behavior.
   2. Topic digest flow: "Create digest" posts selected snippet ids to `/api/summary`.
5. Hardening and tests

   1. Add a `/dev/components` page that renders all components using fixtures, for fast visual QA.
   2. Add basic e2e smoke test that loads key pages and checks for expected text.

## Backlog items (nice to have, later)

1. Streaming RAG answers with provenance links.
2. Per-paper pinned notes and export (JSON / Markdown).
3. Server-side rendering for paper list for SEO if needed.
4. Access control, multi-user session handling.
5. Topic map visualization (bubble map), precomputed topics in backend.

## Known issues and warnings

1. Next client/server boundary: keep interactive logic in client components. Prefer small client components and server page for data fetching where possible.
2. Token/prompt budget. Plan prompt stitching and top-k selection server-side. Avoid sending full paper text.
3. Watch for hard paths to trashed copies. If Next references Trash paths again, clear caches and remove trashed copy, then restart.
4. If you later add large fixtures, use lazy chunk-load to avoid huge pages.

## Acceptance criteria for this milestone

1. All four pages render and use fixture data.
2. Navigation between pages works, chunk anchors scroll to target.
3. Summarize button triggers a stubbed API and UI shows returned summary.
4. No lingering references to trashed folders in dev logs.




## Update# Memo — lock-in: current backend / pipeline / frontend status, decisions, CLI, next steps

Short: this memo records exactly what works, what is brittle, and the pragmatic fixes and CLI commands to reproduce the current state. It’s written to make it easy to pick up tomorrow and avoid repeating the mistakes that caused crashes. I focus on robustness and clear separation of concerns (parsing ↔ embedding ↔ DB).

---

# 1) Current state (facts)

* Repository layout (important bits):

  * `backend/app/` — FastAPI backend and chroma client/helpers.
  * `pipeline/ingestion/` — `pdf_ingestor.py`, `tei_parser.py`, `ingestor.py`.
  * `pipeline/embedding/` — `embedder.py`, `embed_cache.py` (cached embeddings).
  * `store/` — produced artefacts: `store/chunks` (jsonl), `store/chroma/chroma.sqlite3`, `store/emb_cache.sqlite`.
  * `frontend/` — Next.js + shadcn UI; page at `frontend/src/app/health/page.tsx`.
  * Dev data: `frontend/public/dev-data/*` (papers.json, search-results.json, topics.json).

* What **works** right now

  * PDF → TEI ingestion: `pipeline/ingestion/pdf_ingestor` successfully produced per-PDF TEI XMLs into `downloads/data/xmls/` (filenames reflect paper titles now).
  * TEI → chunks: `pipeline/ingestion/tei_parser` runs and writes per-paper `*_chunks.jsonl` into an out dir (the CLI wrapper is present).
  * Embedding + Chroma upsert: `pipeline/embedding/embedder` executed and created `store/chroma/chroma.sqlite3`. Example run showed `Seen=408 Added=408`.
  * A screenshot of the frontend health page is available at:
    `/mnt/data/6a42f5a4-a8f3-450a-ad66-886652af6c8a.png` (use this path as the file URL when needed).
  * Frontend health page exists and can use `frontend/public/dev-data` for offline testing.

* What is brittle / failing / needs small fixes

  * Backend failed on startup earlier because `CHROMA_COLL = CHROMA_CLIENT.get_collection(name=COLLECTION_NAME)` raised `NotFoundError` — code attempted `get_collection` instead of `get_or_create_collection` robustly (fixed later, but `get_or_create_collection` must accept client properly).
  * `ModuleNotFoundError: No module named 'app'` appeared when uvicorn import path didn't match package layout — mixing `backend.app.main` vs `app.main` imports. (Fix: start uvicorn from project root and use package import path; ensure `backend` is on PYTHONPATH or invoke using `-m backend.app.main`.)
  * `chunks_to_records` signature mismatch: `tei_parser` calls `chunks_to_records(title, pid, filtered_chunks)` but implementation accepted 2 args. This resulted in `chunks_to_records() takes 2 positional arguments but 3 were given`.
  * `cached_embed` not injected into FastAPI app startup — search/summary endpoints currently depend on `cached_embed` being set; if it's `None` requests fail.
  * `api_summary` performs synchronous LLM calls — blocks request thread; should be background job / queue and return a task id for polling.
  * `GET /api/papers/{paper_id}` currently fetches whole collection then filters client-side — inefficient at scale. Prefer `where` filtering or maintain a small SQL index of paper → chunk ids/metadata.
  * Inconsistent environment of collection name: code used both `collection_name="chunks"` and `COLLECTION_NAME` env var — unify.

---

# 2) Files you ran / important paths

* TEI produced to:

  * `downloads/data/xmls/2025-13_GRID-Google-project-Foresight-report.tei.xml`, etc.
* Chunk JSONL output (example target dir):

  * `store/chunks/<paper_id>_chunks.jsonl`
  * `store/chunks/all_chunks.jsonl`
* Chroma DB:

  * `store/chroma/chroma.sqlite3`
* Embedding cache:

  * `store/emb_cache.sqlite` (or `src/embedding_cache.sqlite` depending on run)
* Frontend health page:

  * `frontend/src/app/health/page.tsx`
* Screenshot (health UI):

  * `/mnt/data/6a42f5a4-a8f3-450a-ad66-886652af6c8a.png`

---

# 3) Reproducible CLI commands (use from project root)

1. Produce TEI from all PDFs in `storage/downloads` (non-recursive):

```bash
python -m pipeline.adapter.pdf_ingestor storage/downloads/ --out-tei ./downloads/data/xmls
```

2. Parse TEI files into chunks (example):

```bash
python -m pipeline.adapter.tei_parser downloads/data/xmls store/chunks --min-len 50
# or with embedding/upsert (disabled unless embed/upsert functions are properly wired)
python -m pipeline.adapter.tei_parser downloads/data/xmls store/chunks --embed --upsert --chroma-dir store/chroma
```

3. Produce embeddings and upsert into Chroma (fresh chroma, reset):

```bash
python -m shared.embedder \
  --input ./store/chunks \
  --chroma-dir ./store/chroma \
  --cache-db ./store/emb_cache.sqlite \
  --collection chunks \
  --batch 128 \
  --reset
```

4. Run the backend FastAPI (from project root):

```bash
# ensure PYTHONPATH includes project root or run as module
uvicorn backend.app.main:app --reload --port 9000
# Alternative (if package import issues persist):
python -m backend.app.main
```

5. Run frontend dev:

```bash
cd frontend
pnpm dev  # or `npm run dev` / `yarn dev` depending on setup
# open http://localhost:3000/health
```

6. Simple search/health curl:

```bash
curl http://127.0.0.1:9000/                 # health
curl http://127.0.0.1:9000/api/papers      # list papers (depends on Chroma state)
```

---

# 4) Immediate fixes (priority: HIGH) — actionable, copy/paste small patches

1. **Fix `chunks_to_records` signature**

   * Make sure `chunks_to_records(title, paper_id, chunks)` exists and maps canonical chunk schema to final record keys:

```py
def chunks_to_records(title: str, paper_id: str, chunks: List[Dict]) -> List[Dict]:
    recs = []
    for i, c in enumerate(chunks):
        recs.append({
            "chunk_id": c.get("id") or f"{paper_id}::chunk-{i}",
            "paper_id": paper_id,
            "title": title,
            "chunk_index": c.get("index", i),
            "text": c.get("text",""),
            "pages": c.get("pages"),
            # "bboxes": c.get("bboxes"),
            "header_path": c.get("header_path")
        })
    return recs
```

2. **Ensure `get_or_create_collection(name, client)` uses the client instance**

   * At startup: `client = make_chroma_client(CHROMA_DIR)` then `CHROMA_COLL = get_or_create_collection(COLLECTION_NAME, client=client)`.
   * `get_or_create_collection` should *not* ignore `client` param.

3. **Wire `cached_embed` into FastAPI at startup**

   * In `@app.on_event("startup")` set `cached_embed = shared.embed_cache.cached_embed` (or import properly).
   * If the embed cache initialization requires DB path, pass it via env var.

4. **Turn `api_summary` into background job (minimal)**

   * Use FastAPI `BackgroundTasks` to enqueue `run_summary_job(task_id, req)` and return `{"task_id": ..., "status":"queued"}` immediately.
   * Save summary rows into a small SQLite table `summaries(task_id, status, query, result_json, created_at)` so frontend can poll `GET /api/summary/{task_id}`.

5. **Unify collection name**

   * Use one env var `CHROMA_COLLECTION` everywhere; fallback default `"chunks"`.

---

# 5) Small-medium enhancements (next sprint)

* Replace client-side filter in `/api/papers/{paper_id}` with Chroma `where` filtering (if Chromadb version supports `where`).
* Add a minimal relational index (SQLite) for papers/chunks to avoid scanning entire Chroma for metadata queries.
* Implement `pipeline/prompt_builder.py`:

  * Expose `build_prompt(query, top_k_chunks, template_name="summarize.j2") -> (prompt_text, provenance_list)`
  * Use Jinja2 templates in `templates/` (single `summarize.j2` initially). Call this from background summary worker.
* Make summarizer produce provenance mapping and store prompt/templates used.

---

# 6) Frontend notes (how to exercise endpoints)

* Health page: `frontend/src/app/health/page.tsx` loads:

  * `GET /api/papers` to populate left column.
  * `GET /api/papers/{paper_id}` to load chunks into inspector.
  * `POST /api/search` for search box, with body `{ "q": "...", "k": 6 }`.
  * `POST /api/summary` should be adapted to start an async summary job and then poll `GET /api/summary/{task_id}`.
* Use `frontend/public/dev-data/` JSON files to test UI without backend.
* For quick UI tests use the screenshot at `/mnt/data/6a42f5a4-a8f3-450a-ad66-886652af6c8a.png`.

---

# 7) Prioritized checklist (concrete tasks you can do now)

1. (Now) Fix `chunks_to_records` signature and re-run `tei_parser` for `store/chunks`.
2. (Now) Fix `get_or_create_collection` to use `client` and change startup to create collection if missing.
3. (Now) Wire `cached_embed` into backend startup so search and summary endpoints do not crash.
4. (Soon) Change `api_summary` to use `BackgroundTasks` + a small `summaries` SQLite table; update frontend to poll.
5. (Soon) Replace client-side paper filtering with Chroma `where` or small SQLite index for `paper_id -> chunk ids`.
6. (Optional) Add small test that runs `embedder` with `--reset` on a fresh test dir to validate migrations/embedding dims.

---

# 8) Closing note (design stance & trade-offs)

* Keep parsing deterministic and stateless: parsing produces canonical JSONL chunks and stops. Embedding and DB upsert remain separate steps (CLI/orchestrator). This reduces flakiness and keeps retries simple.
* Treat embeddings & Chroma as *stateful* and expensive: expose clear reset and migration commands, and persist embedding cache.
* Move expensive LLM work to background jobs and persist results. This avoids blocking clients and provides the provenance needed for audits.
* Resist adding auth/metrics/testing until the core flows are robust and the background worker + prompt_builder are in place. Prioritize reliability over feature breadth.

---

If you want, I can:

* produce the exact patches for the 3 highest-priority fixes (1. `chunks_to_records`, 2. `get_or_create_collection` startup wiring, 3. `cached_embed` injection) ready to paste into the files you already have; **or**
* generate `pipeline/prompt_builder.py` that uses Jinja2 and a `templates/summarize.j2` file and an example `run_summary_job` background worker that uses it.

Which do you want me to produce next?

---

## Chunk-set backend smoke path

### 1) Generate chunk_set artifacts

Run your normal TEI pipeline/writer flow so files are written to:

- `artifacts/chunk_sets/*.chunk_set.json`

(override destination with `PAPER_KB_CHUNK_SETS_DIR` when needed.)

### 2) Start API using chunk_set storage backend

```bash
make api-chunk-set
```

Equivalent direct command:

```bash
PAPER_KB_CHUNK_SETS_DIR=artifacts/chunk_sets \
STORAGE_BACKEND=chunk_set \
uvicorn backend.app.main:app --reload --port 9000
```

### 3) Run smoke checks

With API running locally:

```bash
make smoke-chunk-set
```

This probes:

- `/`
- `/api/_admin/papers_health`
- `/api/papers`
- `/api/papers/{first_paper_id}` (chunks payload)

Script location:

- `scripts/poke_api_chunk_set.sh`
