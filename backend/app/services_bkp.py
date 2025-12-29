# import logging
# from threading import Lock
# from typing import List, Dict, Any, Optional

# from backend.app.schemas import PaperMeta, PapersList, PaperChunksResponse, ChunkResponse, CanonicalChunk
# from backend.app import chunks_fs, papers_fs
# from shared import chroma_helpers

# logger = logging.getLogger("app.services")


# # from fastapi import HTTPException
# # def get_storage():
# #     # prefer app.state if available, else raise
# #     st = getattr(app, "state", None) and getattr(app.state, "storage", None)
# #     if not st:
# #         raise RuntimeError("storage adapter not initialized")
# #     return st


# _cache_lock = Lock()
# _papers_cache: List[PaperMeta] = []
# _papers_cache_loaded: bool = False



# # ------------------
# # Normalization helpers (thin wrappers)
# # ------------------
# def _normalize_paper_meta_dict(raw: Dict[str, Any]) -> Optional[PaperMeta]:
#     """
#     Turn a raw dict into a PaperMeta instance, defensive about malformed input.
#     Keeps coercion rules centralized here (thin).
#     """
#     if not raw or not isinstance(raw, dict):
#         return None
#     try:
#         # assume PaperMeta is a pydantic model or similar with parse_obj
#         pm = PaperMeta.parse_obj(raw) if hasattr(PaperMeta, "parse_obj") else PaperMeta(**raw)
#         return pm
#     except Exception:
#         logger.debug("failed to coerce paper meta: %r", raw)
#         return None


# def normalize_papers_list(papers_raw: Optional[List[Dict[str, Any]]], dedupe: bool = True) -> List[PaperMeta]:
#     """
#     Convert a list of raw dicts (as returned by papers_fs or chroma helpers)
#     into validated PaperMeta objects. Keeps first occurrence when dedupe=True.
#     """
#     if not papers_raw:
#         return []

#     out: List[PaperMeta] = []
#     seen = set()
#     for idx, r in enumerate(papers_raw):
#         try:
#             pm = _normalize_paper_meta_dict(r)
#             if pm is None:
#                 continue
#             pid = (pm.paper_id or "").strip()
#             if dedupe and pid:
#                 if pid in seen:
#                     continue
#                 seen.add(pid)
#             out.append(pm)
#         except Exception:
#             logger.exception("error normalizing paper at index=%d", idx)
#             continue
#     return out


# # ------------------
# # Cache control (single owner: this module)
# # ------------------
# def invalidate_papers_cache() -> None:
#     global _papers_cache, _papers_cache_loaded
#     with _cache_lock:
#         _papers_cache = []
#         _papers_cache_loaded = False
#     logger.info("papers cache invalidated (memory only)")


# def set_papers_cache(papers: List[PaperMeta], persist: bool = False) -> None:
#     """
#     Replace in-memory cache; optionally persist via papers_fs.write_papers_cache(...)
#     Note: persistence is delegated to papers_fs to keep IO single-sourced.
#     """
#     global _papers_cache, _papers_cache_loaded
#     with _cache_lock:
#         _papers_cache = list(papers)
#         _papers_cache_loaded = True

#     logger.info("papers cache updated in memory (items=%d) persist=%s", len(papers), persist)
#     if persist:
#         try:
#             # papers_fs should implement an atomic writer: write_papers_cache(path_or_list)
#             if hasattr(papers_fs, "write_papers_cache"):
#                 papers_fs.write_papers_cache([p.dict() for p in papers])
#             else:
#                 # best-effort fallback (should not be necessary if FS helpers exist)
#                 logger.debug("papers_fs.write_papers_cache not found; skipping persist")
#         except Exception:
#             logger.exception("failed to persist papers cache via papers_fs")


