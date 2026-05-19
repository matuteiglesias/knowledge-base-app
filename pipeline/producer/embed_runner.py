#!/usr/bin/env python3
# pipeline/runners/embed_runner.py
"""
Streamlined embed runner.

Modes:
 - per-paper: embed_and_upsert(paper_id, client, ...)
 - bulk: ingest_chunks_to_chroma(chunks_dir, chroma_dir, ...)

Goals:
 - single place for client lifecycle, adapters, cache handling
 - consistent existence check via get_chunks_for_paper
 - clear dry-run and force semantics
 - small failure dumps to configurable path
"""
from __future__ import annotations
import argparse
import json
import logging
import shutil
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

# project path is expected to be set by your runner shell (PYTHONPATH)
# engine primitives (embedding) and helpers
from kb.embedding.engine import embed_records
from kb.embedding.adapters import PlaceholderAdapter, _build_default_adapter
from kb.embedding.cache import EmbeddingCache

# FS / models
from backend.app import chunks_fs
from backend.app.schemas import CanonicalChunk

# chrome helpers
from shared.chroma_helpers import (
    get_or_create_collection,
    add_chunks_batch,
    add_paper,
    get_chunks_for_paper,
    get_chunks_for_paper_count,
    sanitize_meta_for_chroma,
)
from shared.chroma_client import (
    get_client,
    maybe_persist,
)


from shared.config import CHROMA_DIR, EMBED_CACHE_DB, EMBED_DIM

logger = logging.getLogger("embed_runner")
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


# ---------- Helpers ----------
def load_models_for_paper(paper_id: str) -> List[CanonicalChunk]:
    """Load canonical models for a paper, with a JSONL fallback."""
    models = chunks_fs.read_chunks_as_models(paper_id)
    if models:
        return models
    recs = chunks_fs.read_chunks_jsonl(paper_id)
    return [chunks_fs.normalize_chunk(r, paper_id=paper_id) for r in recs]


def _write_failure_dump(prefix: str, payload: Dict[str, Any], dumps_dir: Path = Path("/tmp")) -> Optional[Path]:
    try:
        dumps_dir.mkdir(parents=True, exist_ok=True)
        short = abs(hash(prefix)) % (10**8)
        path = dumps_dir / f"embed_fail_{prefix}_{short}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf8")
        logger.info("failure dump written to %s", path)
        return path
    except Exception:
        logger.debug("couldn't write failure dump", exc_info=True)
        return None






# ---------- per-paper flow ----------

# pipeline/runner/embed_runner.py (refactored embed_and_upsert)
from shared.chroma_helpers import add_chunks_batch, add_paper, maybe_persist  # implement get_chunks_for_paper helper
from shared.chroma_adapter import CollectionAdapter
from pipeline.parsers.canonicalize import canonical_meta_from_chunk




MAX_POST_UPSERT_PROBE_RETRIES = 2
POST_UPSERT_PROBE_WAIT_SECONDS = 0.5

def _validate_embeddings(embs: List[List[float]], expected_dim: int):
    if not isinstance(embs, list):
        raise RuntimeError("embeddings object is not a list")
    for i, e in enumerate(embs):
        if e is None:
            raise RuntimeError(f"embedding[{i}] is None")
        if not hasattr(e, "__len__"):
            raise RuntimeError(f"embedding[{i}] not length-checkable")
        if len(e) != expected_dim:
            raise RuntimeError(f"embedding[{i}] dim {len(e)} != expected {expected_dim}")

