# pipeline/adapter/manager.py
"""Bounded paper-kb pipeline manager.

This manager keeps paper-kb as the owner of source/PDF/TEI orchestration while
allowing the lower-level embedding runtime to live in the reusable KB module.

Ownership decisions:
- GROBID and source collection remain paper-kb adapters.
- TEI parsing is paper-specific.
- TEI parse emits legacy backend chunks plus canonical chunk_set artifacts.
- Chroma upsert is an optional internal materialization step, not a public contract.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from shared.config import CHUNKS_DIR, TEI_DIR, PDF_DIR, CHROMA_DIR
except Exception:  # lightweight fallback for import smoke tests
    REPO_ROOT = Path(__file__).resolve().parents[2]
    PDF_DIR = REPO_ROOT / "downloads"
    TEI_DIR = REPO_ROOT / "downloads" / "data" / "xmls"
    CHUNKS_DIR = REPO_ROOT / "store" / "chunks"
    CHROMA_DIR = REPO_ROOT / "store" / "chroma"

from pipeline.adapter.grobid_ingest import generate_teis_from_pdfs
from pipeline.producer.tei_runner import parse_teis_to_chunks

logger = logging.getLogger("pipeline.adapter.manager")
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


def _maybe_ingest_chunks_to_chroma(*args, **kwargs):
    """Import the internal materializer lazily to keep parse-only flows light."""
    from pipeline.producer.embed_runner import ingest_chunks_to_chroma

    return ingest_chunks_to_chroma(*args, **kwargs)


def full_run(
    *,
    pdf_dir: Optional[Path] = None,
    tei_dir: Optional[Path] = None,
    chunks_dir: Optional[Path] = None,
    chroma_dir: Optional[Path] = None,
    do_grobid: bool = True,
    do_parse: bool = True,
    do_ingest: bool = False,
    grobid_opts: Optional[Dict[str, Any]] = None,
    parse_opts: Optional[Dict[str, Any]] = None,
    ingest_opts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the bounded paper pipeline.

    The canonical public output of the parse stage is a chunk_set artifact.
    Legacy store/chunks JSONL and Chroma materialization remain compatibility /
    internal side effects.
    """
    grobid_opts = grobid_opts or {}
    parse_opts = parse_opts or {}
    ingest_opts = ingest_opts or {}

    pdf_dir = Path(pdf_dir or PDF_DIR).expanduser().resolve()
    tei_dir = Path(tei_dir or TEI_DIR).expanduser().resolve()
    chunks_dir = Path(chunks_dir or CHUNKS_DIR).expanduser().resolve()
    chroma_dir = Path(chroma_dir or CHROMA_DIR).expanduser().resolve()

    result: Dict[str, Any] = {
        "roles": {
            "grobid": "adapter",
            "parse": "chunk_bus_producer_plus_legacy_backend_writer",
            "ingest": "internal_chroma_materializer",
        },
        "grobid": None,
        "parse": None,
        "ingest": None,
    }

    if do_grobid:
        result["grobid"] = generate_teis_from_pdfs(pdf_dir, tei_dir, **grobid_opts)

    if do_parse:
        result["parse"] = parse_teis_to_chunks(tei_dir, chunks_dir, **parse_opts)

    if do_ingest:
        result["ingest"] = _maybe_ingest_chunks_to_chroma(chunks_dir, chroma_dir, **ingest_opts)

    return result


def _parse_args_and_run() -> None:
    p = argparse.ArgumentParser(prog="pipeline.adapter.manager", description="paper-kb PDF/TEI/chunk_set manager")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grobid", help="POST PDFs to GROBID and write TEI files")
    g.add_argument("pdf_dir")
    g.add_argument("out_tei_dir")
    g.add_argument("--recursive", action="store_true")
    g.add_argument("--timeout", type=int, default=180)
    g.add_argument("--max-retries", type=int, default=3)
    g.add_argument("--max-files", type=int, default=None)
    g.add_argument("--force", action="store_true")

    pr = sub.add_parser("parse", help="Parse TEIs to legacy chunks and canonical chunk_set artifacts")
    pr.add_argument("tei_dir")
    pr.add_argument("chunks_dir")
    pr.add_argument("--min-len", type=int, default=50)
    pr.add_argument("--dry-run", action="store_true")
    pr.add_argument("--force", action="store_true")
    pr.add_argument("--chunk-set-dir", default=None)
    pr.add_argument("--no-chunk-set", action="store_true")

    ing = sub.add_parser("ingest", help="Internal materialization: embed + upsert legacy chunks into Chroma")
    ing.add_argument("chunks_dir")
    ing.add_argument("chroma_dir")
    ing.add_argument("--collection", default="chunks")
    ing.add_argument("--batch-size", type=int, default=256)
    ing.add_argument("--force", action="store_true")
    ing.add_argument("--dry-run", action="store_true")

    f = sub.add_parser("full-run", help="grobid -> parse -> optional internal Chroma materialization")
    f.add_argument("--pdf-dir", default=str(PDF_DIR))
    f.add_argument("--tei-dir", default=str(TEI_DIR))
    f.add_argument("--chunks-dir", default=str(CHUNKS_DIR))
    f.add_argument("--chroma-dir", default=str(CHROMA_DIR))
    f.add_argument("--no-grobid", dest="do_grobid", action="store_false")
    f.add_argument("--no-parse", dest="do_parse", action="store_false")
    f.add_argument("--ingest", dest="do_ingest", action="store_true", help="also run internal Chroma materialization")
    f.add_argument("--min-len", type=int, default=50)
    f.add_argument("--force", action="store_true")
    f.add_argument("--dry-run", action="store_true")
    f.add_argument("--chunk-set-dir", default=None)

    args = p.parse_args()

    if args.cmd == "grobid":
        res = generate_teis_from_pdfs(
            Path(args.pdf_dir),
            Path(args.out_tei_dir),
            recursive=args.recursive,
            timeout=args.timeout,
            max_retries=args.max_retries,
            max_files=args.max_files,
            force=args.force,
        )
    elif args.cmd == "parse":
        res = parse_teis_to_chunks(
            Path(args.tei_dir),
            Path(args.chunks_dir),
            min_len=args.min_len,
            dry_run=args.dry_run,
            force=args.force,
            emit_chunk_set_artifact=not args.no_chunk_set,
            chunk_set_dir=Path(args.chunk_set_dir).expanduser().resolve() if args.chunk_set_dir else None,
        )
    elif args.cmd == "ingest":
        res = _maybe_ingest_chunks_to_chroma(
            Path(args.chunks_dir),
            Path(args.chroma_dir),
            collection=args.collection,
            batch_size=args.batch_size,
            force=args.force,
            dry_run=args.dry_run,
        )
    else:
        res = full_run(
            pdf_dir=Path(args.pdf_dir),
            tei_dir=Path(args.tei_dir),
            chunks_dir=Path(args.chunks_dir),
            chroma_dir=Path(args.chroma_dir),
            do_grobid=args.do_grobid,
            do_parse=args.do_parse,
            do_ingest=args.do_ingest,
            grobid_opts={"recursive": True} if args.do_grobid else {},
            parse_opts={
                "min_len": args.min_len,
                "dry_run": args.dry_run,
                "force": args.force,
                "chunk_set_dir": Path(args.chunk_set_dir).expanduser().resolve() if args.chunk_set_dir else None,
            },
            ingest_opts={"batch_size": 256, "force": args.force, "dry_run": args.dry_run},
        )

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _parse_args_and_run()
