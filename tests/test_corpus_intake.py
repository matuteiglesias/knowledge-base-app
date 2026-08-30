from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pipeline.sources.corpus_intake import discover_pdfs, register_pdf_directory, require_corpus_pdfs


def _pdf(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_register_pdf_directory_creates_portable_manifest_and_flat_snapshot(tmp_path: Path):
    source = tmp_path / "incoming"
    _pdf(source / "paper-a.pdf", b"%PDF-1.4\npaper-a\n")
    _pdf(source / "nested" / "paper-b.PDF", b"%PDF-1.4\npaper-b\n")
    repo = tmp_path / "repo"

    result = register_pdf_directory(corpus="fcv-literature", source_dir=source, repo_root=repo)

    assert result["status"] == "registered"
    corpus_root = repo / "corpora" / "fcv-literature"
    assert (corpus_root / "pdfs" / "paper-a.pdf").read_bytes() == b"%PDF-1.4\npaper-a\n"
    assert (corpus_root / "pdfs" / "paper-b.PDF").read_bytes() == b"%PDF-1.4\npaper-b\n"

    manifest_text = (corpus_root / "source-manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    assert manifest["schema_id"] == "paper-kb.corpus-source-manifest"
    assert manifest["corpus_id"] == "fcv-literature"
    assert manifest["source_path_recorded"] is False
    assert manifest["pdf_count"] == 2
    assert str(source.resolve()) not in manifest_text
    assert [row["source_relative_path"] for row in manifest["files"]] == ["nested/paper-b.PDF", "paper-a.pdf"]
    assert {row["registered_filename"] for row in manifest["files"]} == {"paper-a.pdf", "paper-b.PDF"}
    assert manifest["files"][0]["sha256"] == hashlib.sha256(b"%PDF-1.4\npaper-b\n").hexdigest()


def test_same_registration_is_idempotent(tmp_path: Path):
    source = tmp_path / "incoming"
    _pdf(source / "paper.pdf", b"%PDF-1.4\nstable\n")
    repo = tmp_path / "repo"

    first = register_pdf_directory(corpus="papers", source_dir=source, repo_root=repo)
    manifest_before = (repo / "corpora" / "papers" / "source-manifest.json").read_bytes()
    second = register_pdf_directory(corpus="papers", source_dir=source, repo_root=repo)

    assert first["status"] == "registered"
    assert second["status"] == "unchanged"
    assert second["input_set_sha256"] == first["input_set_sha256"]
    assert (repo / "corpora" / "papers" / "source-manifest.json").read_bytes() == manifest_before


def test_input_identity_ignores_incidental_source_folder_layout(tmp_path: Path):
    source_a = tmp_path / "incoming-a"
    source_b = tmp_path / "incoming-b"
    payload = b"%PDF-1.4\nsame-paper\n"
    _pdf(source_a / "topic" / "paper.pdf", payload)
    _pdf(source_b / "archive" / "deep" / "paper.pdf", payload)
    repo = tmp_path / "repo"

    first = register_pdf_directory(corpus="papers", source_dir=source_a, repo_root=repo)
    second = register_pdf_directory(corpus="papers", source_dir=source_b, repo_root=repo)

    assert second["status"] == "unchanged"
    assert second["input_set_sha256"] == first["input_set_sha256"]


def test_require_corpus_pdfs_fails_closed_for_empty_corpus(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "corpora" / "papers" / "pdfs").mkdir(parents=True)

    with pytest.raises(RuntimeError, match="has 0 PDFs"):
        require_corpus_pdfs(corpus="papers", repo_root=repo)


def test_require_corpus_pdfs_accepts_registered_inputs(tmp_path: Path):
    source = tmp_path / "incoming"
    _pdf(source / "paper.pdf", b"pdf")
    repo = tmp_path / "repo"
    register_pdf_directory(corpus="papers", source_dir=source, repo_root=repo)

    result = require_corpus_pdfs(corpus="papers", repo_root=repo)

    assert result["pdf_count"] == 1


def test_registration_recovers_from_old_empty_build_skeleton(tmp_path: Path):
    source = tmp_path / "incoming"
    _pdf(source / "paper.pdf", b"%PDF-1.4\nreal-input\n")
    repo = tmp_path / "repo"
    corpus_root = repo / "corpora" / "papers"
    (corpus_root / "pdfs").mkdir(parents=True)
    (corpus_root / "xmls").mkdir()
    (corpus_root / "chunks").mkdir()
    (corpus_root / "chunk_sets").mkdir()
    (corpus_root / "review").mkdir()
    (corpus_root / "catalog").mkdir()
    (corpus_root / "review" / "paper.review-record.v1.jsonl").write_bytes(b"")
    (corpus_root / "catalog" / "paper.catalog-record.v1.jsonl").write_bytes(b"")

    result = register_pdf_directory(corpus="papers", source_dir=source, repo_root=repo)

    assert result["status"] == "registered"
    assert result["recovered_empty_build_skeleton"] is True
    assert (corpus_root / "pdfs" / "paper.pdf").read_bytes() == b"%PDF-1.4\nreal-input\n"


def test_registration_still_refuses_meaningful_unmanaged_state(tmp_path: Path):
    source = tmp_path / "incoming"
    _pdf(source / "paper.pdf", b"pdf")
    repo = tmp_path / "repo"
    existing = repo / "corpora" / "papers" / "review" / "manual-note.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("keep me", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already contains local state"):
        register_pdf_directory(corpus="papers", source_dir=source, repo_root=repo)


def test_changed_input_fails_closed_without_replace_and_replace_clears_generated_state(tmp_path: Path):
    source = tmp_path / "incoming"
    _pdf(source / "paper.pdf", b"%PDF-1.4\nv1\n")
    repo = tmp_path / "repo"
    register_pdf_directory(corpus="papers", source_dir=source, repo_root=repo)

    generated = repo / "corpora" / "papers" / "chunk_sets" / "stale.chunk_set.json"
    generated.write_text("{}", encoding="utf-8")
    _pdf(source / "paper.pdf", b"%PDF-1.4\nv2\n")

    with pytest.raises(RuntimeError, match="different input set"):
        register_pdf_directory(corpus="papers", source_dir=source, repo_root=repo)

    replaced = register_pdf_directory(corpus="papers", source_dir=source, repo_root=repo, replace=True)
    assert replaced["status"] == "registered"
    assert not generated.exists()
    assert (repo / "corpora" / "papers" / "pdfs" / "paper.pdf").read_bytes() == b"%PDF-1.4\nv2\n"


def test_registration_refuses_duplicate_basenames(tmp_path: Path):
    source = tmp_path / "incoming"
    _pdf(source / "a" / "paper.pdf", b"one")
    _pdf(source / "b" / "paper.pdf", b"two")

    with pytest.raises(ValueError, match="duplicate PDF basenames"):
        discover_pdfs(source, recursive=True)


def test_registration_refuses_empty_or_unsafe_inputs(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no PDF files"):
        register_pdf_directory(corpus="papers", source_dir=empty, repo_root=tmp_path / "repo")

    source = tmp_path / "incoming"
    _pdf(source / "paper.pdf", b"pdf")
    with pytest.raises(ValueError, match="corpus name"):
        register_pdf_directory(corpus="../escape", source_dir=source, repo_root=tmp_path / "repo")


def test_source_dir_must_not_be_inside_target_corpus(tmp_path: Path):
    repo = tmp_path / "repo"
    source = repo / "corpora" / "papers" / "incoming"
    _pdf(source / "paper.pdf", b"pdf")

    with pytest.raises(ValueError, match="outside the target corpus directory"):
        register_pdf_directory(corpus="papers", source_dir=source, repo_root=repo)


def test_dry_run_writes_nothing(tmp_path: Path):
    source = tmp_path / "incoming"
    _pdf(source / "paper.pdf", b"pdf")
    repo = tmp_path / "repo"

    result = register_pdf_directory(corpus="papers", source_dir=source, repo_root=repo, dry_run=True)

    assert result["status"] == "would_register"
    assert not (repo / "corpora" / "papers").exists()
