from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.storage_adapter import ChunkSetStorageAdapter
from backend.exports.build_summary_inputs import build_summary_inputs
from backend.exports.summary_artifacts import build_summary_artifact, safe_paper_id, summary_path, write_json_atomic
from backend.llm.agent_framework_provider import AgentFrameworkSummaryProvider
from backend.llm.base import SummaryInput
from backend.llm.mock_provider import MockSummaryProvider
from pipeline.corpus import resolve_corpus_paths


def _provider(name: str, model: str | None = None, env_file_path: str | None = None):
    if name == "mock":
        return MockSummaryProvider()
    if name == "agent-framework":
        return AgentFrameworkSummaryProvider(model=model, env_file_path=env_file_path)
    raise ValueError(f"unknown provider: {name}")


@dataclass
class RunStats:
    written: int = 0
    skipped_existing: int = 0
    provider_calls: int = 0
    n_section_calls: int = 0
    n_synthesis_calls: int = 0


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


def _group_chunks(all_chunks: list[dict[str, Any]], window_size: int = 10, max_group_chars: int = 6000) -> list[dict[str, Any]]:
    if not all_chunks:
        return []

    with_header = [c for c in all_chunks if isinstance(c.get("header_path"), list) and c.get("header_path")]
    groups: list[dict[str, Any]] = []

    if with_header:
        bucket: dict[str, list[dict[str, Any]]] = {}
        for c in all_chunks:
            hp = c.get("header_path")
            key = str(hp[0]).strip() if isinstance(hp, list) and hp else "unknown"
            bucket.setdefault(key, []).append(c)
        items = list(bucket.items())
    else:
        sorted_chunks = sorted(all_chunks, key=lambda c: int(c.get("chunk_index") or 0))
        items = []
        for i in range(0, len(sorted_chunks), window_size):
            slice_chunks = sorted_chunks[i:i + window_size]
            first = int(slice_chunks[0].get("chunk_index") or 0)
            last = int(slice_chunks[-1].get("chunk_index") or first)
            items.append((f"chunks_{first:04d}_{last:04d}", slice_chunks))

    for idx, (label, chunks) in enumerate(items, 1):
        text = "\n".join(" ".join(str(c.get("text") or "").split()) for c in chunks)[:max_group_chars]
        groups.append({
            "group_id": f"group_{idx:04d}",
            "group_label": label,
            "chunk_ids": [str(c.get("chunk_id")) for c in chunks if c.get("chunk_id")],
            "text": text,
        })
    return groups


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


async def generate_summary_for_row_hierarchical(corpus: str, row: dict[str, Any], provider_name: str, run_id: str, force: bool = False, provider: Any | None = None) -> tuple[dict[str, Any], bool, int, int]:
    provider = provider or _provider(provider_name)
    paths = resolve_corpus_paths(corpus).ensure_dirs()
    summaries_dir = paths.root / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    pid = row["paper_id"]
    target = summary_path(summaries_dir, pid)
    if target.exists() and not force:
        return json.loads(target.read_text(encoding="utf-8")), False, 0, 0

    storage = ChunkSetStorageAdapter(chunk_sets_dir=str(paths.chunk_sets))
    storage.load_caches()
    all_chunks = storage.list_chunks(pid, limit=1000000).get("chunks", [])
    groups = _group_chunks(all_chunks)

    inter_path = paths.root / "summary_runs" / run_id / "intermediate" / f"{safe_paper_id(pid)}.section_summaries.jsonl"
    inter_path.parent.mkdir(parents=True, exist_ok=True)

    section_records: list[dict[str, Any]] = []
    n_section_calls = 0
    if inter_path.exists() and not force:
        section_records = [json.loads(ln) for ln in inter_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    if not section_records:
        for g in groups:
            section_prompt = (
                "Summarize this section of a paper for a thesis literature review. Return JSON only with keys: "
                "summary, method, data, limitations, relevance_to_thesis, warnings.\n"
                f"paper_id={pid}\nsection={g['group_label']}\nContext:\n{g['text']}"
            )
            payload = await _execute_provider(provider, {
                "paper_id": pid,
                "prompt": section_prompt,
                "context": {"group_id": g["group_id"], "group_label": g["group_label"], "chunk_ids": g["chunk_ids"]},
            })
            section_records.append({
                "paper_id": pid,
                "group_id": g["group_id"],
                "group_label": g["group_label"],
                "chunk_ids": g["chunk_ids"],
                "payload": payload,
            })
            n_section_calls += 1
        with inter_path.open("w", encoding="utf-8") as fh:
            for rec in section_records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    synthesis_context = "\n".join(
        f"[{i}] section={r.get('group_label','')} summary={str((r.get('payload') or {}).get('one_line') or (r.get('payload') or {}).get('summary') or '')}"
        for i, r in enumerate(section_records, 1)
    )[:12000]
    synthesis_prompt = (
        "Synthesize a single paper summary from section summaries. Return JSON only with keys: "
        "one_line,research_question,data,method,main_contribution,limitations,relevance_to_thesis,suggested_tags,confidence,warnings.\n"
        f"paper_id={pid}\ntitle={row.get('title','')}\nSections:\n{synthesis_context}"
    )
    final_payload = await _execute_provider(provider, {"paper_id": pid, "prompt": synthesis_prompt, "context": {"n_sections": len(section_records)}})
    n_synthesis_calls = 1

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
        payload=final_payload,
    )
    write_json_atomic(target, artifact)
    return artifact, True, n_section_calls, n_synthesis_calls