# # ------------------
# # Listing / refresh (very thin)
# # ------------------
# def refresh_papers_cache_from_fs() -> List[PaperMeta]:
#     """
#     Ask papers_fs for the canonical on-disk list and normalize it.
#     This function does NOT know about JSON/JSONL; papers_fs does.
#     """
#     try:
#         raw = papers_fs.list_papers_from_fs() if hasattr(papers_fs, "list_papers_from_fs") else []
#         normalized = normalize_papers_list(raw)
#         with _cache_lock:
#             global _papers_cache, _papers_cache_loaded
#             _papers_cache = normalized
#             _papers_cache_loaded = True
#         logger.info("papers cache refreshed from FS (items=%d)", len(normalized))
#         return list(normalized)
#     except Exception:
#         logger.exception("papers_fs.list_papers_from_fs failed")
#         return []


# def list_papers(chroma_client: Optional[Any] = None) -> List[PaperMeta]:
#     """
#     API-facing list of papers. Precedence:
#       1) in-memory cache
#       2) filesystem fast-path (papers_fs)
#       3) chroma scan (chroma_helpers.list_papers_from_chroma)
#     The service layer only orchestrates these sources and updates the in-memory cache.
#     """
#     # 1) in-memory
#     with _cache_lock:
#         if _papers_cache_loaded and _papers_cache:
#             logger.debug("list_papers -> returning in-memory cache (items=%d)", len(_papers_cache))
#             return list(_papers_cache)

#     # 2) filesystem fast-path (canonical on-disk representation)
#     fs_list = refresh_papers_cache_from_fs()
#     if fs_list:
#         logger.debug("list_papers -> returning FS cache (items=%d)", len(fs_list))
#         return fs_list

#     # 3) chroma fallback (ask chroma_helpers; do not unpack here)
#     try:
#         if hasattr(chroma_helpers, "list_papers_from_chroma"):
#             chroma_list_raw = chroma_helpers.list_papers_from_chroma(chroma_client)
#         else:
#             # best-effort: try get_papers_from_chroma helper name alternatives
#             chroma_list_raw = chroma_helpers._list_papers_from_chroma(chroma_client) if hasattr(chroma_helpers, "_list_papers_from_chroma") else []

#         normalized = normalize_papers_list(chroma_list_raw)
#         if normalized:
#             set_papers_cache(normalized, persist=True)
#         return normalized
#     except Exception:
#         logger.exception("list_papers -> chroma scan failed")
#         return []


# # ------------------
# # Chunk accessors
# # ------------------
# def _normalize_upstream_to_canonical(upstream: Dict[str, Any], paper_id: str) -> Optional[CanonicalChunk]:
#     """
#     Use chunks_fs.normalize_chunk as single source of truth for canonical chunk shaping.
#     """
#     try:
#         if hasattr(chunks_fs, "normalize_chunk"):
#             return chunks_fs.normalize_chunk(upstream, paper_id=paper_id, default_index=0)
#         # fallback: attempt minimal coercion
#         return CanonicalChunk(
#             chunk_id=upstream.get("chunk_id") or upstream.get("id"),
#             paper_id=paper_id,
#             text=str(upstream.get("text") or ""),
#             chunk_index=int(upstream.get("chunk_index") or 0),
#             char_len=int(upstream.get("char_len") or len(str(upstream.get("text") or ""))),
#             header_path=upstream.get("header_path"),
#             pages=upstream.get("pages"),
#             meta=upstream.get("meta") or {},
#         )
#     except Exception:
#         logger.exception("normalize upstream chunk failed for paper=%s id=%s", paper_id, upstream.get("chunk_id") or upstream.get("id"))
#         return None


# def _chunks_to_api_chunks(canonical_chunks: List[CanonicalChunk]) -> List[ChunkResponse]:
#     out: List[ChunkResponse] = []
#     for cc in canonical_chunks:
#         out.append(ChunkResponse(
#             chunk_id=cc.chunk_id, text=cc.text, chunk_index=cc.chunk_index,
#             char_len=cc.char_len, header_path=cc.header_path, pages=cc.pages, meta=cc.meta
#         ))
#     return out


