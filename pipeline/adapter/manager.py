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
import socket
import time
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

from pipeline.corpus import resolve_corpus_paths

logger = logging.getLogger("pipeline.adapter.manager")
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


def _maybe_ingest_chunks_to_chroma(*args, **kwargs):
    """Import the internal materializer lazily to keep parse-only flows light."""
    from pipeline.producer.embed_runner import ingest_chunks_to_chroma

    return ingest_chunks_to_chroma(*args, **kwargs)




def _resolve_runtime_paths(*, corpus: Optional[str], pdf_dir: Optional[Path], tei_dir: Optional[Path], chunks_dir: Optional[Path], chunk_set_dir: Optional[Path]) -> Dict[str, Path | None]:
    corpus_paths = None
    if corpus:
        corpus_paths = resolve_corpus_paths(corpus).ensure_dirs()

    resolved_pdf_dir = Path(pdf_dir).expanduser().resolve() if pdf_dir else (corpus_paths.pdfs if corpus_paths else None)
    resolved_tei_dir = Path(tei_dir).expanduser().resolve() if tei_dir else (corpus_paths.xmls if corpus_paths else None)
    resolved_chunks_dir = Path(chunks_dir).expanduser().resolve() if chunks_dir else (corpus_paths.chunks if corpus_paths else None)
    resolved_chunk_set_dir = Path(chunk_set_dir).expanduser().resolve() if chunk_set_dir else (corpus_paths.chunk_sets if corpus_paths else None)

    return {
        "pdf_dir": resolved_pdf_dir,
        "tei_dir": resolved_tei_dir,
        "chunks_dir": resolved_chunks_dir,
        "chunk_set_dir": resolved_chunk_set_dir,
    }


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
    corpus: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the bounded paper pipeline.

    The canonical public output of the parse stage is a chunk_set artifact.
    Legacy store/chunks JSONL and Chroma materialization remain compatibility /
    internal side effects.
    """
    grobid_opts = grobid_opts or {}
    parse_opts = parse_opts or {}
    ingest_opts = ingest_opts or {}

    runtime_paths = _resolve_runtime_paths(
        corpus=corpus,
        pdf_dir=pdf_dir or Path(PDF_DIR),
        tei_dir=tei_dir or Path(TEI_DIR),
        chunks_dir=chunks_dir or Path(CHUNKS_DIR),
        chunk_set_dir=parse_opts.get("chunk_set_dir") if isinstance(parse_opts, dict) else None,
    )
    pdf_dir = runtime_paths["pdf_dir"]
    tei_dir = runtime_paths["tei_dir"]
    chunks_dir = runtime_paths["chunks_dir"]
    chroma_dir = Path(chroma_dir or CHROMA_DIR).expanduser().resolve()
    if runtime_paths.get("chunk_set_dir") is not None and "chunk_set_dir" not in parse_opts:
        parse_opts["chunk_set_dir"] = runtime_paths["chunk_set_dir"]

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
        from pipeline.adapter.grobid_ingest import generate_teis_from_pdfs
        result["grobid"] = generate_teis_from_pdfs(pdf_dir, tei_dir, **grobid_opts)

    if do_parse:
        from pipeline.producer.tei_runner import parse_teis_to_chunks
        result["parse"] = parse_teis_to_chunks(tei_dir, chunks_dir, **parse_opts)

    if do_ingest:
        result["ingest"] = _maybe_ingest_chunks_to_chroma(chunks_dir, chroma_dir, **ingest_opts)

    return result


def _is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, int(port))) != 0


def _probe_grobid(url: Optional[str] = None, timeout: float = 1.5) -> bool:
    try:
        import requests
        from shared.config import GROBID_URL
        target = url or GROBID_URL
        r = requests.get(target, timeout=timeout)
        return r.status_code < 500
    except Exception:
        return False


def _validate_chunk_set_local(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"invalid_json: {exc}", "null_header_path": 0, "duplicate_chunk_ids": 0}

    chunks = payload.get("chunks") or []
    if not isinstance(chunks, list):
        return {"ok": False, "error": "chunks_not_list", "null_header_path": 0, "duplicate_chunk_ids": 0}

    null_header = 0
    seen = set()
    dupes = 0
    for ch in chunks:
        if not isinstance(ch, dict):
            continue
        if ch.get("header_path") in (None, "", []):
            null_header += 1
        cid = ch.get("chunk_id")
        if cid in seen:
            dupes += 1
        elif cid is not None:
            seen.add(cid)
    return {"ok": True, "error": None, "null_header_path": null_header, "duplicate_chunk_ids": dupes}


def run_doctor(*, corpus: str, strict: bool = False, as_json: bool = False, check_grobid: bool = False, port: Optional[int] = None) -> Dict[str, Any]:
    cp = resolve_corpus_paths(corpus).ensure_dirs()

    pdfs = sorted(cp.pdfs.glob("*.pdf")) if cp.pdfs.exists() else []
    xmls = sorted([p for p in cp.xmls.glob("*.xml") if p.is_file()]) if cp.xmls.exists() else []
    chunk_sets = sorted(cp.chunk_sets.glob("*.chunk_set.json")) if cp.chunk_sets.exists() else []
    review_csvs = sorted(cp.review.glob("*.csv")) if cp.review.exists() else []

    failures = []
    for d in (cp.xmls / "failures", cp.chunks / "failures"):
        if d.exists():
            failures.extend(sorted(d.glob("*.fail.json")))

    validation = []
    invalid_count = 0
    null_header_count = 0
    duplicate_chunk_ids = 0
    for cs in chunk_sets:
        v = _validate_chunk_set_local(cs)
        validation.append({"path": str(cs), **v})
        if not v["ok"]:
            invalid_count += 1
        null_header_count += int(v.get("null_header_path", 0))
        duplicate_chunk_ids += int(v.get("duplicate_chunk_ids", 0))

    warnings = []
    errors = []

    if len(pdfs) > 0 and len(xmls) == 0:
        warnings.append("PDFs exist but no XMLs generated yet")
    if len(xmls) > 0 and len(chunk_sets) == 0:
        warnings.append("XMLs exist but no chunk_set artifacts generated yet")
    if invalid_count > 0:
        errors.append(f"{invalid_count} invalid chunk_set artifact(s)")
    if null_header_count > 0:
        warnings.append(f"{null_header_count} chunks have null/empty header_path")
    if duplicate_chunk_ids > 0:
        warnings.append(f"{duplicate_chunk_ids} duplicate chunk_id occurrences detected")

    grobid_reachable = None
    if check_grobid:
        grobid_reachable = _probe_grobid()
        if not grobid_reachable:
            errors.append("GROBID not reachable")

    port_available = None
    if port is not None:
        port_available = _is_port_available(port)
        if not port_available:
            warnings.append(f"port {port} is occupied")

    newest_xml = max((p.stat().st_mtime for p in xmls), default=None)
    newest_chunk = max((p.stat().st_mtime for p in chunk_sets), default=None)
    if newest_xml and newest_chunk and newest_xml > newest_chunk + 60:
        warnings.append("chunk_set artifacts may be stale relative to XML inputs")

    ready_to_parse = len(pdfs) > 0
    ready_to_serve = len(chunk_sets) > 0 and invalid_count == 0

    report = {
        "corpus_name": cp.name,
        "resolved_paths": {
            "root": str(cp.root), "pdfs": str(cp.pdfs), "xmls": str(cp.xmls), "chunks": str(cp.chunks), "chunk_sets": str(cp.chunk_sets), "review": str(cp.review),
        },
        "n_pdfs": len(pdfs),
        "n_xmls": len(xmls),
        "n_chunk_sets": len(chunk_sets),
        "n_review_csvs": len(review_csvs),
        "n_failures": len(failures),
        "latest_failure_files": [str(p) for p in sorted(failures, key=lambda x: x.stat().st_mtime, reverse=True)[:5]],
        "chunk_set_validation": {"n_pass": len(chunk_sets)-invalid_count, "n_fail": invalid_count},
        "null_header_path_count": null_header_count,
        "duplicate_chunk_id_count": duplicate_chunk_ids,
        "grobid_reachable": grobid_reachable,
        "port_available": port_available,
        "ready_to_parse": ready_to_parse,
        "ready_to_serve": ready_to_serve,
        "warnings": warnings,
        "errors": errors,
        "generated_at": time.time(),
    }

    if strict and (errors or invalid_count > 0):
        report["strict_failed"] = True
    else:
        report["strict_failed"] = False

    return report


def _parse_args_and_run() -> None:
    p = argparse.ArgumentParser(prog="pipeline.adapter.manager", description="paper-kb PDF/TEI/chunk_set manager")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grobid", help="POST PDFs to GROBID and write TEI files")
    g.add_argument("pdf_dir", nargs="?")
    g.add_argument("out_tei_dir", nargs="?")
    g.add_argument("--corpus", default=None)
    g.add_argument("--recursive", action="store_true")
    g.add_argument("--timeout", type=int, default=180)
    g.add_argument("--max-retries", type=int, default=3)
    g.add_argument("--max-files", type=int, default=None)
    g.add_argument("--force", action="store_true")
    g.add_argument("--no-consolidate-header", action="store_true", help="disable external header consolidation for reproducible/offline parsing")

    pr = sub.add_parser("parse", help="Parse TEIs to legacy chunks and canonical chunk_set artifacts")
    pr.add_argument("tei_dir", nargs="?")
    pr.add_argument("chunks_dir", nargs="?")
    pr.add_argument("--corpus", default=None)
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
    f.add_argument("--corpus", default=None)
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
    f.add_argument("--no-consolidate-header", action="store_true", help="disable external header consolidation for reproducible/offline parsing")

    d = sub.add_parser("doctor", help="Check corpus readiness for parse/serve/browse")
    d.add_argument("--corpus", required=True)
    d.add_argument("--strict", action="store_true")
    d.add_argument("--json", action="store_true")
    d.add_argument("--check-grobid", action="store_true")
    d.add_argument("--port", type=int, default=None)

    args = p.parse_args()

    if args.cmd == "doctor":
        res = run_doctor(corpus=args.corpus, strict=args.strict, as_json=args.json, check_grobid=args.check_grobid, port=args.port)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(f"[doctor] corpus={res['corpus_name']} parse={res['ready_to_parse']} serve={res['ready_to_serve']}")
            print(json.dumps(res, ensure_ascii=False, indent=2))
        if args.strict and res.get("strict_failed"):
            raise SystemExit(2)
        return
    elif args.cmd == "grobid":
        runtime_paths = _resolve_runtime_paths(
            corpus=args.corpus,
            pdf_dir=Path(args.pdf_dir).expanduser().resolve() if args.pdf_dir else None,
            tei_dir=Path(args.out_tei_dir).expanduser().resolve() if args.out_tei_dir else None,
            chunks_dir=None,
            chunk_set_dir=None,
        )
        if runtime_paths["pdf_dir"] is None or runtime_paths["tei_dir"] is None:
            raise SystemExit("grobid requires pdf_dir and out_tei_dir, or --corpus")
        from pipeline.adapter.grobid_ingest import generate_teis_from_pdfs
        res = generate_teis_from_pdfs(
            runtime_paths["pdf_dir"],
            runtime_paths["tei_dir"],
            recursive=args.recursive,
            timeout=args.timeout,
            max_retries=args.max_retries,
            max_files=args.max_files,
            force=args.force,
            consolidate_header=not args.no_consolidate_header,
        )
    elif args.cmd == "parse":
        runtime_paths = _resolve_runtime_paths(
            corpus=args.corpus,
            pdf_dir=None,
            tei_dir=Path(args.tei_dir).expanduser().resolve() if args.tei_dir else None,
            chunks_dir=Path(args.chunks_dir).expanduser().resolve() if args.chunks_dir else None,
            chunk_set_dir=Path(args.chunk_set_dir).expanduser().resolve() if args.chunk_set_dir else None,
        )
        if runtime_paths["tei_dir"] is None or runtime_paths["chunks_dir"] is None:
            raise SystemExit("parse requires tei_dir and chunks_dir, or --corpus")
        from pipeline.producer.tei_runner import parse_teis_to_chunks
        res = parse_teis_to_chunks(
            runtime_paths["tei_dir"],
            runtime_paths["chunks_dir"],
            min_len=args.min_len,
            dry_run=args.dry_run,
            force=args.force,
            emit_chunk_set_artifact=not args.no_chunk_set,
            chunk_set_dir=runtime_paths["chunk_set_dir"],
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
            grobid_opts={"recursive": True, "consolidate_header": not args.no_consolidate_header} if args.do_grobid else {},
            parse_opts={
                "min_len": args.min_len,
                "dry_run": args.dry_run,
                "force": args.force,
                "chunk_set_dir": Path(args.chunk_set_dir).expanduser().resolve() if args.chunk_set_dir else None,
            },
            ingest_opts={"batch_size": 256, "force": args.force, "dry_run": args.dry_run},
            corpus=args.corpus,
        )

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _parse_args_and_run()
