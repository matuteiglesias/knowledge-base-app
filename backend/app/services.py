# backend/app/services.py
"""
Services layer for Paper-KB.

Principles:
 - adapter-first: every public function takes `storage` and calls only adapter methods.
 - small, testable functions that orchestrate and normalize using chunks_fs.normalize_chunk.
 - safe FS fallbacks only if the adapter lacks an implementation (migration path).
 - minimal side-effects (in-memory cache) and clear failure modes.

Expected StorageAdapter methods (recommended):
 - list_papers() -> List[Dict] or List[PaperMeta-like dicts]
 - list_chunks(paper_id, offset=0, limit=200, q=None) -> {"n": int, "chunks": [ {id,text,meta,...}, ... ]}
 - get_chunk(paper_id, chunk_id) -> Dict or None
 - semantic_search(q, k, paper_id=None) -> List[{"id","text","meta","score"}]
 - load_caches(), counts(), maybe_persist(), close(), save_summary_record(...)
"""
from __future__ import annotations
import logging
from threading import Lock
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import uuid

from backend.app import chunks_fs, papers_fs
from backend.app.schemas import (
    PaperMeta,
    PapersList,
    PaperChunksResponse,
    ChunkResponse,
    CanonicalChunk,
    SearchResponse,
    SearchHit,
    SummaryRequest,
    SummaryResult,
)
from fastapi import HTTPException
from backend.app.storage_adapter import StorageAdapter
logger = logging.getLogger("backend.app.services")

# --- small module-level cache for papers list (memory only) ---
_cache_lock = Lock()
_papers_cache: List[PaperMeta] = []
_papers_cache_loaded: bool = False
_papers_cache_ts: Optional[float] = None
_PAPERS_CACHE_TTL = 60  # seconds, simple TTL to avoid stale forever


# --- custom exceptions for clearer control flow ---
class NotFoundError(Exception):
    pass


# -------------------------
# Helpers: normalization + small utilities
# -------------------------
def _normalize_paper_meta(raw: Dict[str, Any]) -> Optional[PaperMeta]:
    if not raw or not isinstance(raw, dict):
        return None
    try:
        # PaperMeta is a pydantic model; parse_obj keeps things tolerant
        if hasattr(PaperMeta, "parse_obj"):
            return PaperMeta.parse_obj(raw)
        return PaperMeta(**raw)
    except Exception:
        logger.debug("failed coercing paper meta: %r", raw)
        return None


def _normalize_chunks_from_upstream(upstreams: List[Dict[str, Any]], paper_id: str) -> List[CanonicalChunk]:
    out: List[CanonicalChunk] = []
    for u in upstreams:
        try:
            # upstream may use "id" alias
            if "chunk_id" not in u and "id" in u:
                u = dict(u, chunk_id=u.get("id"))
            # use chunks_fs.normalize_chunk as single source of truth
            cc = None
            if hasattr(chunks_fs, "normalize_chunk"):
                cc = chunks_fs.normalize_chunk(u, paper_id=paper_id)
            else:
                # fallback coercion
                cc = CanonicalChunk(
                    chunk_id=str(u.get("chunk_id") or u.get("id") or ""),
                    paper_id=paper_id,
                    text=str(u.get("text") or u.get("preview") or ""),
                    chunk_index=int(u.get("chunk_index") or u.get("meta", {}).get("chunk_index") or 0),
                    char_len=int(u.get("char_len") or len(u.get("text") or "")),
                    header_path=u.get("meta", {}).get("header_path") if u.get("meta") else None,
                    pages=u.get("meta", {}).get("pages") if u.get("meta") else None,
                    meta=u.get("meta") or {},
                )
            if cc:
                out.append(cc)
        except Exception:
            logger.exception("failed normalize upstream chunk for paper=%s upstream=%s", paper_id, u)
            continue
    return out


def _canonical_to_chunkresponse(cc: CanonicalChunk) -> ChunkResponse:
    return ChunkResponse(
        chunk_id=cc.chunk_id,
        text=cc.text,
        chunk_index=cc.chunk_index,
        char_len=cc.char_len,
        header_path=cc.header_path,
        pages=cc.pages,
        meta=cc.meta,
    )


