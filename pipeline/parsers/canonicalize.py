# pipeline/parsers/canonicalize.py
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
import hashlib

# import the canonical model types used by the backend API
from backend.app.schemas import CanonicalChunk, PaperMeta

# reuse local normalization where present in repo
try:
    # prefer the pipeline-local normalize_chunk (keeps parser dependencies local)
    from backend.app.chunks_fs import normalize_chunk
except Exception:
    # fallback to backend helper if pipeline one is not available
    from backend.app.chunks_fs import normalize_chunk  # type: ignore

logger = logging.getLogger("pipeline.parsers.canonicalize")



import hashlib
import re
from typing import Dict, Any, List, Optional

# keep using your existing logger and CanonicalChunk, normalize_chunk
# from backend.app.schemas import CanonicalChunk  # already available upstream
# from pipeline.parsers.canonicalize import normalize_chunk  # already available upstream

ID_SAFE = re.compile(r"[^A-Za-z0-9_\-\.]")

def _sanitize_id_fragment(s: str, maxlen: int = 200) -> str:
    if s is None:
        return ""
    s = str(s)
    s = ID_SAFE.sub("_", s)
    return s[:maxlen]



# def _sanitize_part(s: str, maxlen: int = 200) -> str:
#     s = str(s or "")
#     s = _ID_SAFE.sub("_", s)
#     return s[:maxlen]

def canonical_chunk_id(paper_id: str, raw: dict, seq: int) -> str:
    for k in ("chunk_id","chunkId","id","xml_id","xml:id","xmlId"):
        v = raw.get(k)
        if v:
            return f"{_sanitize_id_fragment(paper_id)}::{_sanitize_id_fragment(v)}"
    return f"{_sanitize_id_fragment(paper_id)}::c{seq:06d}"


# pipeline/parsers/canonicalize.py — add canonical_chunk_id and ensure all r["chunk_id"] injections come from it.

def _derive_chunk_id(paper_id: str, raw: Dict[str, Any], seq: int) -> str:
    """
    Single canonical chunk id derivation:
      - prefer raw['chunk_id'] or raw['id'] or raw['xml_id'] or raw.get('xml:id')
      - if found, sanitize and prefix with paper_id to avoid cross-paper collisions
      - else use short sha1 of text (or seq) as fallback
    Return a deterministic id string.
    """
    # try common names
    for k in ("chunk_id", "chunkId", "id", "xml_id", "xml:id", "xmlId"):
        v = raw.get(k)
        if v:
            s = str(v)
            short = _sanitize_id_fragment(s)
            if short:
                return f"{paper_id}__c{seq:06d}__{short}"
            # if sanitization removed everything, fall through to hash fallback

    # implement canonical_chunk_id(.. ?)

    # fallback: stable short hash of the text (or seq if no text)
    text = raw.get("text") or raw.get("content") or ""
    base = text if text else str(seq)
    h = hashlib.sha1(base.encode("utf8")).hexdigest()[:12]
    return f"{paper_id}__c{seq:06d}__{h}"

