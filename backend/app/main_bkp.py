# # backend/app/main.py
# """Paper-KB FastAPI backend (refactored, minimal, robust).

# Usage:
#   CHROMA_DIR=./store/chroma CHROMA_COLLECTION=chunks uvicorn backend.app.main:app --reload --port 9000

# This module:
#  - creates a Chroma client and collection on startup (uses get_or_create_collection correctly)
#  - exposes basic endpoints for papers, chunks, search, and async summaries (background task)
#  - persists summary jobs/results into a small sqlite DB (simple schema)
#  - expects a cached_embed(text_id, text) function available via import; otherwise uses a deterministic placeholder embed
# """
# from __future__ import annotations
# import os
# import json
# import sqlite3
# import hashlib
# import time
# import traceback
# from pathlib import Path
# from typing import Any, Dict, List, Optional

# import uvicorn
# from fastapi import FastAPI, HTTPException, BackgroundTasks
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from backend.app.chunks_fs import normalize_chunk

# # Project helpers (adjust if your package layout differs)
# # Make sure backend/app/chroma_client.py defines make_chroma_client and get_or_create_collection
# import sys

# sys.path.insert(0, str(Path(__file__).resolve().parents[2]))




# from shared.config import CHROMA_DIR, SUMMARY_DB, chroma_collection_name, STORE_SUMMARIES_DIR
# from shared.chroma_helpers import safe_query, get_chunks_for_paper, get_or_create_collection
# from pipeline.embedding.engine import batch_embed_records




# # LLM wrapper (keeps code minimal). Use OPENAI_API_KEY env if you want real LLM calls.
# try:
#     import openai
#     OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
#     if OPENAI_API_KEY:
#         openai.api_key = OPENAI_API_KEY
# except Exception:
#     openai = None
#     OPENAI_API_KEY = None



# # -------------------------
# # FastAPI app + CORS
# # -------------------------
# app = FastAPI(
#     title="Paper-KB API",
#     description="Paper-KB: fast prototype backend exposing Chroma-powered paper/chunk APIs, search and summarization jobs.",
#     version="0.1.0",
#     contact={"name": "Matias Iglesias", "email": "you@example.com"},
#     docs_url="/docs",
#     redoc_url="/redoc",
#     openapi_url="/openapi.json",
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
#     allow_credentials=True,
#     allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
#     allow_headers=["*"],
# )



# # -------------------------
# # Chroma client & collection (initialized on startup)
# # -------------------------
# from shared.chroma_helpers import get_or_create_collection  # use relative imports
# from shared.chroma_client import get_client
# def _get_coll_or_503():
#     # Prefer the collection cached on app.state, fall back to module global
#     coll = getattr(app.state, "chroma_collection", None)
#     if coll is None:
#         raise HTTPException(status_code=503, detail="Chroma collection not initialized")
#     return coll

# # imports (place with your other shared imports)
# from pathlib import Path as _Path  # avoid shadowing earlier Path import
# from shared.chunks_cache import (
#     load_chunks_cache,
#     is_loaded as chunks_cache_loaded,
#     get_chunk_from_cache,
#     list_chunks_for_paper,
#     list_papers_summary,
#     is_streaming_mode as chunks_cache_streaming,
#     get_loaded_path as chunks_cache_path,
# )




# # from backend.schemas import PaperMeta, CanonicalChunk, SummaryRequest, SearchRequest

# from backend.app.schemas import (
#     PaperMeta,
#     PapersList,
#     CanonicalChunk,
#     ChunkResponse,
#     PaperChunksResponse,
#     # normalize_chunk,
#     SummaryRequest,
#     SearchRequest,
#     SummaryResult,
#     SearchResponse,
#     SearchHit,
#     canonical_to_api_chunk,
# )

# from backend.app.services import (
#     get_paper_chunks,
#     seed_dev_fixture,
#     get_chunk,
#     list_papers,
#     seed_dev_fixture,
#     refresh_papers_cache_from_fs,
# )


# # -------------------------
# # API endpoints
# # -------------------------
# @app.get("/", tags=["health"])
# def root():
#     return {"status": "ok", "message": "paper-kb backend running"}


# from fastapi import Depends

# def get_storage():
#     st = getattr(app.state, "storage", None)
#     if not st:
#         raise HTTPException(status_code=503, detail="storage not initialized")
#     return st



# from collections import defaultdict

# sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# from shared.chroma_helpers import _safe_collection_get_all
# from backend.app.storage_adapter import StorageAdapter, JsonlAdapter

