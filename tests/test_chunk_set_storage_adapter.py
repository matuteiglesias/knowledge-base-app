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