def post_upsert_verify_and_retry(client: Any, collection_name: str, chunk_ids: List[str]) -> bool:
    """
    Probe that at least one inserted id is visible via the client. Retry maybe_persist() once.
    Returns True if probe succeeded.
    """
    # conservative: probe the first id
    if not chunk_ids:
        return True
    probe_id = chunk_ids[0]
    last_exc = None
    for attempt in range(MAX_POST_UPSERT_PROBE_RETRIES + 1):
        try:
            coll = None
            try:
                coll = client.get_collection(collection_name)
            except Exception:
                # some client shapes give collection via client.get_collection; some helper may wrap
                coll = None
            if coll is not None:
                # try a minimal get (include ids)
                try:
                    res = coll.get(ids=[probe_id], include=["ids", "metadatas"])
                    if res and res.get("ids"):
                        return True
                except Exception:
                    # fallback to count or query
                    pass
            # fallback: attempt collection count by filter (best-effort)
            try:
                # if you have helper get_chunks_for_paper_count, prefer that, else try coll.count() if available
                if hasattr(coll, "count"):
                    # some versions: coll.count() may be signatureless
                    cnt = coll.count()
                    if cnt and cnt > 0:
                        return True
            except Exception:
                pass
        except Exception as e:
            last_exc = e

        # if attempt < retry: request persistence and wait
        if attempt < MAX_POST_UPSERT_PROBE_RETRIES:
            try:
                maybe_persist(client)
            except Exception:
                pass
            time.sleep(POST_UPSERT_PROBE_WAIT_SECONDS * (attempt + 1))
    # final failure
    logger.warning("post_upsert_verify failed for id=%s (err=%s)", probe_id, last_exc)
    return False



def embed_and_upsert(
    paper_id: str,
    client: Optional[Any],
    collection_name: str = "chunks",
    adapter: Optional[Any] = None,
    cache: Optional[Any] = None,
    dry_run: bool = False,
    force: bool = False,
    batch_size: int = 512,
    failure_dump_dir: Path = Path("/tmp"),
) -> Dict[str, Any]:
    logger.info("embed_and_upsert: %s", paper_id)
    try:
        models = load_models_for_paper(paper_id)
        if not models:
            return {"paper_id": paper_id, "status": "no_models"}

        client = client or get_client(persist_directory=Path(CHROMA_DIR))
        logger.info("embed_and_upsert client type=%s persist_dir=%s has_persist=%s", type(client), CHROMA_DIR, hasattr(client, "persist"))

        # ensure we have a client created consistently
        # if client is None:
        #     client = get_client(persist_directory=CHROMA_DIR)  # CHROMA_DIR from shared.config

        # existence check
        if not force:
            try:
                existing_count = get_chunks_for_paper_count(paper_id, client=client, collection_name=collection_name)
                if existing_count >= len(models):
                    return {"paper_id": paper_id, "status": "skipped_existing", "n_existing": existing_count}
            except Exception:
                logger.debug("existence check failed; continuing", exc_info=True)

        adapter = adapter or _build_default_adapter()
        embs = embed_records(models, adapter=adapter, cache=cache, expected_dim=EMBED_DIM, batch_size=min(batch_size, 512))

        if len(embs) != len(models):
            raise RuntimeError(f"embeddings length mismatch: {len(embs)} != {len(models)}")

        # strict per-embedding dimension check
        _validate_embeddings(embs, EMBED_DIM)

        chunk_ids = [str(getattr(m, "chunk_id")) for m in models]
        docs = [getattr(m, "text", "") or "" for m in models]
        metadatas = [sanitize_meta_for_chroma(canonical_meta_from_chunk(m)) for m in models]

        if dry_run:
            logger.info("dry-run: would upsert %d chunks for %s", len(chunk_ids), paper_id)
            return {"paper_id": paper_id, "status": "dry_run", "n_chunks": len(chunk_ids)}

        # Upsert — ensure add_chunks_batch uses provided client (it takes client param)
        add_chunks_batch(
            chunk_ids=chunk_ids,
            paper_ids=[paper_id] * len(chunk_ids),
            previews=docs,
            metadatas=metadatas,
            embeddings=embs,
            client=client,
            collection_name=collection_name,
            batch_size=batch_size,
        )

        # Post-upsert verification / retry with persist if necessary
        visible = post_upsert_verify_and_retry(client, collection_name, chunk_ids)
        if not visible:
            # Not fatal but informative: write failure dump and return "partial" status
            msg = f"post-upsert visibility failed for paper {paper_id}"
            logger.warning(msg)
            _write_failure_dump(paper_id, {"paper_id": paper_id, "error": msg}, failure_dump_dir)
            return {"paper_id": paper_id, "status": "partial_ok", "n_chunks": len(chunk_ids)}

        # best-effort paper doc
        try:
            preview = docs[0][:200] if docs else ""
            title = getattr(models[0], "paper_title", paper_id) or paper_id
            add_paper(paper_id, {"paper_id": paper_id, "title": title, "n_chunks": len(models), "preview": preview}, client=client, collection_name="papers")
        except Exception:
            logger.debug("add_paper non-fatal failure", exc_info=True)

        return {"paper_id": paper_id, "status": "ok", "n_chunks": len(chunk_ids)}
    except Exception as exc:
        tb = traceback.format_exc()
        logger.exception("embed_and_upsert failed for %s", paper_id)
        _write_failure_dump(paper_id, {"paper_id": paper_id, "error": str(tb)}, failure_dump_dir)
        return {"paper_id": paper_id, "status": "failed", "error": str(tb)}