# -------------------------
# Papers: refresh / list (adapter-first)
# -------------------------
def refresh_papers_cache(storage: StorageAdapter) -> List[PaperMeta]:
    """
    Force reload papers list from adapter (or FS fallback).
    Returns normalized PaperMeta list and updates in-memory cache.
    """
    global _papers_cache, _papers_cache_loaded, _papers_cache_ts
    try:
        # adapter expected to return list[dict]
        raw = []
        if hasattr(storage, "list_papers"):
            raw = storage.list_papers() or []
        else:
            raise NotImplementedError("storage.list_papers not implemented")
    except Exception as e:
        logger.exception("storage.list_papers failed, falling back to papers_fs: %s", e)
        try:
            raw = papers_fs.list_papers_from_fs() or []
        except Exception:
            logger.exception("papers_fs.list_papers_from_fs failed")
            raw = []

    normalized: List[PaperMeta] = []
    seen = set()
    for r in (raw or []):
        pm = _normalize_paper_meta(r)
        if pm is None:
            continue
        pid = (pm.paper_id or "").strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        normalized.append(pm)

    with _cache_lock:
        _papers_cache = normalized
        _papers_cache_loaded = True
        _papers_cache_ts = datetime.utcnow().timestamp()
    logger.info("refreshed papers cache (n=%d)", len(normalized))
    return normalized


def list_papers(storage: StorageAdapter, prefer_cache: bool = True) -> List[PaperMeta]:
    """
    Return list of papers. Order of precedence:
      1) in-memory cache (if fresh)
      2) storage.list_papers()
      3) FS fallback (papers_fs)
    """
    global _papers_cache, _papers_cache_loaded, _papers_cache_ts

    with _cache_lock:
        if prefer_cache and _papers_cache_loaded and _papers_cache:
            age = (datetime.utcnow().timestamp() - (_papers_cache_ts or 0)) if _papers_cache_ts else None
            if age is not None and age < _PAPERS_CACHE_TTL:
                logger.debug("list_papers -> returning in-memory cache (age=%s s, n=%d)", age, len(_papers_cache))
                return list(_papers_cache)

    # try adapter
    try:
        if hasattr(storage, "list_papers"):
            raw = storage.list_papers() or []
            normalized = []
            seen = set()
            for r in raw:
                pm = _normalize_paper_meta(r)
                if pm is None:
                    continue
                pid = (pm.paper_id or "").strip()
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                normalized.append(pm)
            if normalized:
                with _cache_lock:
                    _papers_cache = normalized
                    _papers_cache_loaded = True
                    _papers_cache_ts = datetime.utcnow().timestamp()
                return normalized
    except Exception:
        logger.exception("storage.list_papers failed; will try FS fallback")

    # FS fallback
    return refresh_papers_cache(storage)


# -------------------------
# Chunk accessors
# -------------------------
def get_paper_chunks(storage: StorageAdapter, paper_id: str, offset: int = 0, limit: int = 200, q: Optional[str] = None) -> PaperChunksResponse:
    """
    Primary: ask storage.list_chunks which should support server-side pagination.
    Adapter must return {"n": int, "chunks": [ {id,text,meta}, ... ]}.
    If adapter lacks list_chunks, fall back to FS (chunks_fs.read_chunks_as_models) and implement offset/limit there.
    """
    # validate
    if offset < 0 or limit <= 0:
        raise HTTPException(status_code=400, detail="invalid offset/limit")

    # Try adapter pagination
    try:
        if hasattr(storage, "list_chunks"):
            res = storage.list_chunks(paper_id=paper_id, offset=offset, limit=limit, q=q)
            if not isinstance(res, dict):
                raise ValueError("storage.list_chunks must return dict with 'n' and 'chunks'")
            raw_chunks = res.get("chunks", []) or []
            total = int(res.get("n", len(raw_chunks)))
            # normalize upstream chunk dicts to canonical
            canonical = _normalize_chunks_from_upstream(raw_chunks, paper_id)
            # ensure stable sort by chunk_index then return API objects
            canonical.sort(key=lambda x: int(x.chunk_index or 0))
            paged = canonical  # adapter already paginated, so trust it
            return PaperChunksResponse(paper_id=paper_id, total=total, chunks=[_canonical_to_chunkresponse(c) for c in paged])
    except Exception as e:
        logger.exception("storage.list_chunks failed for %s: %s", paper_id, e)

    # FS fallback: try to use an indexed reader (chunks_fs.get_chunk_by_id or read_chunks_as_models)
    try:
        if hasattr(chunks_fs, "read_chunks_as_models"):
            models = chunks_fs.read_chunks_as_models(paper_id) or []
            # models may be CanonicalChunk instances or dicts; coerce minimally to dict then normalize
            upstreams = []
            for m in models:
                if hasattr(m, "model_dump"):
                    upstreams.append(m.model_dump())
                elif hasattr(m, "dict"):
                    upstreams.append(m.dict())
                elif isinstance(m, dict):
                    upstreams.append(m)
                else:
                    upstreams.append({
                        "chunk_id": getattr(m, "chunk_id", None),
                        "text": getattr(m, "text", None),
                        "chunk_index": getattr(m, "chunk_index", None),
                        "char_len": getattr(m, "char_len", None),
                        "meta": getattr(m, "meta", None),
                    })
            total = len(upstreams)
            # apply q filter if requested (simple substring on text)
            if q:
                qlow = q.lower()
                upstreams = [u for u in upstreams if qlow in ( (u.get("text") or u.get("preview") or "").lower() )]
                total = len(upstreams)
            # slice (source didn't support pagination)
            slice_upstreams = upstreams[offset: offset + limit]
            canonical = _normalize_chunks_from_upstream(slice_upstreams, paper_id)
            canonical.sort(key=lambda x: int(x.chunk_index or 0))
            return PaperChunksResponse(paper_id=paper_id, total=total, chunks=[_canonical_to_chunkresponse(c) for c in canonical])
    except Exception:
        logger.exception("chunks_fs fallback failed for %s", paper_id)

    # Nothing found -> empty stable response
    return PaperChunksResponse(paper_id=paper_id, total=0, chunks=[])


