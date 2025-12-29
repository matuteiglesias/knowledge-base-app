# # pipeline/ingestion/manager.py
# from __future__ import annotations
# from pathlib import Path
# import json
# import logging
# from typing import List, Optional, Dict, Any, Tuple

# # from pipeline.ingestion.grobid_ingest import post_pdf_to_grobid, _collect_pdf_paths, _sanitize_filename
# # from pipeline.parsers.tei_parser import parse_tei_text
# # from pipeline.parsers.canonicalize import chunks_to_models, make_paper_meta
# # from backend.app import chunks_fs as chunks_fs
# # from backend.app.chunks_fs import write_chunks_jsonl, chunk_file_for
# # from pipeline.embedding.engine import embed_records, _build_default_adapter


# from shared.config import CHUNKS_DIR, TEI_DIR, PDF_DIR, EMBED_CACHE_DB, EMBED_DIM, CHROMA_DIR

# logger = logging.getLogger("ingest.manager")
# logger.addHandler(logging.StreamHandler())
# logger.setLevel(logging.INFO)




# def _done_marker_path(chunks_dir: Path, paper_id: str) -> Path:
#     return chunks_dir / f"{paper_id}.done"



# # ---------- 4) Full orchestration ----------
# def full_run(pdf_dir: Optional[Path] = None,
#              tei_dir: Optional[Path] = None,
#              chunks_dir: Optional[Path] = None,
#              chroma_dir: Optional[Path] = None,
#              do_grobid: bool = True,
#              do_parse: bool = True,
#              do_ingest: bool = True,
#              grobid_opts: Optional[Dict[str, Any]] = None,
#              parse_opts: Optional[Dict[str, Any]] = None,
#              ingest_opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
#     """
#     Orchestrate grobid -> parse -> ingest. Each step's summary is returned.
#     """
#     grobid_opts = grobid_opts or {}
#     parse_opts = parse_opts or {}
#     ingest_opts = ingest_opts or {}

#     pdf_dir = Path(pdf_dir or PDF_DIR)
#     tei_dir = Path(tei_dir or TEI_DIR)
#     chunks_dir = Path(chunks_dir or CHUNKS_DIR)
#     chroma_dir = Path(chroma_dir or CHROMA_DIR)

#     overall = {"grobid": None, "parse": None, "ingest": None}

#     if do_grobid:
#         overall["grobid"] = generate_teis_from_pdfs(pdf_dir, tei_dir, **grobid_opts)

#     if do_parse:
#         overall["parse"] = parse_teis_to_chunks(tei_dir, chunks_dir, **parse_opts)

#     if do_ingest:
#         overall["ingest"] = ingest_chunks_to_chroma(chunks_dir, chroma_dir, **ingest_opts)

#     return overall


# # ---------- CLI ----------
# def _parse_args_and_run():
#     import argparse
#     p = argparse.ArgumentParser(prog="ingest.manager", description="Manager for PDF -> TEI -> chunks -> Chroma ingestion")
#     sub = p.add_subparsers(dest="cmd", required=True)

#     # grobid
#     g = sub.add_parser("grobid", help="POST PDFs to GROBID and write TEI files")
#     g.add_argument("pdf_dir")
#     g.add_argument("out_tei_dir")
#     g.add_argument("--recursive", action="store_true")
#     g.add_argument("--timeout", type=int, default=180)
#     g.add_argument("--max-retries", type=int, default=3)
#     g.add_argument("--max-files", type=int, default=None)
#     g.add_argument("--force", action="store_true")

#     # parse
#     pr = sub.add_parser("parse", help="Parse TEIs to chunk jsonl")
#     pr.add_argument("tei_dir")
#     pr.add_argument("chunks_dir")
#     pr.add_argument("--min-len", type=int, default=50)
#     pr.add_argument("--dry-run", action="store_true")
#     pr.add_argument("--force", action="store_true")

#     # ingest
#     ing = sub.add_parser("ingest", help="Embed + upsert chunks into chroma")
#     ing.add_argument("chunks_dir")
#     ing.add_argument("chroma_dir")
#     ing.add_argument("--collection", default="chunks")
#     ing.add_argument("--batch-size", type=int, default=256)
#     ing.add_argument("--force", action="store_true")
#     ing.add_argument("--dry-run", action="store_true")

#     # full-run
#     f = sub.add_parser("full-run", help="grobid -> parse -> ingest")
#     f.add_argument("--pdf-dir", default=str(PDF_DIR))
#     f.add_argument("--tei-dir", default=str(TEI_DIR))
#     f.add_argument("--chunks-dir", default=str(CHUNKS_DIR))
#     f.add_argument("--chroma-dir", default=str(CHROMA_DIR))
#     f.add_argument("--no-grobid", dest="do_grobid", action="store_false")
#     f.add_argument("--no-parse", dest="do_parse", action="store_false")
#     f.add_argument("--no-ingest", dest="do_ingest", action="store_false")
#     f.add_argument("--min-len", type=int, default=50)
#     f.add_argument("--force", action="store_true")
#     f.add_argument("--dry-run", action="store_true")

#     args = p.parse_args()

#     if args.cmd == "grobid":
#         res = generate_teis_from_pdfs(Path(args.pdf_dir), Path(args.out_tei_dir), recursive=args.recursive,
#                                      timeout=args.timeout, max_retries=args.max_retries, max_files=args.max_files, force=args.force)
#     elif args.cmd == "parse":
#         res = parse_teis_to_chunks(Path(args.tei_dir), Path(args.chunks_dir), min_len=args.min_len, dry_run=args.dry_run, force=args.force)
#     elif args.cmd == "ingest":
#         res = ingest_chunks_to_chroma(Path(args.chunks_dir), Path(args.chroma_dir), collection=args.collection,
#                                      batch_size=args.batch_size, force=args.force, dry_run=args.dry_run)
#     else:  # full-run
#         grobid_opts = {"recursive": True} if args.do_grobid else {}
#         parse_opts = {"min_len": args.min_len, "dry_run": args.dry_run, "force": args.force}
#         ingest_opts = {"batch_size": 256, "force": args.force, "dry_run": args.dry_run}
#         res = full_run(pdf_dir=Path(args.pdf_dir), tei_dir=Path(args.tei_dir), chunks_dir=Path(args.chunks_dir), chroma_dir=Path(args.chroma_dir),
#                        do_grobid=args.do_grobid, do_parse=args.do_parse, do_ingest=args.do_ingest,
#                        grobid_opts=grobid_opts, parse_opts=parse_opts, ingest_opts=ingest_opts)

#     # print machine readable summary
#     print(json.dumps(res, ensure_ascii=False, indent=2))


# if __name__ == "__main__":
#     _parse_args_and_run()