from shared.chroma_helpers import get_chunks_for_paper

# # ---------- bulk ingest flow ----------
# def ingest_chunks_to_chroma(
#     chunks_dir: Path,
#     chroma_dir: Path,
#     collection: str = "chunks",
#     adapter: Optional[Callable] = None,
#     cache_db: Optional[Path] = None,
#     batch_size: int = 256,
#     force: bool = False,
#     dry_run: bool = False,
#     reset: bool = False,
#     failure_dump_dir: Path = Path("/tmp"),
# ) -> Dict[str, Any]:
#     """
#     Bulk ingest all *_chunks.jsonl under chunks_dir into chroma_dir collection.

#     Returns a summary dict with processed/skipped/failed counts and details list.
#     """
#     chunks_dir = Path(chunks_dir).expanduser().resolve()
#     chroma_dir = Path(chroma_dir).expanduser().resolve()
#     client = get_client(persist_directory=chroma_dir, create_if_missing=True)
#     coll_name = collection
#     coll = get_or_create_collection(client=client, name=coll_name)

#     files = sorted(chunks_dir.rglob("*_chunks.jsonl"))
#     if not files:
#         logger.error("no chunk jsonl files under %s", chunks_dir)
#         return {"error": "no_files"}

#     if reset:
#         logger.info("reset requested: clearing chroma dir %s and cache %s", chroma_dir, cache_db or EMBED_CACHE_DB)
#         try:
#             shutil.rmtree(str(chroma_dir), ignore_errors=True)
#         except Exception:
#             logger.debug("couldn't remove chroma_dir", exc_info=True)
#         try:
#             Path(cache_db or EMBED_CACHE_DB).unlink()
#         except Exception:
#             pass
#         # recreate client after reset
#         client = get_client(persist_directory=chroma_dir, create_if_missing=True)
#         coll = get_or_create_collection(client=client, name=coll_name)

#     # adapter default
#     if adapter is None:
#         adapter = _build_default_adapter()

#     # cache open
#     cache = None
#     if cache_db:
#         try:
#             cache = EmbeddingCache.open(Path(cache_db))
#         except Exception:
#             logger.warning("could not open embedding cache %s (continuing without cache)", cache_db)

#     summary = {"n_files": len(files), "processed": 0, "skipped": 0, "failed": 0, "details": []}
#     for cf in files:
#         try:
#             paper_id = cf.stem.replace("_chunks", "")
#             logger.info("bulk ingest: %s (paper_id=%s)", cf.name, paper_id)

