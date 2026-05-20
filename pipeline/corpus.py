from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CorpusPaths:
    name: str
    root: Path
    pdfs: Path
    xmls: Path
    chunks: Path
    chunk_sets: Path
    review: Path

    def ensure_dirs(self) -> "CorpusPaths":
        for p in (self.root, self.pdfs, self.xmls, self.chunks, self.chunk_sets, self.review):
            p.mkdir(parents=True, exist_ok=True)
        return self



def resolve_corpus_paths(corpus_name: str, repo_root: Path | None = None) -> CorpusPaths:
    name = (corpus_name or "").strip()
    if not name:
        raise ValueError("corpus_name must be non-empty")

    base = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    root = base.expanduser().resolve() / "corpora" / name
    return CorpusPaths(
        name=name,
        root=root,
        pdfs=root / "pdfs",
        xmls=root / "xmls",
        chunks=root / "chunks",
        chunk_sets=root / "chunk_sets",
        review=root / "review",
    )