async def generate_summaries(corpus: str, provider_name: str, limit: int | None = None, force: bool = False, model: str | None = None, env_file_path: str | None = None, mode: str = "direct") -> tuple[Path, RunStats]:
    provider = _provider(provider_name, model=model, env_file_path=env_file_path)
    inputs_path, _ = build_summary_inputs(corpus=corpus, limit=limit)
    rows = _read_input_rows(inputs_path)

    paths = resolve_corpus_paths(corpus).ensure_dirs()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = paths.root / "summary_runs" / run_id / "outputs" / "paper_summary_outputs.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stats = RunStats()

    with out_path.open("w", encoding="utf-8") as dst:
        for row in rows:
            pid = row["paper_id"]
            if mode == "hierarchical":
                artifact, was_written, n_section_calls, n_synthesis_calls = await generate_summary_for_row_hierarchical(
                    corpus=corpus, row=row, provider_name=provider_name, run_id=run_id, force=force, provider=provider
                )
                stats.n_section_calls += n_section_calls
                stats.n_synthesis_calls += n_synthesis_calls
                if was_written:
                    stats.provider_calls += (n_section_calls + n_synthesis_calls)
            else:
                artifact, was_written = await generate_summary_for_row(corpus=corpus, row=row, provider_name=provider_name, force=force, provider=provider)
                if was_written:
                    stats.provider_calls += 1
            if was_written:
                stats.written += 1
                dst.write(json.dumps({"paper_id": pid, "status": "written"}, ensure_ascii=False) + "\n")
            else:
                stats.skipped_existing += 1
                dst.write(json.dumps({"paper_id": pid, "status": "skipped_existing"}, ensure_ascii=False) + "\n")

    run_record = {
        "run_id": run_id,
        "mode": mode,
        "provider": provider_name,
        "n_papers": len(rows),
        "written": stats.written,
        "skipped_existing": stats.skipped_existing,
        "n_section_calls": stats.n_section_calls,
        "n_synthesis_calls": stats.n_synthesis_calls,
        "provider_calls_total": stats.provider_calls,
    }
    write_json_atomic(paths.root / "summary_runs" / run_id / "run_record.json", run_record)
    return out_path, stats


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", required=True)
    p.add_argument("--provider", choices=["mock", "agent-framework"], default="mock")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--model", default=None)
    p.add_argument("--env-file-path", default=None)
    p.add_argument("--mode", choices=["direct", "hierarchical"], default="direct")
    a = p.parse_args()
    out, stats = asyncio.run(generate_summaries(a.corpus, a.provider, a.limit, a.force, model=a.model, env_file_path=a.env_file_path, mode=a.mode))
    print(f"outputs: {out}")
    print(f"written: {stats.written}")
    print(f"skipped_existing: {stats.skipped_existing}")
    print(f"provider_calls: {stats.provider_calls}")
    print(f"n_section_calls: {stats.n_section_calls}")
    print(f"n_synthesis_calls: {stats.n_synthesis_calls}")


if __name__ == "__main__":
    main()