#             models = load_models_for_paper(paper_id)
#             if not models:
#                 logger.info("no models for %s -> skipping", paper_id)
#                 summary["skipped"] += 1
#                 summary["details"].append({"paper_id": paper_id, "status": "no_models"})
#                 continue

#             # cheap existence check
#             if not force:
#                 try:
#                     existing = get_chunks_for_paper(paper_id, client=client, collection_name=coll_name, limit=1)
#                     if existing and len(existing) >= len(models):
#                         logger.info("collection already has %d chunks for %s; skipping", len(existing), paper_id)
#                         summary["skipped"] += 1
#                         summary["details"].append({"paper_id": paper_id, "status": "skipped_existing", "n_existing": len(existing)})
#                         continue
#                 except Exception:
#                     logger.debug("could not query chroma for existence check", exc_info=True)

#             # compute embeddings for the batch of models


#             adapter = adapter or _build_default_adapter()
#             embs = embed_records(models, adapter=adapter, cache=cache, expected_dim=EMBED_DIM)


#             if not embs or len(embs) != len(models):
#                 raise RuntimeError(f"embeddings length mismatch for {paper_id}")

#             # build add payload
#             chunk_ids = [m.chunk_id for m in models]
#             docs = [m.text for m in models]
#             metadatas = []
#             for m in models:
#                 meta = dict(getattr(m, "meta", {}) or {})
#                 meta.update(
#                     {
#                         "paper_id": getattr(m, "paper_id", paper_id),
#                         "chunk_index": getattr(m, "chunk_index", None),
#                         "char_len": getattr(m, "char_len", None),
#                     }
#                 )
#                 metadatas.append(sanitize_meta_for_chroma(meta))

#             if dry_run:
#                 logger.info("dry-run would add %d chunks for %s", len(chunk_ids), paper_id)
#                 summary["processed"] += 1
#                 summary["details"].append({"paper_id": paper_id, "status": "dry_run", "n_chunks": len(chunk_ids)})
#                 continue

#             add_chunks_batch(chunk_ids=chunk_ids, paper_ids=[paper_id] * len(chunk_ids), previews=docs, metadatas=metadatas, embeddings=embs, client=client, collection_name=coll_name, batch_size=batch_size)

#             # add paper doc (best-effort)
#             try:
#                 preview = docs[0][:200] if docs else ""
#                 add_paper(paper_id, {"paper_id": paper_id, "title": getattr(models[0], "paper_id", paper_id), "n_chunks": len(models), "preview": preview}, client=client, collection_name="papers")
#             except Exception:
#                 logger.debug("add_paper non-fatal failure", exc_info=True)

#             summary["processed"] += 1
#             summary["details"].append({"paper_id": paper_id, "status": "upserted", "n_chunks": len(chunk_ids)})
#         except Exception as exc:
#             tb = traceback.format_exc()
#             logger.exception("bulk ingest failed for %s", cf)
#             summary["failed"] += 1
#             summary["details"].append({"chunk_file": str(cf), "error": str(exc)})
#             _write_failure_dump(cf.stem, {"chunk_file": str(cf), "error": str(exc), "traceback": tb}, failure_dump_dir)
#             continue

#     # persist client best-effort
#     try:
#         persisted = maybe_persist(client)
#         logger.info("maybe_persist returned: %s", persisted)
#     except Exception:
#         logger.debug("maybe_persist failed", exc_info=True)

#     if cache is not None:
#         try:
#             cache.close()
#         except Exception:
#             pass

#     return summary




