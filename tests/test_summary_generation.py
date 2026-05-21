from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.exports.build_summary_inputs import build_summary_inputs
from backend.exports import generate_summaries as gs_mod
from backend.exports.generate_summaries import generate_summaries
from pipeline.corpus import resolve_corpus_paths


def _write_chunk_set(path: Path, paper_id: str, title: str, texts: list[str]):
    chunks = [
        {
            "chunk_id": f"{paper_id}_c{i}",
            "paper_id": paper_id,
            "text": t,
            "chunk_index": i,
            "char_len": len(t),
            "source_file": f"{paper_id}.tei.xml",
            "metadata": {"title": title},
        }
        for i, t in enumerate(texts)
    ]
    payload = {"artifact_kind": "chunk_set", "chunks": chunks, "paper_meta": {"paper_id": paper_id, "title": title}}
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_summary_idempotency_and_force(tmp_path):
    paths = resolve_corpus_paths("demo_idem").ensure_dirs()
    import shutil
    shutil.rmtree(paths.root, ignore_errors=True)
    paths = resolve_corpus_paths("demo_idem").ensure_dirs()
    sets = paths.chunk_sets
    _write_chunk_set(sets / "a.chunk_set.json", "p1", "Paper 1", ["alpha text", "beta text"])

    in_path, n_inputs = build_summary_inputs("demo_idem", limit=1, max_chunks=1)
    assert n_inputs == 1
    assert in_path.exists()

    _, stats1 = asyncio.run(generate_summaries("demo_idem", "mock", limit=1))
    assert stats1.written == 1
    assert stats1.provider_calls == 1
    assert stats1.skipped_existing == 0

    summary_path = paths.root / "summaries" / "p1.summary.json"
    first_content = summary_path.read_text(encoding="utf-8")
    first_mtime = summary_path.stat().st_mtime

    _, stats2 = asyncio.run(generate_summaries("demo_idem", "mock", limit=1))
    assert stats2.written == 0
    assert stats2.provider_calls == 0
    assert stats2.skipped_existing == 1
    assert summary_path.read_text(encoding="utf-8") == first_content
    assert summary_path.stat().st_mtime == first_mtime

    time.sleep(0.01)
    _, stats3 = asyncio.run(generate_summaries("demo_idem", "mock", limit=1, force=True))
    assert stats3.written == 1
    assert stats3.provider_calls == 1
    assert stats3.skipped_existing == 0
    assert summary_path.stat().st_mtime >= first_mtime

    artifact = json.loads(summary_path.read_text(encoding="utf-8"))
    required_keys = {
        "paper_id", "title", "summary_version", "generated_at", "provider", "model", "source", "status", "one_line",
        "research_question", "data", "method", "main_contribution", "limitations", "relevance_to_thesis",
        "suggested_tags", "confidence", "warnings",
    }
    assert required_keys.issubset(set(artifact.keys()))
    assert artifact["summary_version"] == 1
    assert artifact["source"]["corpus"] == "demo_idem"


