from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SUMMARY_VERSION = 1
_CONFIDENCE_ALLOWED = {"low", "medium", "high"}
_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def safe_paper_id(paper_id: str) -> str:
    cleaned = _SAFE_ID_RE.sub("_", str(paper_id or "").strip())
    return cleaned.strip("._") or "unknown_paper"


def summary_path(summaries_dir: Path, paper_id: str) -> Path:
    return summaries_dir / f"{safe_paper_id(paper_id)}.summary.json"


def build_summary_artifact(*, paper_id: str, title: str, provider: str, model: str | None, corpus: str, chunk_set_dir: str, n_chunks_total: int, n_chunks_selected: int, selected_chunk_ids: list[str], payload: dict[str, Any]) -> dict[str, Any]:
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    confidence = payload.get("confidence") if payload.get("confidence") in _CONFIDENCE_ALLOWED else "medium"
    tags = payload.get("suggested_tags") if isinstance(payload.get("suggested_tags"), dict) else {}
    return {
        "paper_id": paper_id,
        "title": title or "",
        "summary_version": SUMMARY_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": provider,
        "model": model or "",
        "source": {
            "corpus": corpus,
            "chunk_set_dir": chunk_set_dir,
            "n_chunks_total": int(n_chunks_total),
            "n_chunks_selected": int(n_chunks_selected),
            "selected_chunk_ids": list(selected_chunk_ids),
        },
        "status": "ready",
        "one_line": str(payload.get("one_line") or payload.get("summary") or ""),
        "research_question": str(payload.get("research_question") or ""),
        "data": str(payload.get("data") or ""),
        "method": str(payload.get("method") or ""),
        "main_contribution": str(payload.get("main_contribution") or ""),
        "limitations": str(payload.get("limitations") or ""),
        "relevance_to_thesis": str(payload.get("relevance_to_thesis") or ""),
        "suggested_tags": {
            "method_tags": list(tags.get("method_tags") or []),
            "data_tags": list(tags.get("data_tags") or []),
        },
        "confidence": confidence,
        "warnings": warnings,
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
