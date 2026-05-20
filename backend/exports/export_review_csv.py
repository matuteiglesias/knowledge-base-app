from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.storage_adapter import StorageAdapter, create_adapter_from_env

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


def cli() -> None:
    parser = argparse.ArgumentParser(description="Export paper-kb papers to abstract-scroller-friendly CSV.")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()
    out = export_review_csv(Path(args.out))
    print(str(out))


if __name__ == "__main__":
    cli()