# import json
# from pathlib import Path as _Path  # if not already present
# from typing import cast


# # simple in-process papers cache
# _PAPERS_CACHE: list[dict] = []
# _PAPERS_CACHE_LOADED: bool = False
# _PAPERS_CACHE_PATH: str | None = None


# @app.post("/_dev/seed")
# def seed_dev_data():
#     # write to in-memory store or file
#     return {"ok": True}

# def get_storage() -> StorageAdapter:
#     st = getattr(app.state, "storage", None)
#     if st is None:
#         # Storage not yet initialized
#         raise HTTPException(status_code=503, detail="storage adapter not initialized")
#     return cast(StorageAdapter, st)



# @app.on_event("startup")
# def _startup():
#     """
#     Create and attach a storage adapter and start background cache loading quickly
#     so the server becomes responsive ASAP.
#     """
#     print(f"[startup] initializing storage adapter (STORAGE_BACKEND={os.getenv('STORAGE_BACKEND')})")
#     try:
#         storage = create_adapter_from_env()
#     except Exception:
#         storage = JsonlAdapter()  # fallback if factory missing; ensure import present if you use this line

#     app.state.storage = storage
#     app.state.cache_ready = False

#     def _bg_load():
#         try:
#             logger = logging.getLogger("storage.loader")
#             logger.info("background cache load started")
#             storage.load_caches()
#             app.state.cache_ready = True
#             logger.info("background cache load finished")
#         except Exception:
#             logger = logging.getLogger("storage.loader")
#             logger.exception("background cache load failed")
#             app.state.cache_ready = False

#     t = threading.Thread(target=_bg_load, daemon=True)
#     t.start()
#     print("[startup] storage adapter attached; caches loading in background")
# @app.get("/api/_admin/papers_health", tags=["health"])
# def papers_health():
#     return {
#         "papers_cache_loaded": bool(getattr(app.state, "papers_cache_loaded", False)),
#         "n_papers_in_cache": len(_PAPERS_CACHE) if isinstance(_PAPERS_CACHE, list) else 0,
#         "chunks_cache_loaded": bool(getattr(app.state, "chunks_cache_loaded", False)),
#         "chroma_client": bool(getattr(app.state, "chroma_client", None) is not None),
#     }

# @app.on_event("shutdown")
# def shutdown_event():
#     try:
#         st = getattr(app.state, "storage", None)
#         if st:
#             print("[shutdown] closing storage adapter")
#             try:
#                 st.close()
#             except Exception:
#                 import traceback
#                 traceback.print_exc()
#     except Exception as e:
#         print("[shutdown] persist/close failed:", e)


# from backend.app import services

# # @app.get("/api/papers", response_model=PapersList, tags=["papers"], summary="List papers (cache -> storage)")
# # def api_list_papers():
# #     st = get_storage()
# #     papers = st.list_papers()
# #     return PapersList(papers=papers)

# @app.get("/api/papers", response_model=PapersList, tags=["papers"], summary="List papers (cache -> storage)")
# def api_list_papers(storage=Depends(get_storage)):
#     papers = services.list_papers(storage)
#     return PapersList(papers=papers)



# @app.get("/api/papers/{paper_id}", response_model=PaperChunksResponse, tags=["papers","chunks"],
#          summary="Get paginated chunks for a paper")
# def api_get_paper(paper_id: str, offset: int = 0, limit: int = 200):
#     return get_paper_chunks(paper_id,
#                            offset=offset,
#                            limit=limit,
#                            chroma_coll=getattr(app.state, "chroma_collection", None))

# @app.get("/api/papers/{paper_id}", response_model=PaperChunksResponse, tags=["papers","chunks"],
#          summary="Get paginated chunks for a paper")
# def api_get_paper(paper_id: str, offset: int = 0, limit: int = 200):
#     st = get_storage()
#     res = st.list_chunks(paper_id=paper_id, limit=limit, offset=offset)
#     total = int(res.get("n", 0))
#     # We need to convert adapter chunks to CanonicalChunk / API chunk shape.
#     chunks_out = []
#     for c in res.get("chunks", []):
#         # c is {'id','text','meta'}
#         # try to normalize via existing helpers (but avoid heavy instantiation)
#         chunks_out.append(ChunkResponse(
#             chunk_id=c.get("id") or "",
#             text=c.get("text") or "",
#             chunk_index=c.get("meta", {}).get("chunk_index", 0),
#             char_len=c.get("meta", {}).get("char_len", len(c.get("text") or "")),
#             header_path=c.get("meta", {}).get("header_path"),
#             pages=c.get("meta", {}).get("pages"),
#             meta=c.get("meta", {})
#         ))
#     return PaperChunksResponse(paper_id=paper_id, total=total, chunks=chunks_out)


