from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.exports.build_summary_inputs import build_summary_inputs
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
