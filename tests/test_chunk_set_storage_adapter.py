from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.storage_adapter import ChunkSetStorageAdapter, create_adapter_from_env


def _write_chunk_set(path: Path):
    payload = {
        "artifact_family": "chunk_bus",
        "artifact_kind": "chunk_set",
        "schema_version": 1,
        "run_id": "r1",
        "producer": "paper-kb",
        "entrypoint": "paper_tei_parse",
        "source_items": ["a.xml"],
        "chunk_count": 2,
        "chunks": [
            {
                "chunk_id": "c1",
                "paper_id": "p1",
                "document_id": "p1",
                "text": "alpha beta",
                "chunk_index": 0,
                "char_len": 10,
                "source_file": "a.xml",
                "header_path": ["Intro"],
                "metadata": {"title": "Paper One", "authors": ["Ada"]},
            },
            {
                "chunk_id": "c2",
                "paper_id": "p1",
                "document_id": "p1",
                "text": "beta gamma",
                "chunk_index": 1,
                "char_len": 10,
                "source_file": "a.xml",
                "header_path": ["Methods"],
                "metadata": {},
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_chunk_set_with_chunks(path: Path, run_id: str, chunks):
    payload = {
        "artifact_family": "chunk_bus",
        "artifact_kind": "chunk_set",
        "schema_version": 1,
        "run_id": run_id,
        "producer": "paper-kb",
        "entrypoint": "paper_tei_parse",
        "source_items": ["a.xml"],
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_chunk_set_adapter_serves_papers_chunks_and_search(tmp_path):
    d = tmp_path / "chunk_sets"
    d.mkdir()
    _write_chunk_set(d / "r1.chunk_set.json")

    adapter = ChunkSetStorageAdapter(chunk_sets_dir=str(d))
    adapter.load_caches()

    papers = adapter.list_papers()
    assert len(papers) == 1
    assert papers[0]["paper_id"] == "p1"
    assert papers[0]["title"] == "Paper One"
    assert papers[0]["n_chunks"] == 2

    listed = adapter.list_chunks("p1", limit=10, offset=0)
    assert listed["n"] == 2
    assert [c["chunk_id"] for c in listed["chunks"]] == ["c1", "c2"]

    c = adapter.get_chunk("p1", "c2")
    assert c is not None
    assert c["text"] == "beta gamma"

    hits = adapter.semantic_search("alpha", k=3, paper_id="p1")
    assert len(hits) == 1
    assert hits[0]["id"] == "c1"


def test_create_adapter_from_env_chunk_set(tmp_path, monkeypatch):
    d = tmp_path / "sets"
    d.mkdir()
    monkeypatch.setenv("STORAGE_BACKEND", "chunk_set")
    monkeypatch.setenv("PAPER_KB_CHUNK_SETS_DIR", str(d))

    adapter = create_adapter_from_env()
    assert isinstance(adapter, ChunkSetStorageAdapter)
    assert adapter.chunk_sets_dir == d


def test_chunk_set_adapter_reconstructs_human_readable_paper_meta_from_paper_meta_payload(tmp_path):
    d = tmp_path / "chunk_sets"
    d.mkdir()
    payload = {
        "artifact_family": "chunk_bus",
        "artifact_kind": "chunk_set",
        "schema_version": 1,
        "run_id": "r-meta",
        "producer": "paper-kb",
        "entrypoint": "paper_tei_parse",
        "source_items": ["tei_doc.xml"],
        "paper_meta": {
            "paper_id": "p2",
            "title": "A TEI Derived Title",
            "authors": ["Alice A.", "Bob B."],
            "source_file": "tei_doc.xml",
        },
        "chunk_count": 1,
        "chunks": [
            {
                "chunk_id": "c1",
                "paper_id": "p2",
                "document_id": "p2",
                "text": "some text",
                "chunk_index": 0,
                "char_len": 9,
                "source_file": "tei_doc.xml",
                "header_path": ["Intro"],
                "metadata": {},
            }
        ],
    }
    (d / "r-meta.chunk_set.json").write_text(json.dumps(payload), encoding="utf-8")

    adapter = ChunkSetStorageAdapter(chunk_sets_dir=str(d))
    papers = adapter.list_papers()
    assert len(papers) == 1
    paper = papers[0]
    assert paper["paper_id"] == "p2"
    assert paper["title"] == "A TEI Derived Title"
    assert paper["source_file"] == "tei_doc.xml"
    assert paper["authors"] == ["Alice A.", "Bob B."]


def test_chunk_set_adapter_reconstructs_authors_as_array_and_source_file_from_chunk_metadata(tmp_path):
    d = tmp_path / "chunk_sets"
    d.mkdir()
    payload = {
        "artifact_family": "chunk_bus",
        "artifact_kind": "chunk_set",
        "schema_version": 1,
        "run_id": "r-meta-fallback",
        "producer": "paper-kb",
        "entrypoint": "paper_tei_parse",
        "source_items": ["fallback.xml"],
        "chunk_count": 1,
        "chunks": [
            {
                "chunk_id": "c1",
                "paper_id": "p3",
                "document_id": "p3",
                "text": "some text",
                "chunk_index": 0,
                "char_len": 9,
                "source_file": "fallback.xml",
                "header_path": ["Fallback Title"],
                "metadata": {"title": "Chunk Meta Title"},
            }
        ],
    }
    (d / "r-fallback.chunk_set.json").write_text(json.dumps(payload), encoding="utf-8")

    adapter = ChunkSetStorageAdapter(chunk_sets_dir=str(d))
    papers = adapter.list_papers()
    assert len(papers) == 1
    paper = papers[0]
    assert paper["paper_id"] == "p3"
    assert paper["title"] == "Chunk Meta Title"
    assert paper["source_file"] == "fallback.xml"
    assert isinstance(paper["authors"], list)
    assert paper["authors"] == []


def test_chunk_set_adapter_deduplicates_duplicate_chunk_ids_with_latest_artifact_precedence(tmp_path):
    d = tmp_path / "chunk_sets"
    d.mkdir()

    old_path = d / "a_old.chunk_set.json"
    new_path = d / "b_new.chunk_set.json"

    _write_chunk_set_with_chunks(
        old_path,
        run_id="old",
        chunks=[
            {
                "chunk_id": "dup-1",
                "paper_id": "p1",
                "document_id": "p1",
                "text": "older text",
                "chunk_index": 2,
                "char_len": 10,
                "source_file": "a.xml",
                "header_path": ["Methods"],
                "metadata": {"title": "Paper One"},
            },
            {
                "chunk_id": "unique-old",
                "paper_id": "p1",
                "document_id": "p1",
                "text": "old unique",
                "chunk_index": 0,
                "char_len": 10,
                "source_file": "a.xml",
                "header_path": ["Intro"],
                "metadata": {"title": "Paper One"},
            },
        ],
    )

    _write_chunk_set_with_chunks(
        new_path,
        run_id="new",
        chunks=[
            {
                "chunk_id": "dup-1",
                "paper_id": "p1",
                "document_id": "p1",
                "text": "newer text",
                "chunk_index": 1,
                "char_len": 10,
                "source_file": "b.xml",
                "header_path": ["Results"],
                "metadata": {"title": "Paper One"},
            },
        ],
    )

    # Ensure deterministic mtime precedence: old then new.
    old_stat = old_path.stat()
    new_stat = new_path.stat()
    new_mtime = max(old_stat.st_mtime, new_stat.st_mtime) + 5
    old_mtime = new_mtime - 10
    old_path.touch()
    new_path.touch()
    import os
    os.utime(old_path, (old_mtime, old_mtime))
    os.utime(new_path, (new_mtime, new_mtime))

    adapter = ChunkSetStorageAdapter(chunk_sets_dir=str(d))
    adapter.load_caches()

    listed = adapter.list_chunks("p1", limit=10, offset=0)
    chunk_ids = [c["chunk_id"] for c in listed["chunks"]]

    assert chunk_ids == ["unique-old", "dup-1"]
    assert listed["n"] == 2

    dup = adapter.get_chunk("p1", "dup-1")
    assert dup is not None
    assert dup["text"] == "newer text"

    papers = adapter.list_papers()
    assert len(papers) == 1
    assert papers[0]["paper_id"] == "p1"
    assert papers[0]["n_chunks"] == 2