# def get_paper_chunks(paper_id: str, offset: int = 0, limit: int = 200) -> PaperChunksResponse:
#     st = get_storage()
#     try:
#         res = st.list_chunks(paper_id=paper_id, limit=limit, offset=offset)
#         raw_chunks = res.get("chunks", [])
#         total = int(res.get("n", len(raw_chunks)))
#     except Exception as e:
#         logger.exception("storage.list_chunks failed, falling back to FS: %s", e)
#         # fallback: use chunks_fs directly (as a last resort)
#         raw_chunks = chunks_fs.read_chunks_as_models(paper_id)
#         raw_chunks = [r.model_dump() if hasattr(r,"model_dump") else (r.dict() if hasattr(r,"dict") else r) for r in raw_chunks]
#         total = len(raw_chunks)

        
# def get_paper_chunks(paper_id: str, offset: int = 0, limit: int = 200, chroma_client: Optional[Any] = None) -> PaperChunksResponse:
#     """
#     Return normalized chunks for a paper. Strategy:
#       - try chroma_helpers.get_chunks_for_paper (single canonical accessor)
#       - else try chunks_fs.read_chunks_as_models (FS)
#       - else return empty list
#     All normalization happens via chunks_fs.normalize_chunk (or fallback).
#     """
#     upstream_docs: List[Dict[str, Any]] = []

#     # Primary: ask chroma_helpers for canonical chunk dicts
#     try:
#         if hasattr(chroma_helpers, "get_chunks_for_paper"):
#             # helper should accept client and return list[dict] with keys chunk_id,text,meta...
#             upstream_docs = chroma_helpers.get_chunks_for_paper(paper_id, client=chroma_client)
#             if not isinstance(upstream_docs, list):
#                 upstream_docs = list(upstream_docs or [])
#     except Exception:
#         logger.debug("chroma_helpers.get_chunks_for_paper failed for %s", paper_id)

#     # FS fallback if chroma returned nothing
#     if not upstream_docs:
#         try:
#             if hasattr(chunks_fs, "read_chunks_as_models"):
#                 cached = chunks_fs.read_chunks_as_models(paper_id)
#                 # read_chunks_as_models may return CanonicalChunk instances or dicts
#                 if cached:
#                     # normalize into dict-like upstreams
#                     for cc in cached:
#                         if hasattr(cc, "dict"):
#                             upstream_docs.append(cc.dict())
#                         elif isinstance(cc, dict):
#                             upstream_docs.append(cc)
#                         else:
#                             # attempt attribute access
#                             upstream_docs.append({
#                                 "chunk_id": getattr(cc, "chunk_id", None),
#                                 "text": getattr(cc, "text", None),
#                                 "chunk_index": getattr(cc, "chunk_index", None),
#                                 "char_len": getattr(cc, "char_len", None),
#                                 "header_path": getattr(cc, "header_path", None),
#                                 "pages": getattr(cc, "pages", None),
#                                 "meta": getattr(cc, "meta", None),
#                             })
#                     logger.debug("loaded %d chunks from FS cache for %s", len(upstream_docs), paper_id)
#         except Exception:
#             logger.debug("chunks_fs.read_chunks_as_models failed for %s", paper_id)

#     # If still empty, return empty but stable response
#     canonical_list: List[CanonicalChunk] = []
#     for u in upstream_docs:
#         # ensure id/text present
#         u2 = dict(u or {})
#         if "chunk_id" not in u2 and "id" in u2:
#             u2["chunk_id"] = u2["id"]
#         cc = _normalize_upstream_to_canonical(u2, paper_id=paper_id)
#         if cc:
#             canonical_list.append(cc)

#     # sort stable by chunk_index
#     canonical_list.sort(key=lambda x: int(x.chunk_index or 0))

#     total = len(canonical_list)
#     paged = canonical_list[offset: offset + limit]
#     chunk_objs = _chunks_to_api_chunks(paged)
#     return PaperChunksResponse(paper_id=paper_id, total=total, chunks=chunk_objs)


