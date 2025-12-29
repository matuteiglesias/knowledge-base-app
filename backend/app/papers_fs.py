import json
import os
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

from shared.config import PAPERS_DIR
from backend.app.schemas import PaperMeta

PAPERS_DIR.mkdir(parents=True, exist_ok=True)
PAPERS_INDEX = PAPERS_DIR / "papers_index.json"


def _atomic_write_text(path: Path, text: str):
    tmp = Path(str(path) + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(text, encoding="utf8")
    os.replace(str(tmp), str(path))


def save_paper_metadata_to_fs(paper_id: str, metadata: Dict[str, Any], store_dir: Path = PAPERS_DIR):
    """
    Validate metadata with PaperMeta and write <paper_id>.json and update papers_index.json atomically.
    """
    store_dir.mkdir(parents=True, exist_ok=True)
    # Validate / coerce
    pm = PaperMeta(**{**metadata, "paper_id": paper_id})
    # ensure created_at is present (coerce to isoformat)
    if pm.created_at is None:
        pm.created_at = datetime.utcnow()
    # write individual file atomically
    pfile = store_dir / f"{paper_id}.json"
    _atomic_write_text(pfile, pm.json(ensure_ascii=False, indent=2))

    # update index (read - modify - write) -> index is a dict keyed by paper_id
    idx: Dict[str, Any] = {}
    if PAPERS_INDEX.exists():
        try:
            raw = PAPERS_INDEX.read_text(encoding="utf8")
            idx = json.loads(raw) if raw else {}
        except Exception:
            idx = {}

    idx_entry = {
        "paper_id": paper_id,
        "title": pm.title,
        "n_chunks": pm.n_chunks,
        "created_at": pm.created_at.isoformat() if hasattr(pm.created_at, "isoformat") else pm.created_at,
        # include small selection of fields useful for listing
        "pipeline_version": pm.pipeline_version,
        "embed_model": pm.embed_model,
    }
    idx[paper_id] = idx_entry
    _atomic_write_text(PAPERS_INDEX, json.dumps(idx, ensure_ascii=False, indent=2))


def load_paper_metadata_from_fs(paper_id: str) -> Dict:
    """Load metadata JSON. Returns {} if not found."""
    path = PAPERS_DIR / f"{paper_id}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except Exception:
        return {}


def list_papers_from_fs() -> List[Dict]:
    """Fast listing: prefer papers_index.json, fallback to scanning files."""
    if PAPERS_INDEX.exists():
        try:
            raw = PAPERS_INDEX.read_text(encoding="utf8")
            idx = json.loads(raw) if raw else {}
            out = []
            for pid, entry in idx.items():
                out.append({
                    "paper_id": pid,
                    "title": entry.get("title", pid),
                    "metadata": entry,
                })
            return out
        except Exception:
            # fallback to scan
            pass

    papers = []
    for f in PAPERS_DIR.glob("*.json"):
        if f.name == PAPERS_INDEX.name:
            continue
        paper_id = f.stem
        try:
            md = json.loads(f.read_text(encoding="utf8"))
        except Exception:
            md = {}
        papers.append({
            "paper_id": paper_id,
            "title": md.get("title", paper_id.replace("_", " ")),
            "metadata": md,
        })
    return papers