# @app.get("/api/papers/{paper_id}/chunks/{chunk_id}", response_model=ChunkResponse, tags=["papers","chunks"],
#          summary="Get single chunk")
# def api_get_chunk(paper_id: str, chunk_id: str):
#     c = get_chunk(paper_id, chunk_id, chroma_coll=getattr(app.state, "chroma_collection", None))
#     if c is None:
#         raise HTTPException(status_code=404, detail="chunk not found")
#     return c

# # dev seed route (optional)
# @app.post("/_dev/seed", tags=["dev"])
# def dev_seed(n_papers: int = 8, min_chunks: int = 6, max_chunks: int = 12):
#     created = seed_dev_fixture(n_papers=n_papers, min_chunks=min_chunks, max_chunks=max_chunks, write_files=True)
#     return {"n": len(created), "papers": [p.dict() for p in created]}



# # ---- GET /api/papers/{paper_id}/chunks?q=...  -> filtered chunks (PaperChunksResponse) ----
# @app.get("/api/papers/{paper_id}/chunks", tags=['papers','chunks'], response_model=PaperChunksResponse,
#             summary="Get chunks for a paper (optionally filtered by q)")
# def get_filtered_chunks(paper_id: str, q: str = "", offset: int = 0, limit: int = 200):
#     try:
#         if getattr(app.state, "chunks_cache_loaded", False):
#             raw_chunks = list_chunks_for_paper(paper_id)  # returns list of dicts
#         else:
#             raw_chunks = get_chunks_for_paper(paper_id)  # your helper to read chunks from FS or collection

#         if q:
#             q_low = q.lower()
#             def preview_text(c):
#                 return (c.get("preview") or c.get("text") or "").lower()
#             filtered = [c for c in raw_chunks if q_low in preview_text(c)]
#         else:
#             filtered = raw_chunks

#         total = len(filtered)
#         page = filtered[offset: offset + limit]

#         chunks_out: List[ChunkResponse] = []
#         for rec in page:
#             try:
#                 cc = normalize_chunk(rec, paper_id=paper_id)
#             except Exception:
#                 # best-effort
#                 cc = CanonicalChunk(
#                     chunk_id=rec.get("chunk_id") or rec.get("id"),
#                     paper_id=paper_id,
#                     text=rec.get("text") or rec.get("preview") or "",
#                     chunk_index=int(rec.get("chunk_index") or 0),
#                     char_len=int(rec.get("char_len") or len((rec.get("text") or ""))),
#                     header_path=rec.get("header_path"),
#                     pages=rec.get("pages"),
#                     meta=rec.get("meta") or {}
#                 )
#             chunks_out.append(
#                 ChunkResponse(
#                     chunk_id = cc.chunk_id,
#                     text = cc.text,
#                     chunk_index = cc.chunk_index,
#                     char_len = cc.char_len,
#                     header_path = cc.header_path,
#                     pages = cc.pages,
#                     meta = cc.meta
#                 )
#             )

#         return PaperChunksResponse(paper_id=paper_id, total=total, chunks=chunks_out)
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))



# @app.post("/api/_admin/refresh_chunks_cache", tags = ['chunks'])
# def refresh_chunks_cache():
#     """
#     Admin-only convenience endpoint. Reloads store/chunks/all_chunks.jsonl into memory.
#     Use only from localhost or protect with auth in production.
#     """
#     try:
#         chroma_dir_path = _Path(CHROMA_DIR)
#         chunks_jsonl = chroma_dir_path.parent / "chunks" / "all_chunks.jsonl"
#         load_chunks_cache(chunks_jsonl)
#         loaded = chunks_cache_loaded()
#         streaming = chunks_cache_streaming()
#         app.state.chunks_cache_loaded = loaded
#         return {"loaded": loaded, "streaming_mode": streaming, "path": chunks_cache_path()}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"refresh failed: {e}")


