#!/usr/bin/env python3
# pipeline/parsers/runner.py
"""
Streamlined TEI runner.

Responsibilities:
 - parse TEI XML -> canonical chunks JSONL via write_chunks_jsonl (atomic behavior delegated there)
 - produce .done markers to avoid reprocessing (idempotency)
 - optionally call embedding/upsert for newly-written papers by delegating to embed_runner.embed_and_upsert
 - keep failure dumps for debugging

Notes:
 - Grobid ingestion (PDF -> TEI) is intentionally NOT included here. Use pipeline/ingestion/grobid_ingest.py.
 - Embedding/upsert uses the same helpers as pipeline.runners.embed_runner to avoid duplication.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
import os
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

# TEI parsing + canonicalization
from pipeline.parsers.tei_parser import parse_tei_text, parse_tei_file
from pipeline.parsers.canonicalize import chunks_to_models, make_paper_meta
from backend.app.schemas import CanonicalChunk  # add import at top if missing

# FS helpers
from backend.app.chunks_fs import write_chunks_jsonl, read_chunks_jsonl
from backend.app.papers_fs import save_paper_metadata_to_fs

# small utils
from pipeline.adapter.grobid_ingest import _sanitize_filename  # keep filename policy consistent with grobid ingest

# embedding/upsert delegation (reuse embed_runner behavior)
from pipeline.producer.embed_runner import embed_and_upsert  # streamlined embed runner
from shared.chroma_client import get_client

from shared.chroma_helpers import sanitize_meta_for_chroma
from pipeline.writers.chunk_set_writer import write_chunk_set_artifact, default_chunk_sets_dir

logger = logging.getLogger("pipeline.parsers.runner")
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


# ---------- marker helpers ----------
def _done_marker_path(chunks_dir: Path, paper_id: str) -> Path:
    return Path(chunks_dir) / ".done" / f"{_sanitize_filename(paper_id)}.json"


def _write_done_marker(out_dir: Path, paper_id: str, meta: Dict[str, Any]) -> None:
    ddir = Path(out_dir)
    ddir.mkdir(parents=True, exist_ok=True)
    dpath = _done_marker_path(out_dir, paper_id)
    tmp = dpath.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf8")
    os.replace(str(tmp), str(dpath))


def _read_done_marker(in_dir: Path, paper_id: str) -> Optional[Dict[str, Any]]:
    dpath = _done_marker_path(in_dir, paper_id)
    if not dpath.exists():
        return None
    try:
        return json.loads(dpath.read_text(encoding="utf8"))
    except Exception:
        return None


def _failure_dump(failures_dir: Path, name: str, payload: Dict[str, Any]) -> None:
    try:
        failures_dir.mkdir(parents=True, exist_ok=True)
        short = hashlib.sha1(name.encode("utf8")).hexdigest()[:8]
        fname = failures_dir / f"{_sanitize_filename(name)}.{short}.fail.json"
        fname.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf8")
        logger.info("wrote failure dump %s", fname)
    except Exception:
        logger.debug("couldn't write failure dump", exc_info=True)


# ---------- 1) Parse TEIs to chunks (idempotent) ----------

# python3 pipeline/runner/tei_runner.py /home/matias/Documents/paper-kb/downloads/data/xmls /home/matias/Documents/paper-kb/store/chunks --min-len 50 --dry-run


from backend.app.chunks_fs import _to_mapping

def parse_teis_to_chunks(
    tei_dir: Path,
    chunks_dir: Path,
    min_len: int = 50,
    dry_run: bool = False,
    force: bool = False,
    failures_subdir: str = "failures",
    emit_chunk_set_artifact: bool = True,
    chunk_set_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Scan tei_dir for TEI XML files and produce <paper_id>_chunks.jsonl files in chunks_dir
    - creates a .done marker per paper_id to avoid reprocessing
    - returns a summary dict
    """
    tei_dir = Path(tei_dir).expanduser().resolve()
    chunks_dir = Path(chunks_dir).expanduser().resolve()
    chunks_dir.mkdir(parents=True, exist_ok=True)
    failures_dir = chunks_dir / failures_subdir
    failures_dir.mkdir(parents=True, exist_ok=True)

    tei_files = sorted(
        [p for p in tei_dir.iterdir() if p.is_file() and (p.suffix.lower().endswith(".xml") or p.name.lower().endswith(".tei.xml"))]
    )
    summary = {"n_input_files": len(tei_files), "n_written": 0, "n_skipped": 0, "n_failures": 0, "n_chunk_set_artifacts": 0, "files": [], "chunk_set_artifacts": [], "errors": []}

    for tei_path in tei_files:

        try:

            logger.info("parse: %s", tei_path.name)
            tei_text = tei_path.read_text(encoding="utf8")
            parsed = parse_tei_text(tei_text)
            title = parsed.get("title") or tei_path.stem

            # paper_id = parsed.get("paper_id") or parsed.get("pid") or (_sanitize_filename(title) or tei_path.stem)


            base = _sanitize_filename(parsed.get("paper_id") or parsed.get("pid") or title or tei_path.stem)[:120]
            suffix = "_" + hashlib.sha1(str(tei_path).encode("utf8")).hexdigest()[:8]
            paper_id = f"{base}{suffix}"


            raw_chunks = parsed.get("chunks", []) or []

            # filter by min_len
            filtered = [c for c in raw_chunks if len((c.get("text") or "").strip()) >= int(min_len)]
            if not filtered:
                logger.info("parse: skipping %s (no chunks after min_len)", tei_path.name)
                summary["n_skipped"] += 1
                summary["files"].append({"tei": str(tei_path), "paper_id": paper_id, "status": "skipped_no_chunks"})
                continue

            # idempotency check
            done_root = chunks_dir / 'papers'
            done = _read_done_marker(done_root, paper_id)
            if done and not force:
                logger.info("parse: skipping %s (done marker exists)", tei_path.name)
                summary["n_skipped"] += 1
                summary["files"].append({"tei": str(tei_path), "paper_id": paper_id, "status": "skipped_done"})
                continue


            # --- before writing ----
            # canonical_models = chunks_to_models(...)
            # stabilize chunk_index already performed above

            canonical_models = chunks_to_models(title, paper_id, filtered)
            # stabilize chunk_index
            for idx, model in enumerate(canonical_models):
                if getattr(model, "chunk_index", None) is None:
                    model.chunk_index = idx

            # if dry_run:
            #     logger.info("parse: dry-run would write %d chunks for %s", len(canonical_models), paper_id)
            #     summary["files"].append({"tei": str(tei_path), "paper_id": paper_id, "status": "dry_run", "n_chunks": len(canonical_models)})
            #     continue


            normalized_models = []
            for m in canonical_models:
                if isinstance(m, CanonicalChunk):
                    normalized_models.append(m)
                elif isinstance(m, dict):
                    # coerce dict -> Pydantic model (will raise if missing required fields)
                    try:
                        normalized_models.append(CanonicalChunk(**m))
                    except Exception as e:
                        logger.warning("parse: could not coerce chunk dict into CanonicalChunk; skipping snippet=%.120s err=%s", (m.get("text") or "")[:120], e)
                        continue
                else:
                    # unknown shape: try best-effort conversion
                    try:
                        normalized_models.append(CanonicalChunk(**(m.__dict__ if hasattr(m, "__dict__") else {})))
                    except Exception:
                        logger.debug("parse: unexpected chunk type, skipping: %r", type(m))
                        continue

            # if dry-run handled earlier; now check n_chunks guard
            n_chunks = len(normalized_models)
            if n_chunks == 0:
                failure = {
                    "paper_id": paper_id,
                    "title": title,
                    "source": str(tei_path),
                    "reason": "no_chunks_after_filter_or_invalid",
                    "n_raw_chunks": len(raw_chunks),
                    "timestamp": time.time(),
                }
                (failures_dir / f"{_sanitize_filename(paper_id)}.no_chunks.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf8")
                logger.warning("parse: no chunks for %s -> wrote failure dump", paper_id)
                summary["n_skipped"] += 1
                summary["files"].append({"tei": str(tei_path), "paper_id": paper_id, "status": "no_chunks", "n_chunks": 0})
                continue


            payload = [_to_mapping(m) for m in normalized_models]


            # WRITE: keep legacy backend-compatible JSONL output.
            # This remains a legacy/internal side effect for backend compatibility,
            # not the canonical public contract surface.
            if not dry_run:
                write_chunks_jsonl(paper_id, payload, build_index=True)

            # WRITE: canonical public Chunk Bus-compatible artifact.
            # This is the artifact downstream consumers should prefer over Chroma or store/chunks.
            chunk_set_path = None
            if emit_chunk_set_artifact and not dry_run:
                run_id = f"paper_tei_parse_{int(time.time())}_{hashlib.sha1(str(tei_path).encode('utf8')).hexdigest()[:8]}"
                chunk_set_path = write_chunk_set_artifact(
                    normalized_models,
                    source_items=[str(tei_path)],
                    run_id=run_id,
                    out_dir=Path(chunk_set_dir).expanduser().resolve() if chunk_set_dir else default_chunk_sets_dir(),
                    producer="paper-kb",
                    entrypoint="paper_tei_parse",
                    fallback_source_file=tei_path.name,
                )
                summary["n_chunk_set_artifacts"] += 1
                summary["chunk_set_artifacts"].append(str(chunk_set_path))

            # save paper-level metadata (coerce to dict appropriately)
            if not dry_run:
                try:
                    pm = make_paper_meta(title, paper_id, normalized_models, {"source_file": tei_path.name})
                    # prefer model_dump when available, fallback to dict for v1 compatibility
                    pm_payload = _to_mapping(pm)
                    save_paper_metadata_to_fs(pm_payload)
                except Exception:
                    logger.debug("could not save paper metadata", exc_info=True)

                # done marker
                done_meta = {"paper_id": paper_id, "n_chunks": n_chunks, "title": title, "written_at": time.time(), "source_file": tei_path.name}
                _write_done_marker(done_root, paper_id, done_meta)
            logger.info("parse: wrote %d chunks for %s", n_chunks, paper_id)
            summary["n_written"] += 1
            summary["files"].append({"tei": str(tei_path), "paper_id": paper_id, "status": "dry_run" if dry_run else "written", "n_chunks": n_chunks, "chunk_set_path": str(chunk_set_path) if chunk_set_path else None})




        except Exception as exc:
            tb = traceback.format_exc()
            logger.exception("parse failed: %s", tei_path)
            err = {"tei": str(tei_path), "error": str(exc), "traceback": tb}
            summary["n_failures"] += 1
            summary["errors"].append(err)
            _failure_dump(failures_dir, tei_path.stem, err)
            continue

    return summary