def get_chunk(storage, paper_id: str, chunk_id: str) -> Optional[ChunkResponse]:
    """
    Adapter-first: call storage.get_chunk(...) or storage.get_chunk_by_id(...)
    Fallback to chunks_fs.get_chunk_text().
    """
    try:
        if hasattr(storage, "get_chunk"):
            upstream = storage.get_chunk(paper_id=paper_id, chunk_id=chunk_id)
            if upstream:
                # normalize upstream to canonical
                canonical = _normalize_chunks_from_upstream([upstream], paper_id=paper_id)
                if canonical:
                    return _canonical_to_chunkresponse(canonical[0])
        elif hasattr(storage, "get_chunk_by_id"):
            upstream = storage.get_chunk_by_id(chunk_id, paper_id=paper_id)
            if upstream:
                canonical = _normalize_chunks_from_upstream([upstream], paper_id=paper_id)
                if canonical:
                    return _canonical_to_chunkresponse(canonical[0])
    except Exception:
        logger.exception("storage.get_chunk failed for %s/%s", paper_id, chunk_id)

    # FS fallback
    try:
        if hasattr(chunks_fs, "get_chunk_text"):
            txt = chunks_fs.get_chunk_text(paper_id, chunk_id)
            if txt is not None:
                canonical = _normalize_chunks_from_upstream([{"chunk_id": chunk_id, "text": txt}], paper_id=paper_id)
                if canonical:
                    return _canonical_to_chunkresponse(canonical[0])
    except Exception:
        logger.exception("chunks_fs.get_chunk_text fallback failed for %s/%s", paper_id, chunk_id)

    return None


# -------------------------
# Search (semantic) - adapter-driven
# -------------------------
def search(storage, q: str, k: int = 6, paper_id: Optional[str] = None) -> SearchResponse:
    """
    Delegate to storage.semantic_search or storage.search (adapter-defined).
    Adapter must return list of hits with at least id/text/meta/score keys.
    """
    if not q:
        raise HTTPException(status_code=400, detail="empty query")

    try:
        if hasattr(storage, "semantic_search"):
            hits = storage.semantic_search(q=q, k=k, paper_id=paper_id) or []
        elif hasattr(storage, "search"):
            hits = storage.search(q=q, k=k, paper_id=paper_id) or []
        else:
            raise NotImplementedError("storage.semantic_search not implemented")
    except Exception:
        logger.exception("storage.semantic_search failed; returning empty hits")
        hits = []

    normalized_hits: List[SearchHit] = []
    for h in hits:
        try:
            # support both 'id' and 'chunk_id'
            hid = h.get("id") or h.get("chunk_id") or h.get("chunk_id") or ""
            normalized_hits.append(SearchHit(
                id=hid,
                text=h.get("text") or h.get("preview") or "",
                score=float(h.get("score")) if h.get("score") is not None else None,
                meta=h.get("meta") or {},
                chunk_id=h.get("chunk_id") or hid,
                paper_id=h.get("meta", {}).get("paper_id") or paper_id
            ))
        except Exception:
            logger.debug("skipping malformed hit: %r", h)
            continue

    return SearchResponse(query=q, k=k, hits=normalized_hits)


