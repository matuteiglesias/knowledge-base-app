from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.projections.review_records import (
    ReviewProjectionError,
    build_review_records,
    export_review_records,
    review_record_from_chunk_set,
)
from pipeline.writers.chunk_set_writer import write_chunk_set_artifact


class ReviewRecordProjectionTest(unittest.TestCase):
    def _write_artifact(self, root: Path, *, run_id: str, paper_uid: str | None, title: str) -> Path:
        paper_meta = {
            "paper_id": paper_uid or "legacy-paper",
            "title": title,
            "abstract": f"Abstract for {title}",
            "year": "2026",
            "venue": "Synthetic Venue",
            "tags": ["synthetic"],
            "badges": ["review-ready"],
        }
        if paper_uid is not None:
            paper_meta["paper_uid"] = paper_uid
        return write_chunk_set_artifact(
            [
                {
                    "chunk_id": f"{run_id}-chunk-1",
                    "paper_id": paper_uid or "legacy-paper",
                    "paper_uid": paper_uid,
                    "text": "Synthetic chunk content.",
                    "chunk_index": 0,
                    "metadata": {},
                }
            ],
            source_items=[f"{run_id}.tei.xml"],
            run_id=run_id,
            out_dir=root,
            paper_meta=paper_meta,
        )

    def test_projection_is_deterministic_and_contract_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_artifact(root, run_id="z-run", paper_uid="paper_z", title="Zeta")
            self._write_artifact(root, run_id="a-run", paper_uid="paper_a", title="Alpha")

            records = build_review_records(root.glob("*.chunk_set.json"))
            self.assertEqual([row["paper_uid"] for row in records], ["paper_a", "paper_z"])
            self.assertEqual(records[0]["year"], 2026)
            self.assertEqual(records[0]["tags"], ["synthetic"])
            self.assertNotIn("doc_id", records[0])
            self.assertNotIn("node_id", records[0])

            out = root / "review" / "paper.review-record.v1.jsonl"
            summary = export_review_records(chunk_set_dir=root, out_path=out)
            self.assertEqual(summary["records"], 2)
            self.assertTrue(summary["sha256"])
            rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["paper_uid"] for row in rows], ["paper_a", "paper_z"])

    def test_missing_canonical_uid_fails_closed(self) -> None:
        payload = {
            "artifact_family": "chunk_bus",
            "artifact_kind": "chunk_set",
            "paper_meta": {"paper_id": "legacy", "title": "Legacy title"},
            "chunks": [],
        }
        with self.assertRaisesRegex(ReviewProjectionError, "paper_meta.paper_uid is required"):
            review_record_from_chunk_set(payload, source_name="legacy.chunk_set.json")

    def test_duplicate_paper_uid_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._write_artifact(root, run_id="run-1", paper_uid="paper_same", title="First")
            second = self._write_artifact(root, run_id="run-2", paper_uid="paper_same", title="Second")
            with self.assertRaisesRegex(ReviewProjectionError, "duplicate paper_uid"):
                build_review_records([first, second])


if __name__ == "__main__":
    unittest.main()
