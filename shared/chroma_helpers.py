# vectorstore adapter (shared/chroma_helpers)

# Responsibility: talk to Chroma (or any vector store) and offer high-level calls for the pipeline: add_chunks_batch(chunk_ids, paper_ids, previews, metadatas, embeddings, client=None), get_chunks_for_paper, list_papers, create_collection_if_missing etc. Must not be mixed with parsing code.

# API: keep get_client, maybe_persist, add_chunks_batch(...), add_paper(...), safe_query(...).

# shared/chroma_helpers.py
"""
Streamlined Chroma helpers for paper-kb.

Goals:
 - clear client singleton management (module-local)
 - robust get_or_create_collection without recursion
 - safe add helpers that accept either collection object or (client, collection_name)
 - deterministic metadata sanitation
 - small normalized getters for differences across chroma versions
"""

from __future__ import annotations
import json
import time
import traceback
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# try:
#     import chromadb
#     from chromadb.config import Settings
# except Exception:
#     chromadb = None
#     Settings = None




from shared.config import EMBED_DIM, CHROMA_DIR, CHROMA_CHUNKS_COLL, CHROMA_PAPERS_COLL


from shared.chroma_client import get_client


# shared/chroma_io.py (or shared/chroma_utils.py)
from typing import Any, List, Dict, Optional
import math


def _extract_and_normalize_embedding(r: Dict[str, Any]) -> Optional[List[float]]:
    emb = r.get("embedding") or r.get("emb")
    if emb is None:
        return None
    # allow numpy arrays, tensors etc.
    if hasattr(emb, "tolist"):
        emb_list = list(emb.tolist())
    else:
        emb_list = list(emb)
    # cast to float and validate finite numbers
    try:
        out = [float(x) for x in emb_list]
    except Exception:
        return None
    if any(not math.isfinite(x) for x in out):
        return None
    return out

# shared/chroma_io.py (continuation)
from pathlib import Path
from shared.chroma_adapter import CollectionAdapter
from pipeline.parsers.canonicalize import canonical_meta_from_chunk
from shared.chroma_client import get_client, maybe_persist


# def _default_upsert(
#     records: List[Dict[str, Any]],
#     paper_meta: Dict[str, Any],
#     chroma_dir: Optional[str] = None,
#     client: Optional[Any] = None,
#     collection_name: str = CHROMA_CHUNKS_COLL,
#     batch_size: int = 512,
#     expected_dim: Optional[int] = None,
# ) -> Dict[str, Any]:
#     summary = {"n_records": 0, "n_upserted": 0, "skipped": 0, "errors": []}
#     if not records:
#         return summary

#     try:
#         if client is None:
#             client = get_client(persist_directory=Path(chroma_dir), create_if_missing=True)
#             logger.info("_default_upsert client type=%s persist_dir=%s has_persist=%s", type(client), chroma_dir, hasattr(client, "persist"))

#     except Exception as e:
#         logger.exception("failed to obtain chroma client")
#         summary["errors"].append({"exception": repr(e)})
#         return summary

#     chunk_ids, previews, metas, embeddings = [], [], [], []

#     for r in records:
#         summary["n_records"] += 1
#         cid = r.get("chunk_id") or r.get("id")
#         if not cid:
#             summary["skipped"] += 1
#             summary["errors"].append({"record": r, "error": "missing chunk_id"})
#             continue

#         emb_list = _extract_and_normalize_embedding(r)
#         if emb_list is None:
#             summary["skipped"] += 1
#             summary["errors"].append({"chunk_id": cid, "error": "missing or invalid embedding"})
#             continue

#         if expected_dim and len(emb_list) != expected_dim:
#             summary["skipped"] += 1
#             summary["errors"].append({"chunk_id": cid, "error": f"dim_mismatch {len(emb_list)} != {expected_dim}"})
#             continue

#         chunk_ids.append(str(cid))
#         previews.append((r.get("text") or r.get("preview") or "")[:2000])
#         meta = dict(r.get("meta") or r.get("metadata") or {})
#         meta = {**meta, "paper_id": str(paper_meta.get("paper_id") or r.get("paper_id") or "unknown")}
#         metas.append(sanitize_meta_for_chroma(canonical_meta_from_chunk(meta)))
#         embeddings.append(emb_list)

