from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from pipeline.corpus import resolve_corpus_paths


_ALLOWED_LEVELS = {"metadata", "consumer"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _records(paths: list[Path], root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda p: p.relative_to(root).as_posix().casefold()):
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return rows


def _glob_files(path: Path, pattern: str) -> list[Path]:
    if not path.exists():
        return []
    return [p for p in path.glob(pattern) if p.is_file()]


def _copy_files(paths: list[Path], source_root: Path, target_root: Path) -> list[Path]:
    copied: list[Path] = []
    for source in paths:
        rel = source.relative_to(source_root)
        target = target_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if _sha256(target) != _sha256(source):
            raise RuntimeError(f"fixture copy verification failed: {rel}")
        copied.append(target)
    return copied


def promote_corpus_fixture(
    *,
    corpus: str,
    repo_root: Path | None = None,
    level: str = "metadata",
    allow_text_derivatives: bool = False,
    replace: bool = False,
) -> dict[str, Any]:
    if level not in _ALLOWED_LEVELS:
        raise ValueError(f"fixture level must be one of {sorted(_ALLOWED_LEVELS)}")
    if level == "consumer" and not allow_text_derivatives:
        raise ValueError(
            "consumer fixtures include chunk_set text; rerun with explicit --allow-text-derivatives only when redistribution is permitted"
        )

    cp = resolve_corpus_paths(corpus, repo_root=repo_root)
    repo = cp.root.parent.parent
    target = repo / "fixture" / "corpora" / corpus

    pdfs = _glob_files(cp.pdfs, "*.pdf") + _glob_files(cp.pdfs, "*.PDF")
    pdfs = list({path.resolve(): path for path in pdfs}.values())
    if not pdfs:
        raise RuntimeError(f"cannot promote corpus fixture without source PDFs: {cp.pdfs}")

    catalog_files = _glob_files(cp.catalog, "*.jsonl")
    review_files = _glob_files(cp.review, "*.jsonl")
    if not catalog_files:
        raise RuntimeError(f"missing catalog JSONL output: {cp.catalog}")
    if not review_files:
        raise RuntimeError(f"missing review JSONL output: {cp.review}")

    selected = catalog_files + review_files
    chunk_sets: list[Path] = []
    if level == "consumer":
        chunk_sets = _glob_files(cp.chunk_sets, "*.chunk_set.json")
        if not chunk_sets:
            raise RuntimeError(f"consumer fixture requested but no chunk_set artifacts exist: {cp.chunk_sets}")
        selected += chunk_sets

    if target.exists():
        if not replace:
            raise RuntimeError(f"fixture already exists: {target}; rerun with --replace after review")
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    copied = _copy_files(selected, cp.root, target)

    source_manifest = cp.root / "source-manifest.json"
    if source_manifest.exists():
        shutil.copy2(source_manifest, target / "source-manifest.json")
        copied.append(target / "source-manifest.json")

    manifest = {
        "schema_id": "paper-kb.corpus-fixture-manifest",
        "schema_version": 1,
        "corpus_id": corpus,
        "fixture_level": level,
        "absolute_paths_recorded": False,
        "source_pdf_count": len(pdfs),
        "source_pdfs": _records(pdfs, cp.root),
        "catalog_record_files": len(catalog_files),
        "review_record_files": len(review_files),
        "chunk_set_count": len(chunk_sets),
        "copied_artifacts": _records(copied, target),
        "omitted": ["pdfs", "xmls", "chunks", "runtime state"],
        "rights_note": (
            "metadata fixture: source PDFs are represented only by filename/size/SHA-256"
            if level == "metadata"
            else "consumer fixture: canonical chunk_set text derivatives were included by explicit operator acknowledgement"
        ),
    }
    manifest_path = target / "fixture-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "status": "promoted",
        "corpus_id": corpus,
        "fixture_level": level,
        "target": str(target),
        "source_pdf_count": len(pdfs),
        "chunk_set_count": len(chunk_sets),
        "copied_file_count": len(copied),
        "manifest": str(manifest_path),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote a local Paper KB corpus into a bounded repository fixture")
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--level", choices=sorted(_ALLOWED_LEVELS), default="metadata")
    parser.add_argument("--allow-text-derivatives", action="store_true")
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = promote_corpus_fixture(
        corpus=args.corpus,
        level=args.level,
        allow_text_derivatives=args.allow_text_derivatives,
        replace=args.replace,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