# def get_chunk(paper_id: str, chunk_id: str, chroma_client: Optional[Any] = None) -> Optional[ChunkResponse]:
#     """
#     Return a single chunk. Strategy:
#       1) try chroma_helpers.get_chunk_by_id (if provided)
#       2) try chunks_fs.get_chunk_text (FS)
#       3) try a raw chroma scan via chroma_helpers.list_collection_documents (last resort)
#     """
#     # 1) chroma direct
#     try:
#         if hasattr(chroma_helpers, "get_chunk_by_id"):
#             upstream = chroma_helpers.get_chunk_by_id(chunk_id, client=chroma_client)
#             if upstream:
#                 cc = _normalize_upstream_to_canonical(upstream, paper_id=paper_id)
#                 if cc:
#                     return ChunkResponse(
#                         chunk_id=cc.chunk_id, text=cc.text, chunk_index=cc.chunk_index,
#                         char_len=cc.char_len, header_path=cc.header_path, pages=cc.pages, meta=cc.meta
#                     )
#     except Exception:
#         logger.debug("chroma_helpers.get_chunk_by_id failed for id=%s", chunk_id)

#     # 2) FS
#     try:
#         if hasattr(chunks_fs, "get_chunk_text"):
#             txt = chunks_fs.get_chunk_text(paper_id, chunk_id)
#             if txt is not None:
#                 cc = _normalize_upstream_to_canonical({"chunk_id": chunk_id, "text": txt}, paper_id=paper_id)
#                 if cc:
#                     return ChunkResponse(
#                         chunk_id=cc.chunk_id, text=cc.text, chunk_index=cc.chunk_index,
#                         char_len=cc.char_len, header_path=cc.header_path, pages=cc.pages, meta=cc.meta
#                     )
#     except Exception:
#         logger.debug("chunks_fs.get_chunk_text failed for %s/%s", paper_id, chunk_id)

#     # 3) last resort: raw chroma scan (ask chroma_helpers for a raw collection dump)
#     try:
#         if hasattr(chroma_helpers, "scan_collection_for_id"):
#             upstream = chroma_helpers.scan_collection_for_id(chunk_id, client=chroma_client)
#             if upstream:
#                 cc = _normalize_upstream_to_canonical(upstream, paper_id=paper_id)
#                 if cc:
#                     return ChunkResponse(
#                         chunk_id=cc.chunk_id, text=cc.text, chunk_index=cc.chunk_index,
#                         char_len=cc.char_len, header_path=cc.header_path, pages=cc.pages, meta=cc.meta
#                     )
#     except Exception:
#         logger.debug("chroma raw scan failed for chunk id=%s", chunk_id)

#     return None







# # # ------------------
# # # Dev / seeding helpers (use FS helpers; keep service-level orchestration only)
# # # ------------------
# # def seed_dev_fixture(n_papers: int = 8, min_chunks: int = 6, max_chunks: int = 16, write_files: bool = True) -> List[PaperMeta]:
# #     """
# #     Lightweight dev seeding that delegates all writes to papers_fs / chunks_fs.
# #     Returns the normalized PaperMeta list.
# #     """
# #     out: List[PaperMeta] = []

# #     for i in range(n_papers):
# #         pid = f"dev-paper-{i}"
# #         meta = {
# #             "paper_id": pid,
# #             "title": f"Dev Paper {i}",
# #             "authors": ["Dev"],
# #             "n_chunks": min_chunks + (i % (max_chunks - min_chunks + 1)),
# #             "preview": f"preview {i}"
# #         }
# #         if write_files:
# #             try:
# #                 if hasattr(papers_fs, "save_paper_metadata_to_fs"):
# #                     papers_fs.save_paper_metadata_to_fs(pid, meta)
# #                 if hasattr(chunks_fs, "write_chunks_jsonl"):
# #                     chunk_recs = chunks_fs.chunks_to_records(title=meta["title"], paper_id=pid,
# #                                                              chunks=[{"text": f"chunk {j} for {pid}"} for j in range(meta["n_chunks"])])
# #                     chunks_fs.write_chunks_jsonl(pid, chunk_recs)

# #                 # path = chunk_file_for(paper_id)
# #                 # logger.info("wrote chunks jsonl %s (%s bytes)", path, path.stat().st_size if path.exists() else "MISSING")

# #             except Exception:
# #                 logger.exception("dev fixture write failed for %s", pid)
# #         pm = _normalize_paper_meta_dict(meta)
# #         if pm:
# #             out.append(pm)

# #     # update service cache (persist via papers_fs if available)
# #     set_papers_cache(out, persist=True)
# #     logger.info("seeded dev fixture %d papers", len(out))
# #     return out


# # import logging

