from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.sources.corpus_fixture import promote_corpus_fixture


def _write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def _seed(repo: Path, corpus: str = "demo") -> Path:
    root = repo / "corpora" / corpus
    _write(root / "pdfs" / "a.pdf", b"%PDF fixture-a")
    _write(root / "pdfs" / "b.pdf", b"%PDF fixture-b")
    _write(root / "catalog" / "paper.catalog-record.v1.jsonl", '{"paper_uid":"paper_a","title":"A"}\n')
    _write(root / "review" / "paper.review-record.v1.jsonl", '{"paper_uid":"paper_a","title":"A"}\n')
    _write(root / "chunk_sets" / "a.chunk_set.json", '{"paper_meta":{"paper_uid":"paper_a"},"chunks":[{"text":"full text"}]}\n')
    _write(root / "xmls" / "a.xml", "<TEI>full source text</TEI>")
    _write(root / "chunks" / "a.jsonl", '{"text":"legacy"}\n')
    return root


def test_metadata_fixture_keeps_identity_and_projections_but_omits_text_derivatives(tmp_path: Path):
    repo = tmp_path / "repo"
    _seed(repo)

    result = promote_corpus_fixture(corpus="demo", repo_root=repo)

    target = repo / "fixture" / "corpora" / "demo"
    assert result["fixture_level"] == "metadata"
    assert (target / "catalog" / "paper.catalog-record.v1.jsonl").exists()
    assert (target / "review" / "paper.review-record.v1.jsonl").exists()
    assert not (target / "pdfs").exists()
    assert not (target / "xmls").exists()
    assert not (target / "chunks").exists()
    assert not (target / "chunk_sets").exists()

    manifest = json.loads((target / "fixture-manifest.json").read_text())
    assert manifest["source_pdf_count"] == 2
    assert manifest["chunk_set_count"] == 0
    assert manifest["absolute_paths_recorded"] is False
    assert all("sha256" in row for row in manifest["source_pdfs"])


def test_consumer_fixture_requires_explicit_text_derivative_acknowledgement(tmp_path: Path):
    repo = tmp_path / "repo"
    _seed(repo)

    with pytest.raises(ValueError, match="explicit --allow-text-derivatives"):
        promote_corpus_fixture(corpus="demo", repo_root=repo, level="consumer")

    promote_corpus_fixture(
        corpus="demo",
        repo_root=repo,
        level="consumer",
        allow_text_derivatives=True,
    )
    target = repo / "fixture" / "corpora" / "demo"
    assert (target / "chunk_sets" / "a.chunk_set.json").exists()
    assert not (target / "pdfs").exists()
    assert not (target / "xmls").exists()


def test_fixture_promotion_can_adopt_older_corpus_without_source_manifest(tmp_path: Path):
    repo = tmp_path / "repo"
    _seed(repo, "legacy")

    promote_corpus_fixture(corpus="legacy", repo_root=repo)

    manifest = json.loads((repo / "fixture" / "corpora" / "legacy" / "fixture-manifest.json").read_text())
    assert manifest["source_pdf_count"] == 2
    assert not (repo / "fixture" / "corpora" / "legacy" / "source-manifest.json").exists()


def test_existing_fixture_fails_closed_without_replace(tmp_path: Path):
    repo = tmp_path / "repo"
    _seed(repo)
    promote_corpus_fixture(corpus="demo", repo_root=repo)

    with pytest.raises(RuntimeError, match="fixture already exists"):
        promote_corpus_fixture(corpus="demo", repo_root=repo)

    result = promote_corpus_fixture(corpus="demo", repo_root=repo, replace=True)
    assert result["status"] == "promoted"


def test_missing_source_pdfs_is_not_a_governed_fixture(tmp_path: Path):
    repo = tmp_path / "repo"
    root = repo / "corpora" / "empty"
    _write(root / "catalog" / "paper.catalog-record.v1.jsonl", "{}\n")
    _write(root / "review" / "paper.review-record.v1.jsonl", "{}\n")

    with pytest.raises(RuntimeError, match="without source PDFs"):
        promote_corpus_fixture(corpus="empty", repo_root=repo)
