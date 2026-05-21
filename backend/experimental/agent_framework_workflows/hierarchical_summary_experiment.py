from __future__ import annotations

"""Experimental Agent Framework workflow for one-paper hierarchical summarization.

IMPORTANT:
- Experimental only; not imported by normal API startup.
- Production path remains backend.exports.generate_summaries.
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.storage_adapter import ChunkSetStorageAdapter
from backend.exports.generate_summaries import _build_row_for_paper, _group_chunks, _validate_summary_payload
from backend.exports.summary_artifacts import safe_paper_id
from backend.llm.base import SummaryInput
from backend.llm.mock_provider import MockSummaryProvider
from pipeline.corpus import resolve_corpus_paths


def _load_workflow_symbols():
    try:
        from agent_framework import step, workflow  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Experimental workflow requires agent_framework. Install with: pip install agent-framework agent-framework-openai"
        ) from exc
    return workflow, step


def _load_provider(provider_name: str, agent_mode: str):
    if provider_name == "mock":
        return MockSummaryProvider()
    if provider_name == "agent-framework":
        from backend.llm.agent_framework_provider import AgentFrameworkSummaryProvider

        return AgentFrameworkSummaryProvider(agent_mode=agent_mode)
    raise ValueError(f"unknown provider: {provider_name}")


async def run_one_paper_experiment(*, corpus: str, paper_id: str, provider: Any) -> dict[str, Any]:
    row = _build_row_for_paper(corpus=corpus, paper_id=paper_id)
    paths = resolve_corpus_paths(corpus).ensure_dirs()
    storage = ChunkSetStorageAdapter(chunk_sets_dir=str(paths.chunk_sets))
    storage.load_caches()
    all_chunks = storage.list_chunks(paper_id, limit=1000000).get("chunks", [])
    groups = _group_chunks(all_chunks, window_size=8, max_group_chars=6000)
    workflow, step = _load_workflow_symbols()

    @step
    async def summarize_group(group: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "Summarize this section of a paper for a thesis literature review. Return JSON only with keys: "
            "one_line,research_question,data,method,main_contribution,limitations,relevance_to_thesis,suggested_tags,confidence,warnings.\n"
            f"paper_id={paper_id}\nsection={group['group_label']}\nContext:\n{group['text']}"
        )
        payload = await provider.summarize(
            SummaryInput(
                paper_id=paper_id,
                prompt=prompt,
                context={"group_id": group["group_id"], "group_label": group["group_label"], "chunk_ids": group["chunk_ids"]},
            )
        )
        payload = _validate_summary_payload(payload, paper_id)
        return {
            "paper_id": paper_id,
            "group_id": group["group_id"],
            "group_label": group["group_label"],
            "chunk_ids": group["chunk_ids"],
            "payload": payload,
        }

    @step
    async def synthesize(section_records: list[dict[str, Any]]) -> dict[str, Any]:
        context = "\n".join(
            f"[{i}] section={r.get('group_label','')} summary={str((r.get('payload') or {}).get('one_line') or '')}"
            for i, r in enumerate(section_records, 1)
        )[:12000]
        prompt = (
            "Synthesize a single paper summary from section summaries. Return JSON only with keys: "
            "one_line,research_question,data,method,main_contribution,limitations,relevance_to_thesis,suggested_tags,confidence,warnings.\n"
            f"paper_id={paper_id}\ntitle={row.get('title','')}\nSections:\n{context}"
        )
        payload = await provider.summarize(SummaryInput(paper_id=paper_id, prompt=prompt, context={"n_sections": len(section_records)}))
        return _validate_summary_payload(payload, paper_id)

    @workflow
    async def run_flow() -> dict[str, Any]:
        section_records: list[dict[str, Any]] = []
        for g in groups:
            section_records.append(await summarize_group(g))
        final_payload = await synthesize(section_records)
        return {
            "paper_id": paper_id,
            "title": row.get("title"),
            "n_groups": len(groups),
            "n_section_calls": len(section_records),
            "n_synthesis_calls": 1,
            "sections": section_records,
            "final_payload": final_payload,
        }

    return await run_flow()


def _write_experimental_outputs(*, corpus: str, result: dict[str, Any], provider_name: str, agent_mode: str) -> Path:
    paths = resolve_corpus_paths(corpus).ensure_dirs()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = paths.root / "experimental_runs" / "agent_framework_workflows" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    paper_id = str(result.get("paper_id") or "unknown")
    out_file = out_dir / f"{safe_paper_id(paper_id)}.workflow_result.json"
    payload = {
        "run_id": run_id,
        "provider": provider_name,
        "agent_mode": agent_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **result,
    }
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_file


def main() -> None:
    p = argparse.ArgumentParser(description="Experimental Agent Framework workflow (one paper)")
    p.add_argument("--corpus", required=True)
    p.add_argument("--paper-id", required=True)
    p.add_argument("--provider", choices=["mock", "agent-framework"], default="mock")
    p.add_argument("--agent-mode", choices=["client", "agent"], default="client")
    a = p.parse_args()

    provider = _load_provider(a.provider, a.agent_mode)
    result = asyncio.run(run_one_paper_experiment(corpus=a.corpus, paper_id=a.paper_id, provider=provider))
    out_file = _write_experimental_outputs(corpus=a.corpus, result=result, provider_name=a.provider, agent_mode=a.agent_mode)
    print(f"wrote experimental workflow output: {out_file}")


if __name__ == "__main__":
    main()

