"""Chunk Bus-compatible artifact writer for paper-kb.

This module is intentionally small and dependency-light. It turns the existing
paper-kb CanonicalChunk-like records into an inspectable chunk_set artifact,
without replacing the legacy backend store/chunks JSONL outputs.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


def _repo_root_from_cwd() -> Path:
    # Usually called from the paper-kb repo. If not, allow env override.
    return Path(os.environ.get("PAPER_KB_ROOT", ".")).expanduser().resolve()


def default_chunk_sets_dir() -> Path:
    return Path(
        os.environ.get(
            "PAPER_KB_CHUNK_SETS_DIR",
            str(_repo_root_from_cwd() / "artifacts" / "chunk_sets"),
        )
    ).expanduser().resolve()


def _to_mapping(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        return dict(obj.model_dump())
    if hasattr(obj, "dict"):
        return dict(obj.dict())
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    raise TypeError(f"Cannot convert object to mapping: {type(obj)!r}")


def _first_present(mapping: Dict[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return default


def _chunk_to_record(chunk: Any, *, fallback_source_file: Optional[str] = None) -> Dict[str, Any]:
    m = _to_mapping(chunk)
    meta = m.get("metadata") or m.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {"raw_meta": meta}

    chunk_id = _first_present(m, ["chunk_id", "id", "chunkId", "xml_id", "xml:id"])
    if not chunk_id:
        raise ValueError("chunk lacks chunk_id/id/xml_id")

    text = _first_present(m, ["text", "content", "document"], "") or ""
    paper_id = _first_present(m, ["paper_id", "paper", "source_id"], meta.get("paper_id"))
    source_file = _first_present(m, ["source_file", "source"], meta.get("source_file") or fallback_source_file)
    header_path = _first_present(m, ["header_path", "section_title"], meta.get("header_path") or meta.get("section_title"))

    clean_meta = dict(meta)
    for redundant in ("text", "content", "document"):
        clean_meta.pop(redundant, None)

    return {
        "chunk_id": str(chunk_id),
        "source_file": str(source_file) if source_file else None,
        "paper_id": str(paper_id) if paper_id else None,
        "header_path": header_path,
        "text": str(text),
        "metadata": clean_meta,
    }


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def write_chunk_set_artifact(
    chunks: Iterable[Any],
    *,
    source_items: Sequence[str],
    run_id: str,
    out_dir: Optional[Path] = None,
    producer: str = "paper-kb",
    entrypoint: str = "paper_tei_parse",
    schema_version: int = 1,
    fallback_source_file: Optional[str] = None,
) -> Path:
    """Write a Chunk Bus-compatible chunk_set artifact and return its path."""
    out_dir = Path(out_dir) if out_dir is not None else default_chunk_sets_dir()
    out_path = out_dir / f"{run_id}.chunk_set.json"

    records: List[Dict[str, Any]] = [
        _chunk_to_record(c, fallback_source_file=fallback_source_file) for c in chunks
    ]

    payload: Dict[str, Any] = {
        "artifact_family": "chunk_bus",
        "artifact_kind": "chunk_set",
        "schema_version": int(schema_version),
        "run_id": str(run_id),
        "producer": producer,
        "entrypoint": entrypoint,
        "source_items": [str(x) for x in source_items],
        "chunks": records,
        "chunk_count": len(records),
    }
    write_json_atomic(out_path, payload)
    return out_path
