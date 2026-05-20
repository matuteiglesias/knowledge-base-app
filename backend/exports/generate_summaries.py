from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.storage_adapter import ChunkSetStorageAdapter
from backend.exports.build_summary_inputs import build_summary_inputs
from backend.exports.summary_artifacts import build_summary_artifact, summary_path, write_json_atomic
from backend.llm.agent_framework_provider import AgentFrameworkSummaryProvider
from backend.llm.base import SummaryInput
from backend.llm.mock_provider import MockSummaryProvider
from pipeline.corpus import resolve_corpus_paths


def _provider(name: str):
    if name == "mock":
        return MockSummaryProvider()
    if name == "agent-framework":
        return AgentFrameworkSummaryProvider()
    raise ValueError(f"unknown provider: {name}")


@dataclass
class RunStats:
    written: int = 0
    skipped_existing: int = 0
    provider_calls: int = 0


def _read_input_rows(inputs_path: Path) -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in inputs_path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _build_row_for_paper(corpus: str, paper_id: str, max_chunks: int = 6, max_chars: int = 6000) -> dict[str, Any]:
    paths = resolve_corpus_paths(corpus).ensure_dirs()
    storage = ChunkSetStorageAdapter(chunk_sets_dir=str(paths.chunk_sets))
    storage.load_caches()
    paper = storage.get_paper(paper_id)
    if not paper:
        raise KeyError(f"paper not found: {paper_id}")
    all_chunks = storage.list_chunks(paper_id, limit=1000000).get("chunks", [])
    chunks = all_chunks[:max_chunks]
    context = "\n".join(f"[{i}] {' '.join(str(c.get('text') or '').split())}" for i, c in enumerate(chunks, 1))[:max_chars]
    prompt = f"Summarize the paper as JSON with keys: summary, key_points, limitations.\\npaper_id={paper_id}\\ntitle={paper.get('title','')}\\nContext:\\n{context}"
    return {
        "paper_id": paper_id,
        "title": paper.get("title"),
        "prompt": prompt,
        "context": {"n_chunks_total": len(all_chunks), "n_chunks_selected": len(chunks)},
        "selected_chunk_ids": [c.get("chunk_id") for c in chunks if c.get("chunk_id")],
    }


async def _execute_provider(provider: Any, row: dict[str, Any]) -> dict[str, Any]:
    return await provider.summarize(
        SummaryInput(paper_id=row["paper_id"], prompt=row["prompt"], context=row.get("context") or {})
    )


async def generate_summary_for_row(corpus: str, row: dict[str, Any], provider_name: str, force: bool = False, provider: Any | None = None) -> tuple[dict[str, Any], bool]:
    provider = provider or _provider(provider_name)
    paths = resolve_corpus_paths(corpus).ensure_dirs()
    summaries_dir = paths.root / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    pid = row["paper_id"]
    target = summary_path(summaries_dir, pid)
    if target.exists() and not force:
        return json.loads(target.read_text(encoding="utf-8")), False

    payload = await _execute_provider(provider, row)
    artifact = build_summary_artifact(
        paper_id=pid,
        title=str(row.get("title") or ""),
        provider=getattr(provider, "provider_name", provider_name),
        model=getattr(provider, "model_name", ""),
        corpus=corpus,
        chunk_set_dir=str(paths.chunk_sets),
        n_chunks_total=int(row.get("context", {}).get("n_chunks_total", 0)),
        n_chunks_selected=int(row.get("context", {}).get("n_chunks_selected", 0)),
        selected_chunk_ids=list(row.get("selected_chunk_ids") or []),
        payload=payload,
    )
    write_json_atomic(target, artifact)
    return artifact, True


async def generate_summary_for_paper(corpus: str, paper_id: str, provider_name: str, force: bool = False) -> tuple[dict[str, Any], bool]:
    row = _build_row_for_paper(corpus=corpus, paper_id=paper_id)
    return await generate_summary_for_row(corpus=corpus, row=row, provider_name=provider_name, force=force)


async def generate_summaries(corpus: str, provider_name: str, limit: int | None = None, force: bool = False) -> tuple[Path, RunStats]:
    provider = _provider(provider_name)
    inputs_path, _ = build_summary_inputs(corpus=corpus, limit=limit)
    rows = _read_input_rows(inputs_path)

    paths = resolve_corpus_paths(corpus).ensure_dirs()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = paths.root / "summary_runs" / run_id / "outputs" / "paper_summary_outputs.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stats = RunStats()

    with out_path.open("w", encoding="utf-8") as dst:
        for row in rows:
            artifact, was_written = await generate_summary_for_row(corpus=corpus, row=row, provider_name=provider_name, force=force, provider=provider)
            pid = row["paper_id"]
            if was_written:
                stats.provider_calls += 1
                stats.written += 1
                dst.write(json.dumps({"paper_id": pid, "status": "written"}, ensure_ascii=False) + "\n")
            else:
                stats.skipped_existing += 1
                dst.write(json.dumps({"paper_id": pid, "status": "skipped_existing"}, ensure_ascii=False) + "\n")
    return out_path, stats


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", required=True)
    p.add_argument("--provider", choices=["mock", "agent-framework"], default="mock")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--force", action="store_true")
    a = p.parse_args()
    out, stats = asyncio.run(generate_summaries(a.corpus, a.provider, a.limit, a.force))
    print(f"outputs: {out}")
    print(f"written: {stats.written}")
    print(f"skipped_existing: {stats.skipped_existing}")
    print(f"provider_calls: {stats.provider_calls}")


if __name__ == "__main__":
    main()