# ---------- 2) Main orchestration (parse + optional embed/upsert delegation) ----------
def main(
    input_dir: str,
    out_dir: str,
    min_len: int = 50,
    dry_run: bool = False,
    force: bool = False,
    do_embed: bool = False,
    do_upsert: bool = False,
    chroma_dir: Optional[str] = None,
    collection: str = "chunks",
    batch_size: int = 512,
    chunk_set_dir: Optional[str] = None,
    emit_chunk_set_artifact: bool = True,
) -> Dict[str, Any]:
    """
    CLI entrypoint behavior:
     - always runs parse_teis_to_chunks(input_dir -> out_dir)
     - if do_embed or do_upsert are True, will call embed_and_upsert for each written/available paper
    """
    tei_dir = Path(input_dir).expanduser().resolve()
    chunks_dir = Path(out_dir).expanduser().resolve()
    chroma_dir = Path(chroma_dir).expanduser().resolve() if chroma_dir else None

    parse_summary = parse_teis_to_chunks(tei_dir, chunks_dir, min_len=min_len, dry_run=dry_run, force=force, emit_chunk_set_artifact=emit_chunk_set_artifact, chunk_set_dir=Path(chunk_set_dir).expanduser().resolve() if chunk_set_dir else None)

    embed_summary = None
    if (do_embed or do_upsert) and not dry_run:
        # pick up paper ids to process: those that have chunk files
        chunk_files = sorted(list(chunks_dir.rglob("*_chunks.jsonl")))
        if not chunk_files:
            logger.warning("no chunk files found in %s; embedding step skipped", chunks_dir)
            embed_summary = {"error": "no_chunks"}
        else:
            client = get_client(persist_directory=chroma_dir)
            logger.info("main (tei_runner) client type=%s persist_dir=%s", type(client), chroma_dir)

            embed_results: List[Dict[str, Any]] = []
            for cf in chunk_files:
                pid = cf.stem.replace("_chunks", "")
                try:
                    # delegate to embed_runner.embed_and_upsert (keeps behavior shared)
                    res = embed_and_upsert(
                        paper_id=pid,
                        client=client,
                        collection_name=collection,
                        adapter=None,
                        cache=None,
                        dry_run=dry_run,
                        force=force,
                        batch_size=batch_size,
                    )
                    embed_results.append(res)
                except Exception as exc:
                    tb = traceback.format_exc()
                    logger.exception("embed step failed for %s", pid)
                    embed_results.append({"paper_id": pid, "status": "failed", "error": str(exc), "traceback": tb})
            # persist client
            if client is not None:
                try:
                    from shared.chroma_helpers import maybe_persist
                    maybe_persist(client)
                except Exception:
                    logger.debug("maybe_persist failed", exc_info=True)
            embed_summary = {"n": len(embed_results), "details": embed_results}

    return {"parse": parse_summary, "embed": embed_summary}


