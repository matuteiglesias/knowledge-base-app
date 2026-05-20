from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import types

if "lxml" not in sys.modules:
    fake_lxml = types.ModuleType("lxml")
    fake_lxml.etree = types.SimpleNamespace()
    sys.modules["lxml"] = fake_lxml

from pipeline.adapter import manager
from pipeline.corpus import resolve_corpus_paths


def _write_chunk_set(path: Path, *, null_header: bool = False, duplicate: bool = False) -> None:
    chunks = [
        {"chunk_id": "c1", "paper_id": "p1", "text": "alpha", "chunk_index": 0, "header_path": None if null_header else ["Intro"]},
        {"chunk_id": "c1" if duplicate else "c2", "paper_id": "p1", "text": "beta", "chunk_index": 1, "header_path": ["Methods"]},
    ]
    payload = {"artifact_family": "chunk_bus", "artifact_kind": "chunk_set", "schema_version": 1, "run_id": "r1", "chunks": chunks}
    path.write_text(json.dumps(payload), encoding="utf-8")


def _patch_paths(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(manager, "resolve_corpus_paths", lambda name: resolve_corpus_paths(name, repo_root=tmp_path))


def test_doctor_empty_corpus(tmp_path: Path, monkeypatch):
    _patch_paths(monkeypatch, tmp_path)
    r = manager.run_doctor(corpus="empty")
    assert r["corpus_name"] == "empty"
    assert r["n_pdfs"] == 0
    assert r["n_chunk_sets"] == 0
    assert r["ready_to_parse"] is False
    assert r["ready_to_serve"] is False


def test_doctor_healthy_corpus(tmp_path: Path, monkeypatch):
    _patch_paths(monkeypatch, tmp_path)
    root = tmp_path / "corpora" / "tesislcd"
    (root / "pdfs").mkdir(parents=True)
    (root / "xmls").mkdir(parents=True)
    (root / "chunk_sets").mkdir(parents=True)
    (root / "pdfs" / "a.pdf").write_bytes(b"%PDF")
    (root / "xmls" / "a.xml").write_text("<TEI />", encoding="utf-8")
    _write_chunk_set(root / "chunk_sets" / "r1.chunk_set.json")

    r = manager.run_doctor(corpus="tesislcd")
    assert r["n_pdfs"] == 1
    assert r["n_xmls"] == 1
    assert r["n_chunk_sets"] == 1
    assert r["chunk_set_validation"]["n_fail"] == 0
    assert r["ready_to_parse"] is True
    assert r["ready_to_serve"] is True


def test_doctor_invalid_chunk_set_and_null_header(tmp_path: Path, monkeypatch):
    _patch_paths(monkeypatch, tmp_path)
    root = tmp_path / "corpora" / "tesislcd"
    (root / "chunk_sets").mkdir(parents=True)
    _write_chunk_set(root / "chunk_sets" / "bad.chunk_set.json", null_header=True, duplicate=True)
    (root / "chunk_sets" / "broken.chunk_set.json").write_text("{not-json", encoding="utf-8")

    r = manager.run_doctor(corpus="tesislcd", strict=True)
    assert r["chunk_set_validation"]["n_fail"] == 1
    assert r["null_header_path_count"] >= 1
    assert r["duplicate_chunk_id_count"] >= 1
    assert r["strict_failed"] is True
