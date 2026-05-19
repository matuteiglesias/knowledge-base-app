from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import types

# tei_runner imports embed_runner at module import time; stub it for unit isolation
stub_embed = types.ModuleType("pipeline.producer.embed_runner")
stub_embed.embed_and_upsert = lambda **_kwargs: {"status": "ok"}
sys.modules.setdefault("pipeline.producer.embed_runner", stub_embed)

stub_chroma_client = types.ModuleType("shared.chroma_client")
stub_chroma_client.get_client = lambda **_kwargs: None
sys.modules.setdefault("shared.chroma_client", stub_chroma_client)

stub_chroma_helpers = types.ModuleType("shared.chroma_helpers")
stub_chroma_helpers.sanitize_meta_for_chroma = lambda x: x
sys.modules.setdefault("shared.chroma_helpers", stub_chroma_helpers)

from pipeline.producer import tei_runner
from backend.app.schemas import CanonicalChunk


TEI_MIN = """<TEI><teiHeader><fileDesc><titleStmt><title>Test Paper</title></titleStmt></fileDesc></teiHeader><text><body><p>long enough content for chunk extraction and validation test</p></body></text></TEI>"""


def _setup_tei_dir(tmp_path: Path) -> Path:
    tei_dir = tmp_path / "teis"
    tei_dir.mkdir()
    (tei_dir / "doc.tei.xml").write_text(TEI_MIN, encoding="utf-8")
    return tei_dir


def test_validation_failure_is_warning_by_default(monkeypatch, tmp_path):
    tei_dir = _setup_tei_dir(tmp_path)
    chunks_dir = tmp_path / "chunks"
    chunk_set_dir = tmp_path / "chunk_sets"

    monkeypatch.setattr(tei_runner, "_validate_chunk_set_artifact", lambda _p: {"ok": False, "error": "bad schema"})
    monkeypatch.setattr(tei_runner, "parse_tei_text", lambda _t: {"title": "T", "paper_id": "p1", "chunks": [{"text": "abc def ghi", "metadata": {}}]})
    monkeypatch.setattr(tei_runner, "chunks_to_models", lambda title, paper_id, chunks: [CanonicalChunk(chunk_id="c1", paper_id=paper_id, text="abc def ghi", chunk_index=0, char_len=11, meta={})])
    monkeypatch.setattr(tei_runner, "write_chunks_jsonl", lambda *a, **k: None)
    monkeypatch.setattr(tei_runner, "save_paper_metadata_to_fs", lambda *a, **k: None)
    monkeypatch.setattr(tei_runner, "_write_done_marker", lambda *a, **k: None)

    summary = tei_runner.parse_teis_to_chunks(
        tei_dir,
        chunks_dir,
        min_len=1,
        emit_chunk_set_artifact=True,
        chunk_set_dir=chunk_set_dir,
        validate_chunk_set=True,
        strict_chunk_set_validation=False,
    )

    assert summary["n_written"] == 1
    assert summary["n_chunk_set_artifacts"] == 1
    assert summary["n_chunk_set_validation_failures"] == 1
    assert summary["validation"][0]["ok"] is False
    assert summary["n_failures"] == 0


def test_validation_failure_is_strict_error_when_enabled(monkeypatch, tmp_path):
    tei_dir = _setup_tei_dir(tmp_path)
    chunks_dir = tmp_path / "chunks"
    chunk_set_dir = tmp_path / "chunk_sets"

    monkeypatch.setattr(tei_runner, "_validate_chunk_set_artifact", lambda _p: {"ok": False, "error": "bad schema"})
    monkeypatch.setattr(tei_runner, "parse_tei_text", lambda _t: {"title": "T", "paper_id": "p1", "chunks": [{"text": "abc def ghi", "metadata": {}}]})
    monkeypatch.setattr(tei_runner, "chunks_to_models", lambda title, paper_id, chunks: [CanonicalChunk(chunk_id="c1", paper_id=paper_id, text="abc def ghi", chunk_index=0, char_len=11, meta={})])
    monkeypatch.setattr(tei_runner, "write_chunks_jsonl", lambda *a, **k: None)
    monkeypatch.setattr(tei_runner, "save_paper_metadata_to_fs", lambda *a, **k: None)
    monkeypatch.setattr(tei_runner, "_write_done_marker", lambda *a, **k: None)

    summary = tei_runner.parse_teis_to_chunks(
        tei_dir,
        chunks_dir,
        min_len=1,
        emit_chunk_set_artifact=True,
        chunk_set_dir=chunk_set_dir,
        validate_chunk_set=True,
        strict_chunk_set_validation=True,
    )

    assert summary["n_written"] == 0
    assert summary["n_failures"] == 1
    assert summary["n_chunk_set_validation_failures"] == 1
    assert "validation failed" in summary["errors"][0]["error"]
