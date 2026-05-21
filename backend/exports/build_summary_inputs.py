from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from backend.app.storage_adapter import ChunkSetStorageAdapter
from pipeline.corpus import resolve_corpus_paths

def build_summary_inputs(corpus: str, limit: int | None = None, max_chunks: int = 6, max_chars: int = 6000) -> tuple[Path, int]:
    paths = resolve_corpus_paths(corpus).ensure_dirs()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = paths.root / "summary_runs" / run_id / "inputs" / "paper_summary_inputs.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    storage = ChunkSetStorageAdapter(chunk_sets_dir=str(paths.chunk_sets))
    papers = storage.list_papers()[:limit] if limit is not None else storage.list_papers()
    n = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for paper in papers:
            pid = str(paper.get("paper_id") or "").strip()
            if not pid:
                continue
            all_chunks = storage.list_chunks(pid, limit=1000000).get("chunks", [])
            chunks = all_chunks[:max_chunks]
            context = "\n".join(f"[{i}] {' '.join(str(c.get('text') or '').split())}" for i, c in enumerate(chunks, 1))[:max_chars]
            prompt = f"Summarize the paper as JSON with keys: summary, key_points, limitations.\\npaper_id={pid}\\ntitle={paper.get('title','')}\\nContext:\\n{context}"
            fh.write(json.dumps({"paper_id": pid, "title": paper.get("title"), "prompt": prompt, "context": {"n_chunks_total": len(all_chunks), "n_chunks_selected": len(chunks)}, "selected_chunk_ids": [c.get("chunk_id") for c in chunks if c.get("chunk_id")]}, ensure_ascii=False) + "\n")
            n += 1
    return out_path, n

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", required=True)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--max-chunks", type=int, default=6)
    a = p.parse_args()
    out, n = build_summary_inputs(a.corpus, a.limit, a.max_chunks)
    print(f"wrote {n} rows -> {out}")

if __name__ == "__main__":
    main()
