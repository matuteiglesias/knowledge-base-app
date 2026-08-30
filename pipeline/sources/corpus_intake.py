from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.corpus import resolve_corpus_paths


_CORPUS_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _canonical_sha256(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_corpus_name(corpus: str) -> str:
    name = (corpus or "").strip()
    if not _CORPUS_NAME_RE.fullmatch(name):
        raise ValueError(
            "corpus name must start with an alphanumeric character and contain only letters, numbers, '.', '_' or '-'"
        )
    return name


def discover_pdfs(source_dir: Path, *, recursive: bool = True) -> list[Path]:
    root = Path(source_dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"source directory does not exist or is not a directory: {root}")

    iterator = root.rglob("*") if recursive else root.glob("*")
    pdfs = sorted(
        (path for path in iterator if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )
    if not pdfs:
        raise ValueError(f"no PDF files found under source directory: {root}")

    by_registered_name: dict[str, list[str]] = {}
    for path in pdfs:
        registered_name = path.name.casefold()
        by_registered_name.setdefault(registered_name, []).append(path.relative_to(root).as_posix())
    collisions = {name: paths for name, paths in by_registered_name.items() if len(paths) > 1}
    if collisions:
        detail = "; ".join(f"{name}: {paths}" for name, paths in sorted(collisions.items()))
        raise ValueError(
            "duplicate PDF basenames cannot be registered safely because the canonical corpus PDF directory is flat: " + detail
        )
    return pdfs


def _file_records(source_dir: Path, pdfs: list[Path]) -> list[dict[str, Any]]:
    root = source_dir.expanduser().resolve()
    records = []
    for path in pdfs:
        records.append(
            {
                "source_relative_path": path.relative_to(root).as_posix(),
                "registered_filename": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return records


def _registered_input_identity(records: list[dict[str, Any]]) -> str:
    """Hash the canonical registered corpus snapshot, not incidental local directory layout."""
    identity_records = [
        {
            "registered_filename": record["registered_filename"],
            "size_bytes": record["size_bytes"],
            "sha256": record["sha256"],
        }
        for record in records
    ]
    identity_records.sort(key=lambda row: row["registered_filename"].casefold())
    return _canonical_sha256(identity_records)


def _load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"existing source manifest is unreadable: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"existing source manifest must contain a JSON object: {path}")
    return payload


def _verify_registered_pdfs(pdfs_dir: Path, records: list[dict[str, Any]]) -> bool:
    expected_names = {record["registered_filename"] for record in records}
    actual = (
        sorted(path for path in pdfs_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf")
        if pdfs_dir.exists()
        else []
    )
    if {path.name for path in actual} != expected_names:
        return False
    return all(_sha256_file(pdfs_dir / record["registered_filename"]) == record["sha256"] for record in records)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _safe_empty_build_skeleton(cp: Any) -> bool:
    """Recognize the harmless zero-record outputs produced by the old empty build path."""
    if not cp.root.exists():
        return True
    files = [path for path in cp.root.rglob("*") if path.is_file()]
    if not files:
        return True

    allowed_roots = (cp.review.resolve(), cp.catalog.resolve())
    for path in files:
        resolved = path.resolve()
        if path.stat().st_size != 0:
            return False
        if not any(_is_within(resolved, root) for root in allowed_roots):
            return False
    return True


def require_corpus_pdfs(*, corpus: str, repo_root: Path | None = None) -> dict[str, Any]:
    """Fail closed before a build when the named corpus contains no PDF inputs."""
    name = _validate_corpus_name(corpus)
    cp = resolve_corpus_paths(name, repo_root=repo_root)
    pdfs = (
        sorted(path for path in cp.pdfs.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf")
        if cp.pdfs.exists()
        else []
    )
    if not pdfs:
        raise RuntimeError(
            f"corpus '{name}' has 0 PDFs under {cp.pdfs}; register an input directory first with "
            f"make corpus-register CORPUS={name} SOURCE_DIR=/path/to/pdfs"
        )
    return {"corpus_id": name, "pdf_count": len(pdfs), "pdf_dir": str(cp.pdfs)}


def register_pdf_directory(
    *,
    corpus: str,
    source_dir: Path,
    repo_root: Path | None = None,
    recursive: bool = True,
    replace: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Register an existing local directory of PDFs as a named Paper KB corpus.

    Registration is intentionally bounded to source intake. It inventories and hashes
    the approved PDFs, copies the exact bytes into the canonical local corpus layout,
    and writes a portable manifest that never records the absolute source path.
    Parsing/GROBID remain separate operator actions.
    """

    name = _validate_corpus_name(corpus)
    source_root = Path(source_dir).expanduser().resolve()
    cp = resolve_corpus_paths(name, repo_root=repo_root)
    if _is_within(source_root, cp.root):
        raise ValueError("source directory must be outside the target corpus directory")

    pdfs = discover_pdfs(source_root, recursive=recursive)
    records = _file_records(source_root, pdfs)
    input_set_sha256 = _registered_input_identity(records)

    manifest_path = cp.root / "source-manifest.json"
    existing = _load_manifest(manifest_path)
    safe_empty_skeleton = False

    if existing and existing.get("input_set_sha256") == input_set_sha256:
        if _verify_registered_pdfs(cp.pdfs, records):
            return {
                "status": "unchanged",
                "corpus_id": name,
                "pdf_count": len(records),
                "total_bytes": sum(record["size_bytes"] for record in records),
                "input_set_sha256": input_set_sha256,
                "manifest_path": str(manifest_path),
                "registered_pdf_dir": str(cp.pdfs),
            }
        if not replace:
            raise RuntimeError(
                "source manifest matches but registered PDF bytes drifted or are incomplete; rerun with --replace to restore the snapshot"
            )

    if existing and existing.get("input_set_sha256") != input_set_sha256 and not replace:
        raise RuntimeError(
            "corpus is already registered with a different input set; use a new corpus name or rerun with --replace"
        )

    if not existing and cp.root.exists():
        safe_empty_skeleton = _safe_empty_build_skeleton(cp)
        if not safe_empty_skeleton and not replace:
            raise RuntimeError(
                f"corpus directory already contains local state without a matching source manifest: {cp.root}; use --replace only after review"
            )

    result = {
        "status": "would_register" if dry_run else "registered",
        "corpus_id": name,
        "pdf_count": len(records),
        "total_bytes": sum(record["size_bytes"] for record in records),
        "input_set_sha256": input_set_sha256,
        "manifest_path": str(manifest_path),
        "registered_pdf_dir": str(cp.pdfs),
        "replace": bool(replace),
        "recovered_empty_build_skeleton": bool(safe_empty_skeleton),
    }
    if dry_run:
        return result

    if safe_empty_skeleton:
        for generated_dir in (cp.xmls, cp.chunks, cp.chunk_sets, cp.review, cp.catalog):
            if generated_dir.exists():
                shutil.rmtree(generated_dir)

    cp.root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".pdf-intake-", dir=cp.root) as tmp:
        staged = Path(tmp) / "pdfs"
        staged.mkdir()
        for source_path, record in zip(pdfs, records):
            destination = staged / record["registered_filename"]
            shutil.copy2(source_path, destination)
            copied_sha = _sha256_file(destination)
            if copied_sha != record["sha256"]:
                raise RuntimeError(f"copy verification failed for {record['registered_filename']}")

        if cp.pdfs.exists():
            shutil.rmtree(cp.pdfs)
        staged.replace(cp.pdfs)

    if replace:
        for generated_dir in (cp.xmls, cp.chunks, cp.chunk_sets, cp.review, cp.catalog):
            if generated_dir.exists():
                shutil.rmtree(generated_dir)

    for generated_dir in (cp.xmls, cp.chunks, cp.chunk_sets, cp.review, cp.catalog):
        generated_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema_id": "paper-kb.corpus-source-manifest",
        "schema_version": 1,
        "corpus_id": name,
        "source_kind": "approved-local-pdf-directory",
        "source_path_recorded": False,
        "materialization": "copy",
        "recursive_discovery": bool(recursive),
        "pdf_count": len(records),
        "total_bytes": sum(record["size_bytes"] for record in records),
        "input_set_sha256": input_set_sha256,
        "files": records,
        "registered_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "authority_note": "This manifest governs the exact registered PDF byte set; it does not grant publication rights.",
    }
    tmp_manifest = manifest_path.with_suffix(".json.tmp")
    tmp_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_manifest.replace(manifest_path)

    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register approved local PDF directories as governed Paper KB corpus inputs")
    sub = parser.add_subparsers(dest="command", required=True)

    register = sub.add_parser("register", help="inventory, hash and copy an existing PDF directory into a named corpus")
    register.add_argument("--corpus", required=True)
    register.add_argument("--source-dir", required=True)
    register.add_argument("--top-level-only", action="store_true", help="do not discover PDFs in nested directories")
    register.add_argument("--replace", action="store_true", help="replace an existing registration and clear stale downstream artifacts")
    register.add_argument("--dry-run", action="store_true", help="inspect the proposed registration without writing corpus state")

    require = sub.add_parser("require-pdfs", help="fail unless a named corpus has at least one PDF input")
    require.add_argument("--corpus", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "register":
        result = register_pdf_directory(
            corpus=args.corpus,
            source_dir=Path(args.source_dir),
            recursive=not args.top_level_only,
            replace=args.replace,
            dry_run=args.dry_run,
        )
    elif args.command == "require-pdfs":
        result = require_corpus_pdfs(corpus=args.corpus)
    else:  # pragma: no cover - argparse enforces known subcommands
        raise RuntimeError(f"unsupported command: {args.command}")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