# # logger = logging.getLogger("embedding")
# # logger.addHandler(logging.StreamHandler())
# # logger.setLevel(logging.INFO)

# # from shared.chroma_helpers import get_or_create_collection, CHROMA_CHUNKS_COLL
# # from typing import List, Dict, Optional, Any, Callable, Tuple

# # def search_chunks(query_embedding: List[float], n_results: int = 10, where: Optional[Dict[str, Any]] = None, collection_name: str = CHROMA_CHUNKS_COLL) -> List[Dict[str, Any]]:
# #     """
# #     Query by embedding. Returns list of hits with chunk_id, preview, meta, score (distance).
# #     """
# #     client = None
# #     coll = get_or_create_collection(client, collection_name)
# #     try:
# #         out = coll.query(query_embeddings=[list(map(float, query_embedding))], n_results=n_results, where=where or {}, include=["documents", "metadatas", "distances", "ids"])
# #     except Exception as e:
# #         logger.warning("search_chunks query error: %s", e)
# #         return []
# #     hits = []
# #     # out keys contain nested lists per query
# #     if not out or "ids" not in out:
# #         return []
# #     ids_batch = out.get("ids", [[]])[0]
# #     docs_batch = out.get("documents", [[]])[0]
# #     metas_batch = out.get("metadatas", [[]])[0]
# #     dists_batch = out.get("distances", [[]])[0]
# #     for i, cid in enumerate(ids_batch):
# #         hits.append({
# #             "chunk_id": cid,
# #             "preview": docs_batch[i] if i < len(docs_batch) else "",
# #             "meta": metas_batch[i] if i < len(metas_batch) else {},
# #             "score": dists_batch[i] if i < len(dists_batch) else None
# #         })
# #     return hits



# # # -------------------------
# # # Normalizers for query/get outputs (handle API shape differences)
# # # -------------------------
# # def _normalize_query_result(res: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
# #     """
# #     Normalize different shapes returned by client.query() or collection.get().
# #     Returns (documents, metadatas, ids) as flat lists.
# #     """
# #     docs = res.get("documents") or []
# #     metas = res.get("metadatas") or []
# #     ids = res.get("ids") or []

# #     # flatten nested lists (some versions return nested per-query lists)
# #     if docs and isinstance(docs[0], list):
# #         docs = docs[0]
# #     if metas and isinstance(metas[0], list):
# #         metas = metas[0]
# #     if ids and isinstance(ids[0], list):
# #         ids = ids[0]

# #     # guarantee ids exist (fallback to meta keys)
# #     if not ids:
# #         ids = []
# #         for i, m in enumerate(metas):
# #             candidate = None
# #             if isinstance(m, dict):
# #                 candidate = m.get("chunk_id") or m.get("id") or m.get("paper_id")
# #             ids.append(candidate or f"row_{i}")

# #     # ensure same length
# #     L = max(len(docs), len(metas), len(ids))
# #     # pad lists defensively
# #     docs = docs + [""] * (L - len(docs))
# #     metas = metas + ([{}] * (L - len(metas)))
# #     ids = ids + ([f"row_{i}" for i in range(len(ids), L)])

# #     return docs, metas, ids




# # # # query.py

# # # import argparse
# # # from pipeline.embedding.engine import embed_text
# # # from backend.app.services import search_chunks

# # # def main():
# # #     parser = argparse.ArgumentParser(description="Query Chroma using text.")
# # #     parser.add_argument("query", help="Query string")
# # #     parser.add_argument("--n", type=int, default=10, help="Number of results")
# # #     parser.add_argument("--collection", default="chunks", help="Chroma collection name")
# # #     args = parser.parse_args()

# # #     embedding = embed_text([args.query])[0]
# # #     results = search_chunks(query_embedding=embedding, n_results=args.n, collection_name=args.collection)

# # #     print(f"[query] Top {args.n} results for: {args.query}")
# # #     for r in results:
# # #         meta = r["meta"]
# # #         print(f" - [{r['score']:.3f}] {meta.get('paper_id')}:{meta.get('chunk_index')} → {r['preview'][:100]}")

# # # if __name__ == "__main__":
# # #     main()