def chunks_to_models(title: str, paper_id: str, chunks: List[Dict[str, Any]]) -> List[CanonicalChunk]:
    """
    Convert raw chunk dicts into validated CanonicalChunk pydantic models.

    Guarantees:
      - stable deterministic chunk_id injected when missing
      - passes a default_index to normalize_chunk so chunk_index exists
      - returns only validated CanonicalChunk instances
      - stable ordering by chunk_index then chunk_id
    """
    out: List[CanonicalChunk] = []
    seq = 0
    for raw in chunks:
        seq += 1
        # make a shallow copy so we don't mutate upstream data structures
        r = dict(raw)

        # ensure text exists (coerce if parser used different key)
        if "text" not in r and "content" in r:
            r["text"] = r["content"]

        # derive/inject chunk_id if missing (deterministic)
        existing_id = r.get("chunk_id") or r.get("id") or r.get("xml_id") or r.get("xml:id")
        if not existing_id:
            derived = _derive_chunk_id(paper_id, r, seq)
            r["chunk_id"] = derived
            logger.debug("chunks_to_models: injected chunk_id=%s for paper=%s seq=%d", derived, paper_id, seq)
        else:
            # ensure sanitized and prefixed to avoid collisions across papers
            sanitized = _sanitize_id_fragment(str(existing_id))
            r["chunk_id"] = f"{paper_id}__c{seq:06d}__{sanitized}" if sanitized else _derive_chunk_id(paper_id, r, seq)

        # provide default chunk_index to normalize_chunk (0-based)
        default_index = seq - 1

        try:
            # normalize_chunk should accept (raw, paper_id, default_index) and return a CanonicalChunk
            model = normalize_chunk(r, paper_id, default_index=default_index)
            if not isinstance(model, CanonicalChunk):
                # coerce if it returned dict
                model = CanonicalChunk(**(model if isinstance(model, dict) else model.dict()))
            # as a safety, ensure chunk_id exists on model; if not, set from injected id
            if not getattr(model, "chunk_id", None):
                model.chunk_id = r["chunk_id"]
            out.append(model)
        except Exception as exc:
            # keep skipping invalid chunks but log full context for debugging
            logger.warning("chunks_to_models: skip invalid chunk (paper=%s seq=%d) err=%s raw_snippet=%.120s",
                           paper_id, seq, exc, (r.get("text") or "")[:120])
            continue

    # stable ordering: prefer explicit chunk_index, then chunk_id to break ties
    out.sort(key=lambda m: (getattr(m, "chunk_index", 0), getattr(m, "chunk_id", "")))
    return out


def _pages_sample_from_records(records: List[CanonicalChunk]) -> Optional[int]:
    """
    Try to return a simple page scalar representative for the paper.
    Uses the first non-empty pages pair if present.
    """
    for r in records:
        if getattr(r, "pages", None):
            pages = r.pages
            # pages may be tuple (first,last) or single-int
            if isinstance(pages, (list, tuple)) and len(pages) > 0 and pages[0] is not None:
                try:
                    return int(pages[0])
                except Exception:
                    continue
            try:
                return int(pages)
            except Exception:
                continue
    return None


def _preview_from_records(records: List[CanonicalChunk], n_chars: int = 300) -> str:
    if not records:
        return ""
    first_text = (records[0].text or "")[:n_chars]
    return first_text


def _pipeline_version() -> str:
    """
    Return a version string for this pipeline. Keep simple: timestamp + short hash.
    Could be replaced with git commit or explicit version var.
    """
    ts = datetime.utcnow().isoformat()
    short = hashlib.sha1(ts.encode("utf8")).hexdigest()[:6]
    return f"pipeline_{short}"



def make_paper_meta(title: str, paper_id: str, records: List[CanonicalChunk], extra: Optional[Dict[str, Any]] = None) -> PaperMeta:
    """
    Build a PaperMeta model from canonical chunks.

    Rules:
      - n_chunks computed from len(records)
      - preview is the first record's text (trimmed)
      - pages uses _pages_sample_from_records heuristic (int or None)
      - created_at defaults to now (UTC) if not present in `extra`
      - pipeline_version auto-generated if not present in extra
      - authors accepted from extra.get('authors') or extra.get('creators')
    """
    extra = extra or {}
    authors = extra.get("authors") or extra.get("author") or extra.get("creators") or None
    pages = extra.get("pages") or _pages_sample_from_records(records)
    preview = extra.get("preview") or _preview_from_records(records, n_chars=300)
    created_at = extra.get("created_at") or datetime.utcnow()
    pipeline_version = extra.get("pipeline_version") or _pipeline_version()
    embed_model = extra.get("embed_model") or None
    source_file = extra.get("source_file") or None

    # Build the PaperMeta model (pydantic will validate/coerce)
    pm = PaperMeta(
        paper_id=str(paper_id),
        title=str(title or paper_id),
        authors=authors,
        n_chunks=len(records),
        preview=preview,
        pages=pages,
        source_file=source_file,
        created_at=created_at,
        pipeline_version=pipeline_version,
        embed_model=embed_model,
    )
    return pm


from typing import Dict, Any, Optional
from datetime import datetime


