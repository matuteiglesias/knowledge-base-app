from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipeline.writers.chunk_set_writer import write_chunk_set_artifact


def _load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_chunk_set_writer_emits_required_chunk_contract_fields(tmp_path):
    chunks = [
        {
            "chunk_id": "c1",
            "paper_id": "p1",
            "text": "hello",
            "source_file": "a.xml",
            "header_path": "Intro",
            "metadata": {"k": "v"},
        },
        {
            "id": "c2",
            "paper": "p1",
            "document_id": "doc-explicit",
            "content": "world!",
            "chunk_index": 9,
            "metadata": {},
        },
    ]

    out = write_chunk_set_artifact(
        chunks,
        source_items=["a.xml"],
        run_id="run-1",
        out_dir=tmp_path,
    )
    payload = _load(out)

    assert payload["artifact_family"] == "chunk_bus"
    assert payload["artifact_kind"] == "chunk_set"
    assert payload["schema_version"] == 1
    assert payload["chunk_count"] == 2

    c1 = payload["chunks"][0]
    assert c1["chunk_id"] == "c1"
    assert c1["paper_id"] == "p1"
    assert c1["document_id"] == "p1"
    assert c1["text"] == "hello"
    assert c1["chunk_index"] == 0
    assert c1["char_len"] == 5
    assert c1["source_file"] == "a.xml"
    assert c1["header_path"] == "Intro"
    assert c1["metadata"] == {"k": "v"}

    c2 = payload["chunks"][1]
    assert c2["chunk_id"] == "c2"
    assert c2["paper_id"] == "p1"
    assert c2["document_id"] == "doc-explicit"
    assert c2["text"] == "world!"
    assert c2["chunk_index"] == 9
    assert c2["char_len"] == 6


def test_chunk_index_and_char_len_are_stabilized_for_weak_callers(tmp_path):
    chunks = [
        {"chunk_id": "a", "paper_id": "p", "text": "x"},
        {"chunk_id": "b", "paper_id": "p", "text": "yz", "chunk_index": None},
    ]
    out = write_chunk_set_artifact(
        chunks,
        source_items=["x.xml"],
        run_id="run-2",
        out_dir=tmp_path,
    )
    payload = _load(out)

    assert [c["chunk_index"] for c in payload["chunks"]] == [0, 1]
    assert [c["char_len"] for c in payload["chunks"]] == [1, 2]
    assert [c["document_id"] for c in payload["chunks"]] == ["p", "p"]