# @app.post("/api/_admin/refresh_papers_cache", tags = ['papers'])
# def refresh_papers_cache():
#     """
#     Reload store/chunks/all_papers.jsonl into memory.
#     Use only from localhost or protect with auth in production.
#     """
#     try:
#         chroma_dir_path = _Path(CHROMA_DIR)
#         papers_jsonl = chroma_dir_path.parent / "chunks" / "all_papers.jsonl"
#         refresh_papers_cache_from_fs(papers_jsonl)
#         app.state.papers_cache_loaded = bool(_PAPERS_CACHE_LOADED)
#         app.state.papers_cache_path = _PAPERS_CACHE_PATH
#         return {"loaded": _PAPERS_CACHE_LOADED, "path": _PAPERS_CACHE_PATH, "n_papers": len(_PAPERS_CACHE)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"refresh failed: {e}")



# # --- dev seed for paper-kb (insert into backend/app/main.py) ---
# from pathlib import Path
# import random
# import json
# from typing import List, Optional

# # import your schemas
# from backend.app import schemas  # adjust the import if your project layout uses `backend.app.schemas`

# from shared.config import CHUNKS_DIR


# # CHROMA_DIR = Path(_p("CHROMA_DIR", str(REPO_ROOT / "store" / "chroma"))).expanduser().resolve()
# # CHUNKS_DIR = Path(_p("CHUNKS_DIR", str(REPO_ROOT / "store" / "chunks"))).expanduser().resolve()
# # PAPERS_DIR = Path(_p("PAPERS_DIR", str(REPO_ROOT / "store" / "papers"))).expanduser().resolve()
# # STORE_SUMMARIES_DIR = Path(_p("STORE_SUMMARIES_DIR", str(REPO_ROOT / "store" / "summaries"))).expanduser().resolve()


# # configuration: prefer existing app-config values if present, else fallback
# PAPERS_CACHE_PATH = Path("store/fixture/papers.json")          # adapt to your app's configured path
# CHUNKS_CACHE_DIR = Path("store/fixture")               # each paper => file or directory with JSON
# PAPERS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
# CHUNKS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# def _rand_text(seed: int, words: int = 40) -> str:
#     # quick deterministic-ish lorem for debugging
#     random.seed(seed)
#     words_pool = ("effects climate change adaptation mitigation emissions model "
#                   "economy social policy experiment dataset results analysis "
#                   "methodology discussion conclusion figure table reference").split()
#     return " ".join(random.choice(words_pool) for _ in range(words))

# # # FastAPI route
# # from fastapi import APIRouter, HTTPException

# # router = APIRouter()  # or use existing `app` instance: app.post("/_dev/seed")
# @app.post("/_dev/seed", tags=["dev"])
# def seed_dev_data(n_papers: int = 8, min_chunks: int = 6, max_chunks: int = 16, write_files: bool = True):
#     if n_papers <= 0 or min_chunks <= 0 or max_chunks <= 0:
#         raise HTTPException(status_code=400, detail="Bad seed parameters")
#     if min_chunks > max_chunks:
#         min_chunks, max_chunks = max_chunks, min_chunks

#     fixture = seed_dev_fixture(
#         n_papers=n_papers,
#         chunks_range=(min_chunks, max_chunks),
#         include_chunk_files=write_files,
#     )
#     return {"status": "seeded", "n_papers": len(fixture["papers"]), "papers_sample": fixture["papers"][:3]}


# # --- end seed snippet ---





# # -------------------------
# # Run server (for manual runs)
# # -------------------------
# if __name__ == "__main__":
#     uvicorn.run("backend.app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 9000)), reload=True)







# # # -------------------------
# # # Summary flow: enqueue + background worker
# # # -------------------------
# # def llm_generate(prompt: str, max_tokens: int = 256) -> str:
# #     """Synchronous LLM call wrapper. In production, you would replace or route through a queue + billing monitor."""
# #     if openai and OPENAI_API_KEY:
# #         rsp = openai.ChatCompletion.create(
# #             model="gpt-4o-mini",
# #             messages=[{"role": "user", "content": prompt}],
# #             max_tokens=max_tokens,
# #             temperature=0.2,
# #         )
# #         return rsp.choices[0].message.content.strip()
# #     # fallback: echo prompt header (deterministic, safe)
# #     return f"[LLM not configured] prompt preview: {prompt[:500]}"



# # def _build_prompt_and_prov(docs: List[Dict[str, Any]], question: str) -> tuple[str, List[Dict[str, Any]]]:
# #     ctx = ""
# #     prov = []
# #     for n, item in enumerate(docs):
# #         meta = item.get("meta") or {}
# #         src = f"{meta.get('paper_id','?')}:{meta.get('pages','')}"
# #         text = item.get("text","")
# #         ctx += f"[{n+1}] {src} — {text}\n\n"
# #         prov.append({"index": n+1, "id": item.get("id"), "meta": meta})
# #     prompt = f"""You are a concise summarizer. Use ONLY the context paragraphs below to answer the question.
# # Question: {question}