# -------------------------
# Summaries (lightweight job API)
# -------------------------
def _llm_summarize_heuristic(texts: List[str], req: SummaryRequest) -> str:
    """
    Minimal deterministic summarizer for fallback: concatenates and truncates.
    Replace with real LLM call (openai/etc.) in a controlled way.
    """
    joined = "\n\n".join(t.strip() for t in texts if t)
    max_chars = 2000
    if len(joined) <= max_chars:
        return joined
    return joined[:max_chars].rsplit("\n", 1)[0] + " ..."

def create_summary_task(storage, req: SummaryRequest, background_tasks: Optional[Any] = None) -> str:
    """
    Create and optionally queue a summary job.
    - If background_tasks provided (FastAPI BackgroundTasks), schedule process_summary_job and return task id immediately.
    - Otherwise run synchronously (blocking) and return summary_id when finished.
    """
    summary_id = str(uuid.uuid4())
    created_at = datetime.utcnow().timestamp()
    # Save stub record if adapter supports it
    try:
        if hasattr(storage, "save_summary_record"):
            storage.save_summary_record(summary_id, {"status": "queued", "request": req.dict(), "created_at": created_at})
    except Exception:
        logger.exception("storage.save_summary_record failed (stub)")

    if background_tasks:
        # schedule background worker
        background_tasks.add_task(process_summary_job, storage, summary_id, req)
        return summary_id

    # synchronous path (blocking)
    process_summary_job(storage, summary_id, req)
    return summary_id


def process_summary_job(storage, summary_id: str, req: SummaryRequest) -> None:
    """
    Worker: retrieve top-k chunks (semantic_search) -> call LLM (or heuristic) -> persist result via storage.save_summary_record.
    Keep this function idempotent-friendly: if storage.save_summary_record raises, log and continue.
    """
    try:
        # 1) retrieval
        k = int(req.k or 6)
        q = req.q or ""
        paper_id = req.paper_id
        texts = []
        try:
            hits = []
            if hasattr(storage, "semantic_search"):
                hits = storage.semantic_search(q=q, k=k, paper_id=paper_id) or []
            elif hasattr(storage, "search"):
                hits = storage.search(q=q, k=k, paper_id=paper_id) or []
            # extract snippet texts
            for h in hits:
                t = h.get("text") or (h.get("meta") or {}).get("preview") or ""
                if t:
                    texts.append(t)
        except Exception:
            logger.exception("semantic retrieval failed for summary job %s", summary_id)

        # 2) LLM / heuristic
        answer = _llm_summarize_heuristic(texts, req)

        # 3) write result
        result = {
            "summary_id": summary_id,
            "request": req.dict() if hasattr(req, "dict") else dict(req),
            "answer": answer,
            "rag": {"support": [h.get("id") or h.get("chunk_id") for h in (hits or [])], "n_support": len(hits or [])},
            "created_at": datetime.utcnow().timestamp(),
            "status": "done",
        }
        try:
            if hasattr(storage, "save_summary_record"):
                storage.save_summary_record(summary_id, result)
            else:
                # fallback: write to filesystem via papers_fs or STORE_SUMMARIES_DIR could be used by adapter; avoid adding coupling here
                logger.info("summary job completed (no storage.save_summary_record), summary_id=%s", summary_id)
        except Exception:
            logger.exception("failed persisting summary result for %s", summary_id)

    except Exception:
        logger.exception("unhandled exception in process_summary_job %s", summary_id)


# -------------------------
# Health helper
# -------------------------
def health(storage) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "backend": getattr(storage, "backend_name", None),
        "persisted": bool(getattr(storage, "persisted", False)),
        "cache_ready": bool(getattr(storage, "cache_ready", False)),
    }
    try:
        if hasattr(storage, "counts"):
            info.update(storage.counts())
        elif hasattr(storage, "n_papers"):
            info["n_papers"] = int(getattr(storage, "n_papers"))
    except Exception:
        logger.exception("failed getting storage counts")
    return info
