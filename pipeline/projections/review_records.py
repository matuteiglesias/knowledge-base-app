"""Canonical paper review projection from governed chunk_set artifacts.

This module is intentionally independent of the API/read-service layer. The
review projection is a sibling consumer of the canonical paper corpus, not an
export of backend state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Optional

from pipeline.contracts.review_record import validate_review_record_dict
from pipeline.corpus import resolve_corpus_paths


class ReviewProjectionError(ValueError):
    """Raised when canonical corpus artifacts cannot form an unambiguous review projection."""


def _nullable_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _nullable_year(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ReviewProjectionError("year must not be boolean")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ReviewProjectionError(f"year is not an integer: {value!r}") from exc


def _string_list(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ReviewProjectionError(f"{field} must be an array when present")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ReviewProjectionError(f"{field} items must be strings")
        clean = item.strip()
        if clean:
            out.append(clean)
    return out


def review_record_from_chunk_set(payload: dict[str, Any], *, source_name: str = "<memory>") -> dict[str, Any]:
    if payload.get("artifact_family") != "chunk_bus" or payload.get("artifact_kind") != "chunk_set":
        raise ReviewProjectionError(f"{source_name}: expected chunk_bus/chunk_set artifact")

    paper_meta = payload.get("paper_meta")
    if not isinstance(paper_meta, dict):
        raise ReviewProjectionError(f"{source_name}: missing paper_meta")

    paper_uid = _nullable_str(paper_meta.get("paper_uid"))
    if paper_uid is None:
        raise ReviewProjectionError(
            f"{source_name}: paper_meta.paper_uid is required for canonical review projection; "
            "use the legacy CSV export for artifacts without canonical identity"
        )

    title = _nullable_str(paper_meta.get("title") or paper_meta.get("display_title"))
    if title is None:
        raise ReviewProjectionError(f"{source_name}: paper_meta.title is required")

    record = {
        "schema_id": "paper.review-record",
        "schema_version": 1,
        "paper_uid": paper_uid,
        "paper_id": _nullable_str(paper_meta.get("paper_id")),
        "title": title,
        "abstract": _nullable_str(paper_meta.get("abstract")),
        "date": _nullable_str(paper_meta.get("date")),
        "year": _nullable_year(paper_meta.get("year")),
        "venue": _nullable_str(paper_meta.get("venue")),
        "doi": _nullable_str(paper_meta.get("doi")),
        "arxiv_id": _nullable_str(paper_meta.get("arxiv_id")),
        "repec_id": _nullable_str(paper_meta.get("repec_id")),
        "tags": _string_list(paper_meta.get("tags"), field="tags"),
        "badges": _string_list(paper_meta.get("badges"), field="badges"),
        "source_url": _nullable_str(paper_meta.get("source_url")),
    }
    validate_review_record_dict(record)
    return record


def build_review_records(chunk_set_paths: Iterable[Path]) -> list[dict[str, Any]]:
    by_uid: dict[str, dict[str, Any]] = {}
    source_by_uid: dict[str, str] = {}

    for path in sorted((Path(p) for p in chunk_set_paths), key=lambda p: p.name):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ReviewProjectionError(f"{path.name}: invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ReviewProjectionError(f"{path.name}: artifact root must be an object")

        record = review_record_from_chunk_set(payload, source_name=path.name)
        uid = record["paper_uid"]
        if uid in by_uid:
            raise ReviewProjectionError(
                f"duplicate paper_uid {uid!r} in {source_by_uid[uid]} and {path.name}; "
                "canonical review projection requires an unambiguous corpus artifact set"
            )
        by_uid[uid] = record
        source_by_uid[uid] = path.name

    return [by_uid[uid] for uid in sorted(by_uid)]


def write_review_records_jsonl(records: Iterable[dict[str, Any]], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    materialized = list(records)
    for record in materialized:
        validate_review_record_dict(record)

    fd, tmp_name = tempfile.mkstemp(prefix=f".{out_path.name}.", suffix=".tmp", dir=str(out_path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for record in materialized:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
                handle.write("\n")
        os.replace(tmp_name, out_path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return out_path


def export_review_records(*, chunk_set_dir: Path, out_path: Path) -> dict[str, Any]:
    chunk_set_dir = Path(chunk_set_dir)
    if not chunk_set_dir.exists():
        raise ReviewProjectionError(f"chunk_set_dir does not exist: {chunk_set_dir}")
    paths = sorted(chunk_set_dir.glob("*.chunk_set.json"), key=lambda p: p.name)
    records = build_review_records(paths)
    written = write_review_records_jsonl(records, out_path)
    raw = written.read_bytes()
    return {
        "schema_id": "paper.review-record",
        "schema_version": 1,
        "records": len(records),
        "input_artifacts": len(paths),
        "output": str(written),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _resolve_targets(*, corpus: Optional[str], chunk_set_dir: Optional[str], out: Optional[str]) -> tuple[Path, Path]:
    if corpus:
        paths = resolve_corpus_paths(corpus)
        return (
            Path(chunk_set_dir).expanduser().resolve() if chunk_set_dir else paths.chunk_sets,
            Path(out).expanduser().resolve() if out else paths.review / "paper.review-record.v1.jsonl",
        )
    if not chunk_set_dir or not out:
        raise ReviewProjectionError("provide --corpus or both --chunk-set-dir and --out")
    return Path(chunk_set_dir).expanduser().resolve(), Path(out).expanduser().resolve()


def cli() -> int:
    parser = argparse.ArgumentParser(description="Export canonical paper.review-record@1 JSONL from chunk_set artifacts.")
    parser.add_argument("--corpus", required=False)
    parser.add_argument("--chunk-set-dir", required=False)
    parser.add_argument("--out", required=False)
    args = parser.parse_args()

    chunk_set_dir, out_path = _resolve_targets(
        corpus=args.corpus,
        chunk_set_dir=args.chunk_set_dir,
        out=args.out,
    )
    summary = export_review_records(chunk_set_dir=chunk_set_dir, out_path=out_path)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