# # Context paragraphs:
# # {ctx}

# # Answer in one paragraph, and for each factual sentence include a bracketed reference like [1] referring to the context index that supports it.
# # """
# #     return prompt, prov



# # STORE_SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)



# # # -----------------------------
# # # helpers: summary file ops
# # # -----------------------------
# # def summary_id_for_request(req_obj: Dict[str, Any]) -> str:
# #     key = json.dumps(req_obj, sort_keys=True, ensure_ascii=False)
# #     return "sum-" + hashlib.sha1(key.encode("utf8")).hexdigest()


# # def summary_path_for_id(summary_id: str) -> Path:
# #     return STORE_SUMMARIES_DIR / f"{summary_id}.json"


# # def load_summary_record(summary_id: str) -> Optional[Dict[str, Any]]:
# #     p = summary_path_for_id(summary_id)
# #     if not p.exists():
# #         return None
# #     try:
# #         return json.loads(p.read_text(encoding="utf8"))
# #     except Exception:
# #         return None


# # def save_summary_record(summary_id: str, payload: Dict[str, Any]) -> None:
# #     p = summary_path_for_id(summary_id)
# #     tmp = p.with_suffix(".json.tmp")
# #     tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf8")
# #     tmp.replace(p)


# # # -----------------------------
# # # /api/search - typed and robust
# # # -----------------------------
# # @app.post("/api/search", tags=["search"], response_model=SearchResponse, summary="Embedding search (RAG hits)")
# # def api_search(req: SearchRequest):
# #     q = (req.q or "").strip()
# #     if not q:
# #         raise HTTPException(status_code=400, detail="Empty query")

# #     # produce embedding
# #     emb = batch_embed_records("query:" + q, q)
# #     if not emb:
# #         raise HTTPException(status_code=500, detail="Embedding failed")
# #     emb_list = list(emb)

# #     coll = _get_coll_or_503()
# #     where = {"paper_id": {"$eq": req.paper_id}} if req.paper_id else None

# #     try:
# #         res = safe_query(coll, emb_list, n_results=int(req.k or 6), where=where,
# #                          include=["documents", "metadatas", "ids", "distances"])
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=f"safe_query error: {e}")

# #     # safe_query returns shape with possibly nested lists; normalize
# #     docs = res.get("documents") or []
# #     metas = res.get("metadatas") or []
# #     ids = res.get("ids") or []
# #     distances = res.get("distances") or []

# #     # flatten if nested
# #     if docs and isinstance(docs[0], list):
# #         docs = docs[0]
# #         metas = metas[0] if metas and isinstance(metas[0], list) else metas
# #         ids = ids[0] if ids and isinstance(ids[0], list) else ids
# #         distances = distances[0] if distances and isinstance(distances[0], list) else distances

# #     hits: List[SearchHit] = []
# #     for i, (doc, meta, idd) in enumerate(zip(docs, metas, ids)):
# #         score = None
# #         try:
# #             # try to extract score from distances if present (many stores return distance)
# #             if distances:
# #                 score = float(distances[i])
# #         except Exception:
# #             score = None

# #         # try to expose canonical chunk info in the hit for frontend convenience
# #         chunk_id = None
# #         paper_id = None
# #         try:
# #             if isinstance(meta, dict):
# #                 chunk_id = meta.get("chunk_id") or meta.get("id") or idd
# #                 paper_id = meta.get("paper_id") or meta.get("pid") or None
# #         except Exception:
# #             pass

# #         # keep meta as-is but avoid huge embeddings leaking to frontend
# #         if isinstance(meta, dict) and "embedding" in meta:
# #             meta = dict(meta)
# #             meta.pop("embedding", None)

# #         hits.append(SearchHit(
# #             id=str(idd),
# #             text=str(doc or ""),
# #             score=score,
# #             meta=meta,
# #             chunk_id=chunk_id,
# #             paper_id=paper_id
# #         ))

# #     return SearchResponse(query=q, k=int(req.k or 6), hits=hits)


# # # -----------------------------
# # # /api/summary - synchronous, idempotent
# # # -----------------------------
# # @app.post("/api/summary", tags=["summaries"], response_model=SummaryResult, summary="Create or fetch summary")
# # def api_create_summary(req: SummaryRequest):
# #     # must provide q or paper_id
# #     if not (req.q or req.paper_id):
# #         raise HTTPException(status_code=400, detail="Provide 'q' or 'paper_id'")