def ingest_chunks_to_chroma(
    chunks_dir: Path,
    chroma_dir: Path,
    collection: str = "chunks",
    embedding_adapter: Optional[Any] = None,
    cache_db: Optional[Path] = None,
    batch_size: int = 256,
    force: bool = False,
    dry_run: bool = False,
    reset: bool = False,
    failure_dump_dir: Path = Path("/tmp"),
) -> Dict[str, Any]:
    chunks_dir = Path(chunks_dir).expanduser().resolve()
    chroma_dir = Path(chroma_dir).expanduser().resolve()

    client = get_client(persist_directory=chroma_dir, create_if_missing=True)
    logger.info("ingest_chunks_to_chroma client type=%s persist_dir=%s has_persist=%s", type(client), chroma_dir, hasattr(client, "persist"))

    coll_name = collection

    files = sorted(chunks_dir.rglob("*_chunks.jsonl"))
    if not files:
        return {"error": "no_files"}

    if reset:
        shutil.rmtree(str(chroma_dir), ignore_errors=True)
        try:
            Path(cache_db or EMBED_CACHE_DB).unlink()
        except Exception:
            pass
        client = get_client(persist_directory=chroma_dir, create_if_missing=True)
        logger.info("ingest_chunks_to_chroma 2 client type=%s persist_dir=%s has_persist=%s", type(client), chroma_dir, hasattr(client, "persist"))

    embedding_adapter = embedding_adapter or _build_default_adapter()

    cache = None
    if cache_db:
        try:
            cache = EmbeddingCache.open(Path(cache_db))
        except Exception:
            logger.warning("could not open embedding cache %s (continuing without cache)", cache_db)
            cache = None

    summary = {"n_files": len(files), "processed": 0, "skipped": 0, "failed": 0, "details": []}
    for cf in files:
        try:
            paper_id = cf.stem.replace("_chunks", "")
            models = load_models_for_paper(paper_id)
            if not models:
                summary["skipped"] += 1; summary["details"].append({"paper_id": paper_id, "status": "no_models"}); continue

            if not force:
                try:
                    existing_count = get_chunks_for_paper_count(paper_id, client=client, collection_name=coll_name)
                    if existing_count >= len(models):
                        summary["skipped"] += 1; summary["details"].append({"paper_id": paper_id, "status": "skipped_existing", "n_existing": existing_count}); continue
                except Exception:
                    logger.debug("could not query chroma for existence check", exc_info=True)

            embs = embed_records(models, adapter=embedding_adapter, cache=cache, expected_dim=EMBED_DIM, batch_size=min(batch_size,512))

            if len(embs) != len(models):
                raise RuntimeError("embeddings length mismatch")

            chunk_ids = [m.chunk_id for m in models]
            docs = [m.text for m in models]
            metadatas = [sanitize_meta_for_chroma(canonical_meta_from_chunk(m)) for m in models]

            if dry_run:
                summary["processed"] += 1; summary["details"].append({"paper_id": paper_id, "status": "dry_run", "n_chunks": len(chunk_ids)}); continue

            add_chunks_batch(chunk_ids=chunk_ids, paper_ids=[paper_id]*len(chunk_ids), previews=docs, metadatas=metadatas, embeddings=embs, client=client, collection_name=coll_name, batch_size=batch_size)

            # paper doc best-effort
            try:
                preview = docs[0][:200] if docs else ""
                add_paper(paper_id, {"paper_id": paper_id, "title": getattr(models[0], "paper_id", paper_id), "n_chunks": len(models), "preview": preview}, client=client, collection_name="papers")
            except Exception:
                logger.debug("add_paper non-fatal failure", exc_info=True)

            summary["processed"] += 1
            summary["details"].append({"paper_id": paper_id, "status": "upserted", "n_chunks": len(chunk_ids)})

        except Exception as exc:
            tb = traceback.format_exc()
            logger.exception("bulk ingest failed for %s", cf)
            summary["failed"] += 1
            summary["details"].append({"chunk_file": str(cf), "error": str(exc)})
            _write_failure_dump(cf.stem, {"chunk_file": str(cf), "error": str(exc), "traceback": tb}, failure_dump_dir)
            continue

    # persist + close cache once
    try:
        maybe_persist(client)
    except Exception:
        logger.debug("maybe_persist failed", exc_info=True)
    if cache is not None:
        try:
            cache.close()
        except Exception:
            pass

    return summary