#     if not chunk_ids:
#         return summary

#     # use adapter + safe_add_batch
#     adapter = CollectionAdapter(client, collection_name=collection_name)
#     res = safe_add_batch(
#         adapter=adapter,
#         ids=chunk_ids,
#         documents=previews,
#         embeddings=embeddings,
#         metadatas=metas,
#         batch_size=batch_size,
#         prefer_upsert=True,
#         persist=False,   # persist at end below
#     )

#     # map results into summary
#     summary["n_upserted"] = res.get("n_upserted", 0) + res.get("n_added", 0)
#     summary["errors"].extend(res.get("errors", []))

#     # persist once
#     try:
#         adapter.maybe_persist()
#     except Exception as e:
#         logger.debug("persist failed: %s", e)

#     return summary


# # -----------------------
# # Safe add wrappers ?
# # -----------------------


# shared/chroma_io.py
from typing import Any, List, Dict, Optional
from pathlib import Path
import json, time, traceback, logging

logger = logging.getLogger(__name__)
from shared.chroma_adapter import CollectionAdapter

def safe_add_batch(
    *,
    adapter: Optional[CollectionAdapter] = None,
    collection_or_client: Any = None,
    client: Any = None,
    collection_name: Optional[str] = None,
    ids: List[str],
    documents: Optional[List[str]] = None,
    embeddings: Optional[List[List[float]]] = None,
    metadatas: Optional[List[Dict[str, Any]]] = None,
    batch_size: int = 512,
    prefer_upsert: bool = True,
    persist: bool = False,
    dump_path: Optional[Path] = Path("/tmp/chroma_failed_batch.json"),
) -> Dict[str, Any]:
    """
    Minimal, deterministic batch adder that uses CollectionAdapter.
    Returns summary: {n_attempted, n_upserted, n_added, n_skipped, errors: [...]}
    """
    if adapter is None:
        if collection_or_client is not None:
            adapter = CollectionAdapter(collection_or_client, collection_name=collection_name)
        elif client is not None:
            adapter = CollectionAdapter(client, collection_name=collection_name)
        else:
            raise ValueError("provide adapter or collection_or_client or client+collection_name")

    ids = ids or []
    documents = documents or []
    embeddings = embeddings or []
    metadatas = metadatas or [{}] * len(ids)

    if not ids:
        return {"n_attempted": 0, "n_upserted": 0, "n_added": 0, "n_skipped": 0, "errors": []}

    # validate lengths
    n = len(ids)
    if (documents and len(documents) != n) or (embeddings and len(embeddings) != n) or (metadatas and len(metadatas) != n):
        raise ValueError("length mismatch between ids/documents/embeddings/metadatas")

    summary = {"n_attempted": n, "n_upserted": 0, "n_added": 0, "n_skipped": 0, "errors": []}

    # chunked writes
    for i in range(0, n, batch_size):
        j = min(i + batch_size, n)
        sub_ids = ids[i:j]
        sub_docs = documents[i:j] if documents else None
        sub_embs = embeddings[i:j] if embeddings else None
        sub_metas = metadatas[i:j] if metadatas else None

        try:
            if prefer_upsert:
                try:
                    adapter.upsert(sub_ids, documents=sub_docs, embeddings=sub_embs, metadatas=sub_metas)
                    summary["n_upserted"] += len(sub_ids)
                    continue
                except Exception as e_up:
                    logger.debug("adapter.upsert failed for batch [%d:%d]: %s", i, j, e_up)

            # fallback to add (adapter.add will raise if duplicate ids and coll disallows)
            adapter.add(sub_ids, documents=sub_docs, embeddings=sub_embs, metadatas=sub_metas)
            summary["n_added"] += len(sub_ids)

        except Exception as e:
            tb = traceback.format_exc()
            logger.exception("batch add/upsert failed for ids %s: %s", sub_ids[:6], e)
            sample = {
                "error": str(e),
                "traceback": tb,
                "attempted_ids": sub_ids[:50],
                "docs_preview": [d[:1000] for d in (sub_docs or [])][:50],
                "metas": (sub_metas or [])[:50],
            }
            try:
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                with open(str(dump_path), "w", encoding="utf8") as fh:
                    json.dump(sample, fh, ensure_ascii=False, indent=2)
                logger.warning("Wrote failing batch sample to %s", dump_path)
            except Exception:
                logger.exception("Failed to write failing batch sample")
            summary["errors"].append({"batch_index": i, "exception": repr(e), "traceback": tb})
            # continue to next batch

    if persist:
        try:
            adapter.maybe_persist()
        except Exception:
            logger.debug("persist call failed; ignoring")

    return summary