# #     req_dict = req.dict()
# #     summary_id = summary_id_for_request(req_dict)
# #     existing = load_summary_record(summary_id)
# #     if existing:
# #         # Return cached result (idempotent)
# #         return SummaryResult(**existing)

# #     # Build the query text used for embedding / retrieval
# #     if req.q:
# #         query_text = req.q.strip()
# #     else:
# #         query_text = f"summarize paper {req.paper_id}"

# #     # embed + retrieval
# #     emb = batch_embed_records("query:" + query_text, query_text)
# #     if not emb:
# #         raise HTTPException(status_code=500, detail="Embedding failed")
# #     emb_list = list(emb)

# #     # choose retrieval method: use CHROMA_COLL.query directly for speed
# #     coll = _get_coll_or_503()
# #     try:
# #         # prefer safe_query wrapper to handle versions
# #         res = safe_query(coll, emb_list, n_results=int(req.k or 6), where=( {"paper_id":{"$eq": req.paper_id}} if req.paper_id else None),
# #                          include=["documents", "metadatas", "ids"])
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=f"retrieval failed: {e}")

# #     docs = res.get("documents") or []
# #     metas = res.get("metadatas") or []
# #     ids = res.get("ids") or []

# #     # normalize nested
# #     if docs and isinstance(docs[0], list):
# #         docs = docs[0]; metas = metas[0] if metas else metas; ids = ids[0] if ids else ids

# #     # build support list and used_chunk_ids
# #     support = []
# #     used_chunk_ids = []
# #     for d, m, i in zip(docs, metas, ids):
# #         # keep doc text, and a normalized small meta (avoid large embeddings)
# #         small_meta = m if isinstance(m, dict) else {}
# #         small_meta_copy = dict(small_meta)
# #         small_meta_copy.pop("embedding", None)
# #         # attempt to get canonical chunk id
# #         chunk_id = small_meta_copy.get("chunk_id") or small_meta_copy.get("id") or i
# #         used_chunk_ids.append(chunk_id)
# #         support.append({"id": str(i), "text": str(d or ""), "meta": small_meta_copy})

# #     # build prompt using your helper (keeps provenance)
# #     try:
# #         prompt, prov = _build_prompt_and_prov(support, query_text)
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=f"prompt build failed: {e}")

# #     # call LLM synchronously (can be slow, but idempotent)
# #     try:
# #         llm_out = llm_generate(prompt, max_tokens=600)
# #         answer = llm_out or ""
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=f"LLM generation failed: {e}")

# #     now_ts = time.time()
# #     result_payload = {
# #         "summary_id": summary_id,
# #         "request": req_dict,
# #         "answer": answer,
# #         "rag": {
# #             "support": prov,
# #             "used_chunk_ids": used_chunk_ids
# #         },
# #         "created_at": now_ts
# #     }

# #     # persist summary for idempotency
# #     try:
# #         save_summary_record(summary_id, result_payload)
# #     except Exception:
# #         # persist failure shouldn't prevent returning result
# #         pass

# #     return SummaryResult(**result_payload)


# # @app.get("/api/summary/{summary_id}", tags=["summaries"], response_model=SummaryResult, summary="Get a saved summary")
# # def api_get_summary(summary_id: str):
# #     rec = load_summary_record(summary_id)
# #     if not rec:
# #         raise HTTPException(status_code=404, detail="summary not found")
# #     return SummaryResult(**rec)


# # # Minimal topics endpoint stub (non-blocking)
# # @app.get("/api/topics", tags = ['summaries'])
# # def api_topics(k: int = 200):
# #     """Return a light sample of metadata to allow simple topic UIs (no UMAP here)."""
# #     try:
# #         raw = _safe_collection_get_all(CHROMA_COLL)
# #         metas = raw.get("metadatas", []) or []
# #         ids = raw.get("ids", []) or []
# #         sample = []
# #         for idx, meta in enumerate(metas):
# #             if not isinstance(meta, dict):
# #                 continue
# #             pid = meta.get("paper_id") or meta.get("paper") or None
# #             if pid:
# #                 sample.append({"id": ids[idx] if idx < len(ids) else None, "meta": meta})
# #             if len(sample) >= k:
# #                 break
# #         return {"n_sample": len(sample), "sample": sample}
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))