def canonical_meta_from_chunk(canonical_chunk) -> Dict[str, Any]:
    """
    Build a compact, deterministic metadata dict for a CanonicalChunk-like object.

    The returned dict is intentionally primitive-friendly (str/int/float/bool or short lists).
    Call sanitize_meta_for_chroma(...) afterwards to make it safe for Chroma storage.

    Expected canonical_chunk attributes (best-effort): 
       - chunk_id, paper_id, chunk_index, char_len, header_path, pages, meta (dict), text
    """
    if canonical_chunk is None:
        return {}

    # flexible access (support dict or pydantic-model)
    get = (lambda k, default=None: canonical_chunk.get(k, default)) if isinstance(canonical_chunk, dict) else (lambda k, default=None: getattr(canonical_chunk, k, default))

    chunk_id = get("chunk_id")
    paper_id = get("paper_id")
    idx = get("chunk_index", None)
    char_len = get("char_len", None)
    header = get("header_path", None)
    pages = get("pages", None)  # can be None, "3-5", or [3,5]
    unit = None
    xml_id = None
    extra_meta = get("meta", {}) or {}

    # try common meta fields
    if isinstance(extra_meta, dict):
        unit = extra_meta.get("unit") or extra_meta.get("type")
        xml_id = extra_meta.get("xml_id") or extra_meta.get("id")

    text = (get("text") or "") if get("text", None) is not None else ""
    preview = text.strip()[:300]  # short preview for fast inspection/search

    # canonical pages: try to coerce to "start-end" string for compactness
    pages_out: Optional[str] = None
    if pages is None:
        pages_out = None
    elif isinstance(pages, (list, tuple)) and len(pages) >= 1:
        try:
            pages_out = f"{int(pages[0])}" + (f"-{int(pages[-1])}" if len(pages) > 1 else "")
        except Exception:
            pages_out = str(pages)
    else:
        pages_out = str(pages)

    out: Dict[str, Any] = {
        "chunk_id": str(chunk_id) if chunk_id is not None else None,
        "paper_id": str(paper_id) if paper_id is not None else None,
        "chunk_index": int(idx) if idx is not None else None,
        "char_len": int(char_len) if char_len is not None else (len(text) if text else 0),
        "preview": preview,
        "header_path": str(header) if header else None,
        "pages": pages_out,
        "unit": unit,
        "xml_id": xml_id,
        # provenance / ingest hints
        "imported_at": datetime.utcnow().isoformat() + "Z",
    }

    # include a tiny selection of other simple meta fields if present (authors/title)
    for fld in ("paper_title", "title", "authors", "source_file"):
        val = extra_meta.get(fld)
        if val is None:
            continue
        # keep lists short
        if isinstance(val, (list, tuple)):
            out[fld] = val if len(val) <= 10 and all(isinstance(x, (str, int, float, bool)) for x in val) else ",".join(map(str, val[:10]))
        else:
            out[fld] = val

    # remove None-values (opt: keep them out to reduce storage size)
    return {k: v for k, v in out.items() if v is not None}

 

# import json
# import time
# from datetime import datetime
# from pathlib import Path
# from typing import Any, Dict, Optional, Sequence

# # tune these if needed
# _PREVIEW_CHARS = 300
# _MAX_JSON_LENGTH = 4000
# _MAX_LIST_SERIALIZE = 20

# def _safe_preview(text: Optional[str], n: int = _PREVIEW_CHARS) -> str:
#     if not text:
#         return ""
#     s = " ".join(text.split())  # collapse whitespace/newlines
#     if len(s) <= n:
#         return s
#     return s[:n].rsplit(" ", 1)[0]  # avoid cutting a word when possible

# def _normalize_pages(pages: Optional[Any]) -> Optional[str]:
#     """
#     Accept ints, (start,end) or [start,end] or "12-14" and return simple "start-end" or single number as str.
#     """
#     if pages is None:
#         return None
#     if isinstance(pages, (int, str)):
#         return str(pages)
#     if isinstance(pages, Sequence):
#         try:
#             if len(pages) == 0:
#                 return None
#             if len(pages) == 1:
#                 return str(pages[0])
#             return f"{int(pages[0])}-{int(pages[-1])}"
#         except Exception:
#             return ",".join(map(str, pages))
#     return str(pages)