# # -------------------------
# # Ingest to Chroma - uses embed_records for canonical models
# # -------------------------
# def ingest_files_to_chroma(chunk_files: List[Path], client, collection, adapter, cache=None, batch_size=128, expected_dim=None):
#     """
#     Read chunk jsonl files and add them into Chroma using the provided client and collection objects.
#     Accepts:
#       - chunk_files: list of Path to *_chunks.jsonl or similar
#       - client: chroma client instance
#       - collection: chroma collection instance (preferred)
#       - adapter: low-level adapter (object with .batch or callable)
#       - cache: EmbeddingCache instance (optional) - if provided, embed_records will open its own cache unless None
#     Returns dict: {"total_seen": int, "added": int, "skipped": int, "errors": int}
#     """
#     total_seen = 0
#     added = 0
#     skipped = 0
#     errors_cnt = 0

#     batch_ids: List[str] = []
#     batch_docs: List[str] = []
#     batch_embs: List[List[float]] = []
#     batch_meta: List[Dict[str, Any]] = []

#     # internal flush uses safe_add_batch
#     def flush():
#         nonlocal added, batch_ids, batch_docs, batch_embs, batch_meta
#         if not batch_ids:
#             return

#         # filter invalid embeddings defensively
#         good_idx = [i for i, emb in enumerate(batch_embs) if is_valid_embedding(emb, expected_dim=expected_dim)]
#         if not good_idx:
#             batch_ids.clear(); batch_docs.clear(); batch_embs.clear(); batch_meta.clear()
#             return

#         ids = [batch_ids[i] for i in good_idx]
#         docs = [batch_docs[i] for i in good_idx]
#         embs = [list(batch_embs[i]) for i in good_idx]
#         metas = [sanitize_meta_for_chroma(batch_meta[i]) for i in good_idx]

#         try:
#             safe_add_batch(collection, ids=ids, documents=docs, embeddings=embs, metadatas=metas)
#             added += len(ids)
#         except Exception as e:
#             logger.warning("Chroma add failed for this batch: %s", e)

#         batch_ids.clear(); batch_docs.clear(); batch_embs.clear(); batch_meta.clear()

#     # main loop: read files, build minimal models then call embed_records in batches
#     buffer_models: List[CanonicalChunk] = []
#     buffer_meta: List[Dict[str, Any]] = []

#     for jf in chunk_files:
#         logger.info("processing chunk file %s", jf)
#         for rec in read_chunks_jsonl(jf):
#             total_seen += 1
#             # defensive keys: chunk_id / id / fallback
#             chunk_id = rec.get("chunk_id") or rec.get("id") or f"{jf.stem}::{total_seen}"
#             raw_text = rec.get("text", "") or rec.get("page_content", "")
#             text = normalize_text_field(raw_text)
#             if not text or len(text.strip()) < 8:
#                 skipped += 1
#                 continue

#             meta = {"paper_id": rec.get("paper_id") or jf.stem, "pages": rec.get("pages")}
#             # build canonical-like model (we don't require header_path/pages/more)
#             try:
#                 model = CanonicalChunk(
#                     chunk_id=chunk_id,
#                     paper_id=meta["paper_id"],
#                     text=text,
#                     chunk_index=int(rec.get("chunk_index") or 0),
#                     char_len=int(rec.get("char_len") or len(text)),
#                     header_path=rec.get("header_path"),
#                     pages=rec.get("pages"),
#                     meta=rec.get("meta") or {}
#                 )
#             except Exception:
#                 # fallback minimal
#                 model = CanonicalChunk(
#                     chunk_id=chunk_id,
#                     paper_id=meta["paper_id"],
#                     text=text,
#                     chunk_index=int(rec.get("chunk_index") or 0),
#                     char_len=len(text),
#                 )