# # shared/chroma_helpers.py — change add_chunks_batch signature to keyword-only, add upsert/force flags, and ensure it never re-derives ids.
from typing import List, Dict, Any, Optional
from pathlib import Path
import math, logging, traceback

from backend.app.chunks_fs import write_embeddings_fallback

logger = logging.getLogger(__name__)

def add_chunks_batch(
    chunk_ids: List[str],
    paper_ids: List[str],
    previews: List[str],
    metadatas: List[Dict[str, Any]],
    embeddings: List[List[float]],
    *,
    client: Optional[Any] = None,
    collection_obj: Optional[Any] = None,
    collection_name: Optional[str] = None,
    batch_size: int = 512,
    prefer_upsert: bool = True,
    persist: bool = True,
) -> Dict[str, Any]:
    """
    Upsert/add chunk vectors and metadata into the provided collection or client.
    Returns a summary dict with counts, batches and optional fallback path.

    Requirements: serialize_metadata(), CollectionAdapter(), get_client(), maybe_persist(),
    write_embeddings_fallback() must exist in the module scope or be imported.
    """
    # 1) validation
    n = len(chunk_ids)
    if not all(len(lst) == n for lst in [paper_ids, previews, metadatas, embeddings]):
        raise ValueError("Mismatched input lengths to add_chunks_batch")

    # 2) build metadata with embedded paper_id (do not mutate caller's input)
    metas = [serialize_metadata({**(m or {}), "paper_id": pid}) for m, pid in zip(metadatas, paper_ids)]

    # 3) build adapter: accept a ready collection object or a client+collection_name
    adapter = None
    used_client = None
    try:
        if collection_obj is not None:
            adapter = CollectionAdapter(collection_obj, collection_name=collection_name)
            # try to infer client if possible (adapter may expose it)
            used_client = getattr(collection_obj, "_client", None) or getattr(collection_obj, "client", None)
        else:
            # prefer explicit client passed in; else create one for CHROMA_DIR
            client = client or get_client(persist_directory=Path(CHROMA_DIR))
            used_client = client
            adapter = CollectionAdapter(client, collection_name=collection_name)
    except Exception as e:
        logger.exception("failed to build CollectionAdapter: %s", e)
        raise

    # 4) iterate batches, attempt upsert then fallback to add
    n_batches = math.ceil(n / batch_size)
    n_written = 0
    errors = []
    for i in range(0, n, batch_size):
        j = min(i + batch_size, n)
        ids_slice = chunk_ids[i:j]
        docs_slice = previews[i:j] or None
        emb_slice = embeddings[i:j] or None
        metas_slice = metas[i:j]

        try:
            if prefer_upsert and hasattr(adapter, "upsert"):
                try:
                    adapter.upsert(ids_slice, documents=docs_slice, embeddings=emb_slice, metadatas=metas_slice)
                except Exception as e_up:
                    logger.debug("adapter.upsert failed for batch %d-%d, falling back to add: %s", i, j, e_up, exc_info=True)
                    # fallback to add if upsert raises
                    if hasattr(adapter, "add"):
                        adapter.add(ids_slice, documents=docs_slice, embeddings=emb_slice, metadatas=metas_slice)
                    else:
                        raise
            else:
                # prefer add or adapter does not have upsert
                if hasattr(adapter, "add"):
                    adapter.add(ids_slice, documents=docs_slice, embeddings=emb_slice, metadatas=metas_slice)
                elif hasattr(adapter, "upsert"):
                    adapter.upsert(ids_slice, documents=docs_slice, embeddings=emb_slice, metadatas=metas_slice)
                else:
                    raise RuntimeError("CollectionAdapter has neither add nor upsert")
            n_written += len(ids_slice)
        except Exception as e:
            tb = traceback.format_exc()
            logger.exception("add_chunks_batch batch failure %d-%d: %s", i, j, e)
            errors.append({"batch": (i, j), "error": str(e), "traceback": tb})
            # raise or continue? we'll continue and collect errors to return to caller

    summary = {"n_requested": n, "n_written": n_written, "n_batches": n_batches, "errors": errors, "persisted": False, "fallback_file": None}

    # 5) try to persist if requested and a client is available
    if persist and used_client is not None:
        try:
            persisted = maybe_persist(used_client)
            summary["persisted"] = bool(persisted)
            if persisted:
                logger.info("Chroma client persisted after add_chunks_batch (n=%d)", n_written)
            else:
                # fallback: write JSONL fallback to durable folder with all the data
                try:
                    fname = write_embeddings_fallback(chunk_ids, paper_ids, metas, embeddings)
                    summary["fallback_file"] = fname
                    logger.warning("Client does not support persist(); embeddings written to fallback %s", fname)
                except Exception:
                    logger.exception("fallback embedding write also failed")
        except Exception:
            logger.exception("persist attempt raised")
            # attempt fallback anyway
            try:
                fname = write_embeddings_fallback(chunk_ids, paper_ids, metas, embeddings)
                summary["fallback_file"] = fname
            except Exception:
                logger.exception("fallback embedding write also failed")
    else:
        # no client available or persist not requested -> write fallback for safety
        if persist and used_client is None:
            try:
                fname = write_embeddings_fallback(chunk_ids, paper_ids, metas, embeddings)
                summary["fallback_file"] = fname
                logger.warning("No usable client found; embeddings written to fallback %s", fname)
            except Exception:
                logger.exception("fallback embedding write also failed")

    return summary