# ---------- CLI ----------
def cli():
    p = argparse.ArgumentParser(prog="tei_runner")
    p.add_argument("input_dir", help="directory with TEI XML files")
    p.add_argument("out_dir", help="chunks output directory (store/chunks)")
    p.add_argument("--min-len", type=int, default=50)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="re-parse TEIs even if .done markers exist")
    p.add_argument("--embed", action="store_true", help="after parsing, run embed+upsert using embed_runner")
    p.add_argument("--upsert", action="store_true", help="same as --embed (kept for compatibility)")
    p.add_argument("--chroma-dir", default=None, help="path to chroma persist dir for embedding/upsert")
    p.add_argument("--collection", default="chunks")
    p.add_argument("--batch", type=int, default=512)
    p.add_argument("--chunk-set-dir", default=None, help="directory for canonical Chunk Bus chunk_set artifacts")
    p.add_argument("--no-chunk-set", action="store_true", help="disable canonical chunk_set artifact emission")
    args = p.parse_args()

    summary = main(
        args.input_dir,
        args.out_dir,
        min_len=args.min_len,
        dry_run=args.dry_run,
        force=args.force,
        do_embed=(args.embed or args.upsert),
        do_upsert=(args.embed or args.upsert),
        chroma_dir=args.chroma_dir,
        collection=args.collection,
        batch_size=args.batch,
        chunk_set_dir=args.chunk_set_dir,
        emit_chunk_set_artifact=not args.no_chunk_set,
    )
    print(json.dumps({"summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cli()
