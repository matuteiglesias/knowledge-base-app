from __future__ import annotations

from pathlib import Path
import sys
import types

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

if "lxml" not in sys.modules:
    fake_lxml = types.ModuleType("lxml")
    fake_lxml.etree = types.SimpleNamespace()
    sys.modules["lxml"] = fake_lxml

from pipeline.corpus import resolve_corpus_paths
from pipeline.adapter import manager


def test_resolve_corpus_paths_layout_and_dirs(tmp_path: Path):
    paths = resolve_corpus_paths("eric_mvukiyehe", repo_root=tmp_path)
    assert paths.root == tmp_path / "corpora" / "eric_mvukiyehe"
    assert paths.pdfs == paths.root / "pdfs"
    assert paths.xmls == paths.root / "xmls"
    assert paths.chunks == paths.root / "chunks"
    assert paths.chunk_sets == paths.root / "chunk_sets"
    assert paths.review == paths.root / "review"

    paths.ensure_dirs()
    for d in (paths.root, paths.pdfs, paths.xmls, paths.chunks, paths.chunk_sets, paths.review):
        assert d.exists()
        assert d.is_dir()


def test_manager_runtime_paths_prefers_explicit_over_corpus(tmp_path: Path):
    explicit_xmls = tmp_path / "x" / "xmls"
    explicit_chunks = tmp_path / "x" / "chunks"
    runtime = manager._resolve_runtime_paths(
        corpus="eric_mvukiyehe",
        pdf_dir=None,
        tei_dir=explicit_xmls,
        chunks_dir=explicit_chunks,
        chunk_set_dir=None,
    )
    assert runtime["tei_dir"] == explicit_xmls.resolve()
    assert runtime["chunks_dir"] == explicit_chunks.resolve()
    assert runtime["chunk_set_dir"].name == "chunk_sets"


def test_manager_runtime_paths_uses_corpus_defaults_when_not_explicit():
    runtime = manager._resolve_runtime_paths(
        corpus="eric_mvukiyehe",
        pdf_dir=None,
        tei_dir=None,
        chunks_dir=None,
        chunk_set_dir=None,
    )
    assert runtime["pdf_dir"] is not None
    assert runtime["tei_dir"] is not None
    assert runtime["chunks_dir"] is not None
    assert runtime["chunk_set_dir"] is not None
    assert str(runtime["pdf_dir"]).endswith("corpora/eric_mvukiyehe/pdfs")
    assert str(runtime["tei_dir"]).endswith("corpora/eric_mvukiyehe/xmls")
    assert str(runtime["chunks_dir"]).endswith("corpora/eric_mvukiyehe/chunks")
    assert str(runtime["chunk_set_dir"]).endswith("corpora/eric_mvukiyehe/chunk_sets")