def test_hierarchical_mode_writes_intermediate_and_run_record(tmp_path):
    paths = resolve_corpus_paths("demo_hier").ensure_dirs()
    import shutil
    shutil.rmtree(paths.root, ignore_errors=True)
    paths = resolve_corpus_paths("demo_hier").ensure_dirs()
    sets = paths.chunk_sets

    payload = {
        "artifact_kind": "chunk_set",
        "paper_meta": {"paper_id": "p2", "title": "Paper 2"},
        "chunks": [
                        {"chunk_id": "p2_c0", "paper_id": "p2", "text": "text 0", "chunk_index": 0, "char_len": 6, "header_path": ["Section 0"]},
            {"chunk_id": "p2_c1", "paper_id": "p2", "text": "text 1", "chunk_index": 1, "char_len": 6, "header_path": ["Section 1"]},
            {"chunk_id": "p2_c2", "paper_id": "p2", "text": "text 2", "chunk_index": 2, "char_len": 6, "header_path": ["Section 2"]},
            {"chunk_id": "p2_c3", "paper_id": "p2", "text": "text 3", "chunk_index": 3, "char_len": 6, "header_path": ["Section 0"]},
            {"chunk_id": "p2_c4", "paper_id": "p2", "text": "text 4", "chunk_index": 4, "char_len": 6, "header_path": ["Section 1"]},
            {"chunk_id": "p2_c5", "paper_id": "p2", "text": "text 5", "chunk_index": 5, "char_len": 6, "header_path": ["Section 2"]},
            {"chunk_id": "p2_c6", "paper_id": "p2", "text": "text 6", "chunk_index": 6, "char_len": 6, "header_path": ["Section 0"]},
            {"chunk_id": "p2_c7", "paper_id": "p2", "text": "text 7", "chunk_index": 7, "char_len": 6, "header_path": ["Section 1"]},
            {"chunk_id": "p2_c8", "paper_id": "p2", "text": "text 8", "chunk_index": 8, "char_len": 6, "header_path": ["Section 2"]},
            {"chunk_id": "p2_c9", "paper_id": "p2", "text": "text 9", "chunk_index": 9, "char_len": 6, "header_path": ["Section 0"]},
        ],
    }
    (sets / "a.chunk_set.json").write_text(json.dumps(payload), encoding="utf-8")

    out_path, stats = asyncio.run(generate_summaries("demo_hier", "mock", limit=1, mode="hierarchical", force=True))
    assert out_path.exists()
    assert stats.written == 1
    assert stats.n_section_calls >= 1
    assert stats.n_synthesis_calls == 1
    assert stats.provider_calls == stats.n_section_calls + stats.n_synthesis_calls

    run_dir = out_path.parents[1]
    inter = run_dir / "intermediate" / "p2.section_summaries.jsonl"
    assert inter.exists()
    assert inter.read_text(encoding="utf-8").strip()

    record = json.loads((run_dir / "run_record.json").read_text(encoding="utf-8"))
    assert record["mode"] == "hierarchical"
    assert record["n_section_calls"] == stats.n_section_calls
    assert record["n_synthesis_calls"] == stats.n_synthesis_calls
    assert record["provider_calls_total"] == stats.provider_calls

    out_rows = [json.loads(ln) for ln in out_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(out_rows) == 1
    out_row = out_rows[0]
    assert out_row["paper_id"] == "p2"
    assert out_row["mode"] == "hierarchical"
    assert out_row["n_section_calls"] == stats.n_section_calls
    assert out_row["n_synthesis_calls"] == stats.n_synthesis_calls
    assert out_row["provider_calls_total"] == stats.provider_calls
    assert Path(out_row["final_summary_path"]).exists()
    assert Path(out_row["intermediate_path"]).exists()


def test_hierarchical_idempotency_skips_when_final_exists(tmp_path):
    paths = resolve_corpus_paths("demo_hier_idem").ensure_dirs()
    import shutil
    shutil.rmtree(paths.root, ignore_errors=True)
    paths = resolve_corpus_paths("demo_hier_idem").ensure_dirs()
    sets = paths.chunk_sets
    _write_chunk_set(sets / "a.chunk_set.json", "p3", "Paper 3", ["x", "y", "z"])

    _, stats1 = asyncio.run(generate_summaries("demo_hier_idem", "mock", limit=1, mode="hierarchical", force=True))
    assert stats1.written == 1
    _, stats2 = asyncio.run(generate_summaries("demo_hier_idem", "mock", limit=1, mode="hierarchical", force=False))
    assert stats2.written == 0
    assert stats2.skipped_existing == 1
    assert stats2.provider_calls == 0


def test_hierarchical_small_paper_uses_direct_synthesis_only(tmp_path):
    paths = resolve_corpus_paths("demo_hier_small").ensure_dirs()
    import shutil
    shutil.rmtree(paths.root, ignore_errors=True)
    paths = resolve_corpus_paths("demo_hier_small").ensure_dirs()
    sets = paths.chunk_sets
    _write_chunk_set(sets / "a.chunk_set.json", "p4", "Paper 4", ["a", "b", "c"])

    out_path, stats = asyncio.run(generate_summaries("demo_hier_small", "mock", limit=1, mode="hierarchical", force=True))
    assert out_path.exists()
    assert stats.written == 1
    assert stats.n_section_calls == 0
    assert stats.n_synthesis_calls == 1
    assert stats.provider_calls == 1


def test_invalid_provider_output_does_not_write_ready_summary_and_writes_failure(tmp_path, monkeypatch):
    paths = resolve_corpus_paths("demo_invalid_output").ensure_dirs()
    import shutil
    shutil.rmtree(paths.root, ignore_errors=True)
    paths = resolve_corpus_paths("demo_invalid_output").ensure_dirs()
    _write_chunk_set(paths.chunk_sets / "a.chunk_set.json", "p5", "Paper 5", ["alpha", "beta"])

    class BadProvider:
        provider_name = "bad"
        model_name = "bad-v1"

        async def summarize(self, summary_input):
            return {"one_line": "x"}  # Missing required keys.

    monkeypatch.setattr(gs_mod, "_provider", lambda *args, **kwargs: BadProvider())
    out_path, stats = asyncio.run(generate_summaries("demo_invalid_output", "mock", limit=1, force=True))
    assert out_path.exists()
    assert stats.written == 0

    final = paths.root / "summaries" / "p5.summary.json"
    assert not final.exists()

    lines = [json.loads(ln) for ln in out_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    assert lines[0]["status"] == "failed_validation"
    assert "Invalid LLM summary output" in lines[0]["error"]