#             buffer_models.append(model)
#             buffer_meta.append(meta)

#             # flush embeddings in batches to avoid large memory
#             if len(buffer_models) >= batch_size:
#                 try:
#                     embs = embed_records(buffer_models, adapter=adapter, cache_db=None if cache is None else None, use_cache=(cache is not None), expected_dim=expected_dim)
#                 except Exception as e:
#                     logger.exception("embed_records failed for batch: %s", e)
#                     errors_cnt += len(buffer_models)
#                     buffer_models.clear(); buffer_meta.clear()
#                     continue

#                 # push to local batches for Chroma add
#                 for m, emb, mm in zip(buffer_models, embs, buffer_meta):
#                     if emb is None or not is_valid_embedding(emb, expected_dim=expected_dim):
#                         skipped += 1
#                         continue
#                     batch_ids.append(m.chunk_id)
#                     batch_docs.append(m.text)
#                     batch_embs.append(emb)
#                     batch_meta.append(mm)

#                 buffer_models.clear(); buffer_meta.clear()

#                 # attempt to flush to Chroma
#                 if len(batch_ids) >= batch_size:
#                     flush()

#     # final embed for leftover models
#     if buffer_models:
#         try:
#             embs = embed_records(buffer_models, adapter=adapter, cache_db=None if cache is None else None, use_cache=(cache is not None), expected_dim=expected_dim)
#         except Exception as e:
#             logger.exception("embed_records failed for final batch: %s", e)
#             errors_cnt += len(buffer_models)
#             embs = []
#         for m, emb, mm in zip(buffer_models, embs or [], buffer_meta):
#             if emb is None or not is_valid_embedding(emb, expected_dim=expected_dim):
#                 skipped += 1
#                 continue
#             batch_ids.append(m.chunk_id)
#             batch_docs.append(m.text)
#             batch_embs.append(emb)
#             batch_meta.append(mm)

#     # final flush to push remaining items
#     flush()

#     return {"total_seen": total_seen, "added": added, "skipped": skipped, "errors": errors_cnt}




def text_to_id(text: str, prefix: Optional[str] = None) -> str:
    import hashlib
    h = hashlib.sha1((text or "").encode("utf8")).hexdigest()
    if prefix:
        return f"{prefix}::{h[:10]}"
    return h[:10]



# ---------- convenience for embedding texts ----------
def batch_embed_records(
    texts: Iterable[str],
    ids: Optional[Iterable[str]] = None,
    adapter: Optional[Callable] = None,
    batch_size: int = 256,
) -> List[List[float]]:
    """Embed a list of texts by synthesizing minimal CanonicalChunk objects and calling embed_records."""
    texts = list(texts)
    ids = list(ids) if ids is not None else [text_to_id(t) for t in texts]
    if len(ids) != len(texts):
        raise ValueError("ids length mismatch")

    tmp_models: List[CanonicalChunk] = []
    for tid, txt in zip(ids, texts):
        tmp_models.append(CanonicalChunk(chunk_id=tid, paper_id="__ad_hoc__", text=txt, chunk_index=0, char_len=len(txt or "")))

    out: List[List[float]] = []
    for i in range(0, len(tmp_models), batch_size):
        batch = tmp_models[i : i + batch_size]
        out_batch = embed_records(batch, adapter=adapter) if adapter is not None else embed_records(batch)
        # embs = embed_records(models, adapter=adapter, cache=cache, expected_dim=expected_dim) ?
        out.extend(out_batch)
    return out




