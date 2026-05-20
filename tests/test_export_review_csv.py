from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.storage_adapter import ChunkSetStorageAdapter
from backend.exports.export_review_csv import _resolve_export_targets, export_review_csv


def _write_chunk_set(path: Path, chunks, paper_meta=None):
    payload = {
        "artifact_family": "chunk_bus",
        "artifact_kind": "chunk_set",
        "schema_version": 1,
        "run_id": path.stem,
        "producer": "paper-kb",
        "entrypoint": "paper_tei_parse",
        "source_items": ["a.xml"],
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
    if paper_meta:
        payload["paper_meta"] = paper_meta
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_export_review_csv_two_papers(tmp_path):
    sets = tmp_path / "chunk_sets"
    sets.mkdir()
    out = tmp_path / "exports" / "review" / "papers.csv"

    _write_chunk_set(
        sets / "r1.chunk_set.json",
        chunks=[
            {
                "chunk_id": "c1",
                "paper_id": "p1",
                "text": "Chunk text for p1",
                "chunk_index": 0,
                "char_len": 17,
                "source_file": "p1.tei.xml",
                "metadata": {},
            }
        ],
        paper_meta={"paper_id": "p1", "title": "Paper One", "source_file": "p1.tei.xml"},
    )
    _write_chunk_set(
        sets / "r2.chunk_set.json",
        chunks=[
            {
                "chunk_id": "c2",
                "paper_id": "p2",
                "text": "Fallback abstract from chunk",
                "chunk_index": 0,
                "char_len": 28,
                "source_file": "p2.tei.xml",
                "metadata": {"title": "Paper Two"},
            }
        ],
        paper_meta={"paper_id": "p2", "title": "Paper Two", "source_file": "p2.tei.xml"},
    )

    adapter = ChunkSetStorageAdapter(chunk_sets_dir=str(sets))
    export_review_csv(out, storage=adapter)

    assert out.exists()
    rows = list(csv.DictReader(out.open("r", encoding="utf-8")))
    assert len(rows) == 2
    by_id = {r["paper_id"]: r for r in rows}
    assert by_id["p1"]["doc_id"] == "p1"
    assert by_id["p1"]["title"] == "Paper One"
    assert by_id["p1"]["paper_id"] == "p1"
    assert by_id["p1"]["abstract"] != ""
    assert by_id["p1"]["tags"] == ""
    assert by_id["p1"]["badges"] == ""
    assert by_id["p2"]["title"] == "Paper Two"
    assert by_id["p2"]["abstract"] == "Fallback abstract from chunk"


def test_resolve_export_targets_with_corpus_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out_path, chunk_set_dir = _resolve_export_targets(out_path=None, chunk_set_dir=None, corpus="eric_mvukiyehe")
    assert out_path is not None
    assert chunk_set_dir is not None
    assert str(out_path).endswith("corpora/eric_mvukiyehe/review/papers.csv")
    assert str(chunk_set_dir).endswith("corpora/eric_mvukiyehe/chunk_sets")


def test_export_review_csv_with_explicit_chunk_set_dir_without_env(tmp_path):
    sets = tmp_path / "corpora" / "eric_mvukiyehe" / "chunk_sets"
    sets.mkdir(parents=True)
    out = tmp_path / "corpora" / "eric_mvukiyehe" / "review" / "papers.csv"

    _write_chunk_set(
        sets / "r1.chunk_set.json",
        chunks=[
            {
                "chunk_id": "c1",
                "paper_id": "p1",
                "text": "Useful abstract text",
                "chunk_index": 0,
                "char_len": 20,
                "source_file": "p1.tei.xml",
                "metadata": {},
            }
        ],
        paper_meta={"paper_id": "p1", "title": "Human Title"},
    )

    adapter = ChunkSetStorageAdapter(chunk_sets_dir=str(sets))
    export_review_csv(out, storage=adapter)
    rows = list(csv.DictReader(out.open("r", encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["title"] == "Human Title"
    assert rows[0]["abstract"] == "Useful abstract text"
