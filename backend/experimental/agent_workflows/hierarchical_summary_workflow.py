from __future__ import annotations

"""Experimental functional-workflow wrapper for hierarchical summarization.

IMPORTANT:
- This module is optional and is NOT used by production summary generation.
- Production path remains backend.exports.generate_summaries orchestration.
- Microsoft Agent Framework Functional Workflow API is documented as experimental.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from backend.exports.generate_summaries import _build_row_for_paper, _group_chunks
from backend.llm.base import SummaryInput
from pipeline.corpus import resolve_corpus_paths


def _load_workflow_symbols():
    """Lazy-load Agent Framework workflow decorators.

    Raises RuntimeError with clear install guidance when package is unavailable.
    """
    try:
        from agent_framework import step, workflow  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Experimental workflow requires agent_framework. Install optional deps, e.g. "
            "pip install agent-framework agent-framework-openai"
        ) from exc
    return workflow, step


async def run_hierarchical_summary_workflow_for_paper(
    *,
    corpus: str,
    paper_id: str,
    provider: Any,
    max_group_chars: int = 6000,
) -> dict[str, Any]:
    """Run one-paper experimental functional workflow and return intermediate+final payload.

    Does not write final production summary artifacts; intended for manual experimentation.
    """
    row = _build_row_for_paper(corpus=corpus, paper_id=paper_id)

    paths = resolve_corpus_paths(corpus).ensure_dirs()
    # pull chunks via same source as production code
    from backend.app.storage_adapter import ChunkSetStorageAdapter

    storage = ChunkSetStorageAdapter(chunk_sets_dir=str(paths.chunk_sets))
    storage.load_caches()
    all_chunks = storage.list_chunks(paper_id, limit=1000000).get("chunks", [])
    groups = _group_chunks(all_chunks, max_group_chars=max_group_chars)

    workflow, step = _load_workflow_symbols()

    @step
    async def summarize_group(group: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "Summarize this section of a paper for a thesis literature review. Return JSON only with keys: "
            "summary, method, data, limitations, relevance_to_thesis, warnings.\n"
            f"paper_id={paper_id}\nsection={group['group_label']}\nContext:\n{group['text']}"
        )
        payload = await provider.summarize(
            SummaryInput(
                paper_id=paper_id,
                prompt=prompt,
                context={"group_id": group["group_id"], "group_label": group["group_label"]},
            )
        )
        return {
            "group_id": group["group_id"],
            "group_label": group["group_label"],
            "chunk_ids": group["chunk_ids"],
            "payload": payload,
        }

    @step
    async def synthesize(section_records: list[dict[str, Any]]) -> dict[str, Any]:
        context = "\n".join(
            f"[{i}] section={r.get('group_label','')} summary={str((r.get('payload') or {}).get('one_line') or (r.get('payload') or {}).get('summary') or '')}"
            for i, r in enumerate(section_records, 1)
        )[:12000]
        prompt = (
            "Synthesize a single paper summary from section summaries. Return JSON only with keys: "
            "one_line,research_question,data,method,main_contribution,limitations,relevance_to_thesis,suggested_tags,confidence,warnings.\n"
            f"paper_id={paper_id}\ntitle={row.get('title','')}\nSections:\n{context}"
        )
        return await provider.summarize(SummaryInput(paper_id=paper_id, prompt=prompt, context={"n_sections": len(section_records)}))

    @workflow
    async def paper_summary_flow() -> dict[str, Any]:
        section_records: list[dict[str, Any]] = []
        for g in groups:
            section_records.append(await summarize_group(g))
        final_payload = await synthesize(section_records)
        return {"paper_id": paper_id, "title": row.get("title"), "sections": section_records, "final_payload": final_payload}

    return await paper_summary_flow()


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Experimental Agent Framework functional workflow wrapper")
    p.add_argument("--corpus", required=True)
    p.add_argument("--paper-id", required=True)
    p.add_argument("--provider", choices=["mock", "agent-framework"], default="mock")
    p.add_argument("--out", default=None, help="Optional output JSON path")
    a = p.parse_args()

    if a.provider == "mock":
        from backend.llm.mock_provider import MockSummaryProvider

        provider = MockSummaryProvider()
    else:
        from backend.llm.agent_framework_provider import AgentFrameworkSummaryProvider

        provider = AgentFrameworkSummaryProvider()

    result = asyncio.run(
        run_hierarchical_summary_workflow_for_paper(corpus=a.corpus, paper_id=a.paper_id, provider=provider)
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if a.out:
        out_path = Path(a.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(f"wrote: {out_path}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
