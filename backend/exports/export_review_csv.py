from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.storage_adapter import ChunkSetStorageAdapter, StorageAdapter, create_adapter_from_env
from pipeline.corpus import resolve_corpus_paths

CSV_FIELDS = [
    "doc_id",
    "title",
    "abstract",
    "date",
    "year",
    "venue",
    "tags",
    "badges",
    "source_url",
    "paper_id",
]


def _paper_abstract(storage: StorageAdapter, paper: Dict[str, Any]) -> str:
    for key in ("abstract",):
        value = paper.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    preview = paper.get("preview")
    if isinstance(preview, str) and preview.strip():
        return preview.strip()

    pid = str(paper.get("paper_id") or "").strip()
    if not pid:
        return ""
    try:
        listed = storage.list_chunks(paper_id=pid, offset=0, limit=50, q=None)  # type: ignore[attr-defined]
        for chunk in listed.get("chunks", []):
            txt = chunk.get("text")
            if isinstance(txt, str) and txt.strip():
                return txt.strip()
    except Exception:
        return ""
    return ""


def _first_str(d: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def export_review_csv(out_path: Path, storage: Optional[StorageAdapter] = None) -> Path:
    st = storage or create_adapter_from_env()
    if hasattr(st, "load_caches"):
        st.load_caches()

    papers: List[Dict[str, Any]] = []
    if hasattr(st, "list_papers"):
        papers = st.list_papers() or []  # type: ignore[attr-defined]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for p in papers:
            pid = _first_str(p, "paper_id")
            title = _first_str(p, "title") or pid
            row = {
                "doc_id": pid,
                "title": title,
                "abstract": _paper_abstract(st, p),
                "date": _first_str(p, "date", "published_at"),
                "year": str(p.get("year") or ""),
                "venue": _first_str(p, "venue", "journal"),
                "tags": "",
                "badges": "",
                "source_url": _first_str(p, "source_url", "url"),
                "paper_id": pid,
            }
            writer.writerow(row)
    return out_path


def _resolve_export_targets(
    *,
    out_path: Optional[str],
    chunk_set_dir: Optional[str],
    corpus: Optional[str],
) -> tuple[Optional[Path], Optional[Path]]:
    if corpus:
        corpus_paths = resolve_corpus_paths(corpus).ensure_dirs()
        resolved_out = Path(out_path).expanduser().resolve() if out_path else (corpus_paths.review / "papers.csv")
        resolved_chunk_sets = (
            Path(chunk_set_dir).expanduser().resolve() if chunk_set_dir else corpus_paths.chunk_sets
        )
        return resolved_out, resolved_chunk_sets

    resolved_out = Path(out_path).expanduser().resolve() if out_path else None
    resolved_chunk_sets = Path(chunk_set_dir).expanduser().resolve() if chunk_set_dir else None
    return resolved_out, resolved_chunk_sets


def cli() -> None:
    parser = argparse.ArgumentParser(description="Export paper-kb papers to abstract-scroller-friendly CSV.")
    parser.add_argument("--out", required=False, help="Output CSV path")
    parser.add_argument("--chunk-set-dir", required=False, help="Chunk set directory to export from")
    parser.add_argument("--corpus", required=False, help="Named corpus under corpora/<name>")
    args = parser.parse_args()

    out_path, chunk_set_path = _resolve_export_targets(
        out_path=args.out,
        chunk_set_dir=args.chunk_set_dir,
        corpus=args.corpus,
    )

    if out_path is None:
        raise SystemExit("--out is required unless --corpus is provided.")

    storage: Optional[StorageAdapter] = None
    if chunk_set_path is not None:
        storage = ChunkSetStorageAdapter(chunk_sets_dir=str(chunk_set_path))

    out = export_review_csv(out_path, storage=storage)
    print(str(out))


if __name__ == "__main__":
    cli()