# def _normalize_bbox(bboxes: Optional[Any]) -> Optional[str]:
#     """
#     Convert bbox objects (lists/dicts) to a small JSON string representation.
#     Keep it short to avoid huge metadata fields.
#     """
#     if bboxes is None:
#         return None
#     try:
#         # if it's already a primitive list of numbers, turn to simple CSV
#         if isinstance(bboxes, Sequence) and all(isinstance(x, (int, float)) for x in bboxes):
#             return ",".join(map(str, bboxes))
#         j = json.dumps(bboxes, ensure_ascii=False)
#         if len(j) > _MAX_JSON_LENGTH:
#             return j[:_MAX_JSON_LENGTH] + "…"
#         return j
#     except Exception:
#         try:
#             return str(bboxes)[:_MAX_JSON_LENGTH]
#         except Exception:
#             return None

# def _coerce_small_list(v: Any) -> Any:
#     """If v is a short list of primitives, leave it; if long or complex, stringify."""
#     if isinstance(v, (list, tuple)):
#         if len(v) <= _MAX_LIST_SERIALIZE and all(isinstance(x, (str, int, float, bool)) for x in v):
#             return list(v)
#         try:
#             s = json.dumps(v, ensure_ascii=False)
#             return s if len(s) <= _MAX_JSON_LENGTH else s[:_MAX_JSON_LENGTH] + "…"
#         except Exception:
#             return str(v)[:_MAX_JSON_LENGTH]
#     return v

# def _iso_now() -> str:
#     return datetime.utcnow().isoformat() + "Z"

# def _canonical_meta_from_chunk(chunk: Any) -> Dict[str, Any]:
#     """
#     Produce a canonical metadata mapping for a chunk model (or dict).
#     - returns a plain dict of primitives / small lists (not sanitized for chroma yet).
#     - callers typically call sanitize_meta_for_chroma(...) afterwards.
#     """
#     # support both object-with-attrs and dict-like
#     get = chunk.get if isinstance(chunk, dict) else lambda k, d=None: getattr(chunk, k, d)

#     chunk_id = get("chunk_id") or get("id") or None
#     paper_id = get("paper_id") or get("pid") or None
#     chunk_index = get("chunk_index") or get("index") or None
#     text = get("text") or get("page_content") or ""
#     char_len = int(get("char_len") or (len(text) if text else 0))
#     pages = _normalize_pages(get("pages") or get("page") or get("page_range"))
#     header_path = get("header_path") or get("header") or None
#     unit = get("unit") or None
#     xml_id = get("xml_id") or get("xml:id") or get("id") or None
#     bboxes = _normalize_bbox(get("bboxes") or get("coords") or get("bbox"))
#     source_file = get("source_file") or get("source") or None

#     # any user-supplied metadata that we want to preserve but namespace it
#     raw_meta = get("meta") or get("metadata") or {}
#     if not isinstance(raw_meta, dict):
#         # sometimes meta is a string; try to coerce
#         try:
#             raw_meta = json.loads(raw_meta)
#         except Exception:
#             raw_meta = {"raw": str(raw_meta)}

#     # build canonical map
#     out: Dict[str, Any] = {
#         "chunk_id": str(chunk_id) if chunk_id is not None else None,
#         "paper_id": str(paper_id) if paper_id is not None else None,
#         "chunk_index": int(chunk_index) if chunk_index is not None else None,
#         "char_len": int(char_len),
#         "pages": pages,
#         "header_path": str(header_path) if header_path else None,
#         "unit": str(unit) if unit else None,
#         "xml_id": str(xml_id) if xml_id else None,
#         "bbox": bboxes,
#         "preview": _safe_preview(text, _PREVIEW_CHARS),
#         "source_file": str(source_file) if source_file else None,
#         # timestamp: prefer when provided in raw_meta, else now
#         "created_at": raw_meta.get("created_at") or raw_meta.get("imported_at") or _iso_now(),
#     }

#     # merge a sanitized subset of raw_meta under a namespaced key to avoid collisions
#     if raw_meta:
#         # keep small/primitive fields directly (first-class), and put the rest under raw_meta
#         for k, v in list(raw_meta.items()):
#             if k in ("created_at", "imported_at"):
#                 continue
#             out_key = f"raw_{k}" if k in out else k
#             out[out_key] = _coerce_small_list(v)

#     # remove None values (keep payload compact)
#     out = {k: v for k, v in out.items() if v is not None}

#     return out