# # -----------------------
# # High-level convenience ops
# # -----------------------

def add_paper(paper_id: str, metadata: Dict[str, Any], embedding: Optional[List[float]] = None, client: Optional[Any] = None, collection_name: Optional[str] = None):
    client = client or get_client(persist_directory=Path(CHROMA_DIR))
    logger.info("add_paper client type=%s persist_dir=%s has_persist=%s", type(client), CHROMA_DIR, hasattr(client, "persist"))


    adapter = CollectionAdapter(client, collection_name=collection_name or CHROMA_PAPERS_COLL)
    doc = (metadata or {}).get("title", "")
    metas = serialize_metadata(metadata)
    if embedding is None:
        adapter.add([paper_id], documents=[doc], metadatas=[metas], embeddings=None)
    else:
        adapter.add([paper_id], documents=[doc], metadatas=[metas], embeddings=[embedding])
    adapter.maybe_persist()

def add_chunk(chunk_id: str, paper_id: str, preview_text: str, metadata: Dict[str, Any], embedding: List[float], client: Optional[Any] = None, collection_name: Optional[str] = None):
    client = client or get_client(persist_directory=Path(CHROMA_DIR))
    logger.info("add_chunk client type=%s persist_dir=%s has_persist=%s", type(client), CHROMA_DIR, hasattr(client, "persist"))

    adapter = CollectionAdapter(client, collection_name=collection_name or CHROMA_CHUNKS_COLL)
    meta = {**(metadata or {}), "paper_id": paper_id}
    adapter.add([chunk_id], documents=[preview_text], embeddings=[embedding], metadatas=[serialize_metadata(meta)])
    adapter.maybe_persist()




# shared/chroma_meta.py

# def sanitize_meta_for_chroma(meta) -> dict

# def serialize_metadata(meta) -> dict



