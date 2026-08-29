from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipeline.contracts.review_record import (
    ReviewRecordValidationError,
    load_review_record_schema,
    validate_review_record_dict,
)
from pipeline.identity import make_paper_uid
from pipeline.writers.chunk_set_writer import write_chunk_set_artifact

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "contracts"


class ReviewRecordContractTest(unittest.TestCase):
    def test_valid_fixture(self) -> None:
        payload = json.loads((FIXTURES / "paper.review_record.v1.valid.json").read_text(encoding="utf-8"))
        validate_review_record_dict(payload)

    def test_invalid_fixture(self) -> None:
        payload = json.loads((FIXTURES / "paper.review_record.v1.invalid.json").read_text(encoding="utf-8"))
        with self.assertRaises(ReviewRecordValidationError):
            validate_review_record_dict(payload)

    def test_contract_is_paper_domain_not_scroller_domain(self) -> None:
        schema = load_review_record_schema()
        properties = set(schema["properties"])
        self.assertIn("paper_uid", properties)
        self.assertNotIn("doc_id", properties)
        self.assertNotIn("node_id", properties)
        self.assertNotIn("snapshot_id", properties)
        self.assertNotIn("order_index", properties)

    def test_current_chunk_set_writer_preserves_inputs_for_projection(self) -> None:
        paper_uid = make_paper_uid(doi="10.0000/synthetic.projection")
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "chunk_sets"
            artifact_path = write_chunk_set_artifact(
                [
                    {
                        "chunk_id": "chunk-1",
                        "paper_id": "legacy-paper-1",
                        "paper_uid": paper_uid,
                        "text": "Synthetic chunk text.",
                        "chunk_index": 0,
                        "metadata": {},
                    }
                ],
                source_items=["synthetic.tei.xml"],
                run_id="review-contract-proof",
                out_dir=out_dir,
                paper_meta={
                    "paper_uid": paper_uid,
                    "paper_id": "legacy-paper-1",
                    "title": "Synthetic projection proof",
                    "abstract": "Synthetic abstract.",
                    "date": "2026-01-15",
                    "year": 2026,
                    "venue": "Synthetic Review",
                    "doi": "10.0000/synthetic.projection",
                    "source_url": "https://example.invalid/synthetic",
                },
            )
            chunk_set = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(chunk_set["chunks"][0]["paper_uid"], paper_uid)
            meta = chunk_set["paper_meta"]
            candidate = {
                "schema_id": "paper.review-record",
                "schema_version": 1,
                "paper_uid": meta["paper_uid"],
                "paper_id": meta.get("paper_id"),
                "title": meta["title"],
                "abstract": meta.get("abstract"),
                "date": meta.get("date"),
                "year": meta.get("year"),
                "venue": meta.get("venue"),
                "doi": meta.get("doi"),
                "arxiv_id": meta.get("arxiv_id"),
                "repec_id": meta.get("repec_id"),
                "tags": [],
                "badges": [],
                "source_url": meta.get("source_url"),
            }
            validate_review_record_dict(candidate)


if __name__ == "__main__":
    unittest.main()
