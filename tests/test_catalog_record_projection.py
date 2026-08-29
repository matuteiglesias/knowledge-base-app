from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipeline.corpus import resolve_corpus_paths
from pipeline.projections.catalog_records import (
    CatalogProjectionError,
    build_catalog_records,
    catalog_record_from_chunk_set,
    export_catalog_records,
)
from pipeline.writers.chunk_set_writer import write_chunk_set_artifact


class CatalogRecordProjectionTest(unittest.TestCase):
    def _write_artifact(self, root: Path, *, run_id: str, paper_uid: str | None, title: str, authors=None) -> Path:
        paper_meta = {
            "paper_id": paper_uid or "legacy-paper",
            "title": title,
            "authors": ["Ada Example"] if authors is None else authors,
            "abstract": f"Sanitized abstract for {title}",
            "year": "2026",
            "venue": "Example Working Papers",
            "tags": ["catalog"],
        }
        if paper_uid is not None:
            paper_meta["paper_uid"] = paper_uid
        return write_chunk_set_artifact(
            [{"chunk_id": f"{run_id}-chunk", "paper_id": paper_uid or "legacy", "paper_uid": paper_uid, "text": "Synthetic chunk.", "chunk_index": 0, "metadata": {}}],
            source_items=[f"{run_id}.tei.xml"],
            run_id=run_id,
            out_dir=root,
            paper_meta=paper_meta,
        )

    def test_projection_preserves_authors_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_artifact(root, run_id="z-run", paper_uid="paper_z", title="Zeta", authors=["Z. Author"])
            self._write_artifact(root, run_id="a-run", paper_uid="paper_a", title="Alpha", authors=["Ada Example", "Ben Builder"])
            records = build_catalog_records(root.glob("*.chunk_set.json"))
            self.assertEqual([row["paper_uid"] for row in records], ["paper_a", "paper_z"])
            self.assertEqual(records[0]["authors"], ["Ada Example", "Ben Builder"])
            self.assertEqual(records[0]["year"], 2026)
            self.assertEqual(records[0]["venue"], "Example Working Papers")
            self.assertNotIn("doc_id", records[0])

            out = root / "catalog" / "paper.catalog-record.v1.jsonl"
            summary = export_catalog_records(chunk_set_dir=root, out_path=out)
            self.assertEqual(summary["records"], 2)
            rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows, records)

    def test_missing_uid_fails_closed(self) -> None:
        payload = {"artifact_family": "chunk_bus", "artifact_kind": "chunk_set", "paper_meta": {"title": "Legacy", "authors": []}, "chunks": []}
        with self.assertRaisesRegex(CatalogProjectionError, "paper_meta.paper_uid is required"):
            catalog_record_from_chunk_set(payload, source_name="legacy.chunk_set.json")

    def test_malformed_authors_fail_closed_without_inference(self) -> None:
        payload = {"artifact_family": "chunk_bus", "artifact_kind": "chunk_set", "paper_meta": {"paper_uid": "paper:x", "title": "X", "authors": "Ada Example"}, "chunks": []}
        with self.assertRaisesRegex(CatalogProjectionError, "authors must be an array"):
            catalog_record_from_chunk_set(payload)

    def test_duplicate_uid_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._write_artifact(root, run_id="run-1", paper_uid="paper_same", title="First")
            second = self._write_artifact(root, run_id="run-2", paper_uid="paper_same", title="Second")
            with self.assertRaisesRegex(CatalogProjectionError, "duplicate paper_uid"):
                build_catalog_records([first, second])

    def test_named_corpus_has_catalog_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = resolve_corpus_paths("demo", repo_root=Path(tmp))
            self.assertEqual(paths.catalog, paths.root / "catalog")
            paths.ensure_dirs()
            self.assertTrue(paths.catalog.is_dir())


if __name__ == "__main__":
    unittest.main()