# def embed_text_batch(texts: List[str],
#                ids: Optional[Iterable[str]] = None,
#                adapter: Optional[Callable] = None,
#                cache_db: Optional[Path] = None,
#                use_cache: bool = True,
#                expected_dim: Optional[int] = None,
#                batch_size: int = 256) -> List[List[float]]:
#     ids = list(ids) if ids is not None else [text_to_id(t) for t in texts]
#     if len(ids) != len(texts):
#         raise ValueError("ids length mismatch")
#     # build minimal CanonicalChunk-like objects (we only need chunk_id and text)
#     tmp_models = []
#     for tid, txt in zip(ids, texts):
#         tmp = CanonicalChunk(
#             chunk_id=tid,
#             paper_id="__ad_hoc__",
#             text=txt,
#             chunk_index=0,
#             char_len=len(txt or ""),
#         )
#         tmp_models.append(tmp)
#     # chunked calls to avoid memory/API bursts
#     out = []
#     for i in range(0, len(tmp_models), batch_size):
#         batch = tmp_models[i:i + batch_size]
#         out_batch = embed_records(batch, adapter=adapter, cache_db=cache_db, use_cache=use_cache, expected_dim=expected_dim)
#         out.extend(out_batch)
#     return out


# ---------- CLI ----------
def cli():
    p = argparse.ArgumentParser(prog="embed_runner")
    p.add_argument("--mode", choices=["per-paper", "bulk"], default="per-paper")
    p.add_argument("--papers", nargs="*", help="paper ids to process (per-paper mode)")
    p.add_argument("--input", "-i", default="store/chunks", help="chunks dir (bulk)")
    p.add_argument("--chroma-dir", default=str(CHROMA_DIR))
    p.add_argument("--collection", default="chunks")
    p.add_argument("--adapter", default="placeholder")
    p.add_argument("--dim", type=int, default=EMBED_DIM)
    p.add_argument("--batch", type=int, default=256)
    p.add_argument("--cache-db", default=str(EMBED_CACHE_DB))
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--reset", action="store_true")
    p.add_argument("--failure-dump-dir", default="/tmp")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # adapter selection
    adapter = PlaceholderAdapter(dim=args.dim) if args.adapter == "placeholder" else _build_default_adapter()

    # cache
    cache = None
    try:
        cache = EmbeddingCache.open(Path(args.cache_db))
    except Exception:
        logger.warning("could not open embedding cache %s (continuing without cache)", args.cache_db)

    client = get_client(persist_directory=Path(args.chroma_dir))
    logger.info("embed_runner client type=%s persist_dir=%s", type(client), args.chroma_dir)

    coll = get_or_create_collection(client=client, name=args.collection)


    # chunks_dir: Path,
    # chroma_dir: Path,
    # collection: str = "chunks",
    # adapter: Optional[Callable] = None,
    # cache_db: Optional[Path] = None,
    # batch_size: int = 256,
    # force: bool = False,
    # dry_run: bool = False,
    # reset: bool = False,
    # failure_dump_dir: Path = Path("/tmp"),


    results = []
    if args.mode == "bulk":
        summary = ingest_chunks_to_chroma(
            chunks_dir=Path(args.input),
            chroma_dir=Path(args.chroma_dir),
            collection=args.collection,
            cache_db=args.cache_db,
            batch_size=args.batch,
            force=args.force,
            dry_run=args.dry_run,
            reset=args.reset,
            failure_dump_dir=Path(args.failure_dump_dir),
        )
        results.append(summary)
    else:
        # per-paper
        papers = args.papers or [f.stem.replace("_chunks", "") for f in sorted(Path("store/chunks").rglob("*_chunks.jsonl"))]
        for pid in papers:
            res = embed_and_upsert(
                paper_id=pid,
                client=client,
                collection_name=args.collection,
                adapter=adapter,
                cache=cache,
                dry_run=args.dry_run,
                force=args.force,
                batch_size=args.batch,
                failure_dump_dir=Path(args.failure_dump_dir),
            )
            results.append(res)

    # persist client best-effort
    try:
        maybe_persist(client)
    except Exception:
        logger.debug("maybe_persist failed", exc_info=True)

    if cache is not None:
        try:
            cache.close()
        except Exception:
            pass

    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cli()