# -----------------------
# Metadata sanitation
# -----------------------
def sanitize_meta_for_chroma(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert metadata values to primitives allowed by Chroma."""
    if not meta:
        return {}
    out: Dict[str, Any] = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
            continue
        if isinstance(v, (list, tuple)):
            if all(isinstance(x, (str, int, float, bool)) for x in v) and len(v) <= 20:
                out[k] = ",".join(map(str, v))
            else:
                try:
                    out[k] = json.dumps(v, ensure_ascii=False)
                except Exception:
                    out[k] = str(v)
            continue
        try:
            out[k] = json.dumps(v, ensure_ascii=False)
        except Exception:
            out[k] = str(v)
    return out


def serialize_metadata(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Compatibility wrapper (same as sanitize)."""
    return sanitize_meta_for_chroma(canonical_meta_from_chunk(meta) or {})


# shared/chroma_query.py

# def get_chunks_for_paper(paper_id, client, collection_name) -> list[dict]


# _normalize_get_result should be a single routine that converts the various shapes returned by different chroma versions into a canonical dict with keys ids, metadatas, documents.

# -----------------------
# Normalizers for get()/query() results
# -----------------------
def _normalize_get_result(res: Dict[str, Any]) -> Dict[str, List]:
    """
    Normalize possible shapes returned by coll.get()/query() across chroma versions.
    Ensures keys: documents (list[str]), metadatas (list[dict]), ids (list[str]) if present.
    """
    out_docs = res.get("documents") or []
    out_meta = res.get("metadatas") or []
    out_ids = res.get("ids") or []

    # some versions return nested lists [ [docs...] ]
    if out_docs and isinstance(out_docs[0], list):
        out_docs = out_docs[0]
    if out_meta and isinstance(out_meta[0], list):
        out_meta = out_meta[0]
    if out_ids and isinstance(out_ids[0], list):
        out_ids = out_ids[0]

    return {"documents": out_docs, "metadatas": out_meta, "ids": out_ids}



# -----------------------
# Query helpers
# -----------------------


# Idea to migrate to:
def get_chunks_for_paper_count(paper_id: str, *, client: Any = None, collection_name: str = "chunks") -> int:
    adapter = CollectionAdapter(client, collection_name=collection_name)
    # prefer adapter.query/get with filter - adapt to your Chroma version
    try:
        res = adapter.get(where={"paper_id": paper_id}, include=["ids"])  # normalize in adapter
        # _normalize_get_result should return {'ids': [...]}
        norm = _normalize_get_result(res)
        return len(norm.get("ids", []))
    except Exception:
        # fallback to a cheap search that returns at most 1 (if available)
        res = adapter.query(where={"paper_id": paper_id}, n_results=1) if hasattr(adapter, "query") else adapter.get(ids=[paper_id])
        norm = _normalize_get_result(res)
        return len(norm.get("ids", []))


def get_chunks_for_paper(paper_id: str, client: Optional[Any] = None, collection_name: str = CHROMA_CHUNKS_COLL, limit: int = 1000):
    """Return list of dicts: {'id','preview','meta'} for the given paper_id."""
    adapter = CollectionAdapter(client, collection_name=collection_name)

    try:
        res = adapter.get(where={"paper_id": paper_id}, include=["documents", "metadatas"])  # do not request 'ids' in include
        norm = _normalize_get_result(res)
    except Exception as e:
        logger.warning("get_chunks_for_paper error: %s", e)
        return []

    docs = norm["documents"]
    metas = norm["metadatas"]
    ids = norm.get("ids", [])
    out = []
    n = min(limit, len(docs))
    for i in range(n):
        idv = None
        if i < len(ids):
            idv = ids[i]
        else:
            idv = metas[i].get("chunk_id") if i < len(metas) else f"{paper_id}::chunk::{i}"
        out.append({"id": idv, "preview": docs[i], "meta": metas[i] if i < len(metas) else {}})
    return out







# # This gives you single-purpose modules, easier to test and reason about.






# def safe_query(collection, embedding: Optional[list] = None, n_results: int = 6,
#                where: Optional[dict] = None, include: Optional[list] = None):
#     """
#     Robust wrapper around collection.query that tolerates several chroma client signatures.
#     If embedding is None, attempt metadata-only query/filter (server-side) or fallback to get() + client-side filter.
#     Returns normalized dict with keys: documents, metadatas, ids
#     """
#     include = include or ["documents", "metadatas", "ids"]
#     last_exc = None

#     # Case A: metadata-only query (no vector)
#     if embedding is None:
#         attempts = []
#         # 1) modern signature with where
#         attempts.append(lambda: collection.query(n_results=n_results, where=where, include=include))
#         # 2) alternative filter param
#         attempts.append(lambda: collection.query(top_k=n_results, filter=where, include=include))
#         # 3) some clients support query with only include (no filter)
#         attempts.append(lambda: collection.query(n_results=n_results, include=include))
#         # 4) fallback: client.get() and filter client-side
#         attempts.append(lambda: collection.get(include=include))
#     else:
#         # normalize embedding to plain list
#         try:
#             emb_list = list(embedding)
#         except Exception:
#             raise ValueError("safe_query: embedding is not iterable")
#         attempts = []
#         attempts.append(lambda: collection.query(query_embeddings=[emb_list], n_results=n_results, where=where, include=include))
#         attempts.append(lambda: collection.query(query_embeddings=[emb_list], n_results=n_results, filter=where, include=include))
#         attempts.append(lambda: collection.query(query_vector=emb_list, top_k=n_results, include=include))
#         attempts.append(lambda: collection.query(query_embedding=emb_list, top_k=n_results, include=include))

#     for fn in attempts:
#         try:
#             res = fn()
#             if not isinstance(res, dict):
#                 # normalize to dict if client returns a typed object with .to_dict()
#                 try:
#                     res = dict(res)
#                 except Exception:
#                     pass
#             docs = res.get("documents", []) or []
#             metas = res.get("metadatas", []) or []
#             ids = res.get("ids", []) or []
#             # flatten nested query responses (one response per query)
#             if docs and isinstance(docs[0], list):
#                 docs, metas, ids = docs[0], metas[0], ids[0]
#             return {"documents": docs, "metadatas": metas, "ids": ids}
#         except Exception as e:
#             last_exc = e
#             continue

#     # If none succeeded, raise with last error
#     raise RuntimeError(f"safe_query: all attempts failed; last error: {repr(last_exc)}")

# # -------------------------
# # Helpers for robust chroma access
# # -------------------------
# def _safe_collection_get_all(coll):
#     """Try various include signatures to get documents/metadatas/ids robustly."""
#     include_options = [["metadatas", "data"], ["metadatas", "documents"], ["metadatas"], ["data"]]
#     last_exc = None
#     raw = None
#     for inc in include_options:
#         try:
#             try:
#                 raw = coll.get(include=inc)
#             except TypeError:
#                 raw = coll.get()
#             if raw:
#                 break
#         except Exception as e:
#             last_exc = e
#             raw = None
#             continue
#     if raw is None:
#         raise RuntimeError(f"Chroma get() failed for all include options: {repr(last_exc)}")
#     return raw


# -----------------------
# Collection helpers (defensive)
# -----------------------
def get_or_create_collection(client: Optional[Any] = None, name: Optional[str] = None,
                             metadata: Optional[Dict[str, Any]] = None, persist_directory: Optional[Union[str, Path]] = None):
    """
    Explicit API: pass client (Chroma client) and name (collection name).
    If client is None, open the default persist client.
    If name is None, return the default CHROMA_CHUNKS_COLL.
    """
    from pathlib import Path
    if name is None:
        name = CHROMA_CHUNKS_COLL  # define default constant in module

    if client is None:
        client = get_client(persist_directory=persist_directory, create_if_missing=True)
        logger.info("get_or_create_collection client type=%s persist_dir=%s has_persist=%s", type(client), CHROMA_DIR, hasattr(client, "persist"))


    # Try to get existing collection
    try:
        coll = client.get_collection(name)
        return coll
    except Exception:
        # create it
        try:
            coll = client.create_collection(name=name, metadata=metadata or {"created_by": "paper-kb"})
            return coll
        except Exception as e:
            raise



def list_collections(client: Optional[Any] = None) -> List[str]:
    client = client or get_client(persist_directory=Path(CHROMA_DIR))
    logger.info("list_collections client type=%s persist_dir=%s has_persist=%s", type(client), CHROMA_DIR, hasattr(client, "persist"))

    try:
        cols = client.list_collections()
        names: List[str] = []
        if isinstance(cols, list):
            for c in cols:
                if isinstance(c, str):
                    names.append(c)
                elif isinstance(c, dict) and "name" in c:
                    names.append(c["name"])
        return names
    except Exception as e:
        logger.warning("list_collections error: %s", e)
        return []


