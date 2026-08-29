from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class ReviewSurfaceGovernanceTest(unittest.TestCase):
    def test_makefile_prefers_review_records_and_marks_csv_compatibility(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("export-review-records:", makefile)
        self.assertIn("export-review-csv:", makefile)
        self.assertIn("[DEPRECATED ALIAS]", makefile)
        self.assertIn("preferred machine interface", makefile.lower())

    def test_review_contract_identity_remains_producer_owned(self) -> None:
        schema = json.loads(
            (REPO_ROOT / "contracts" / "paper.review_record.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        props = schema["properties"]
        self.assertIn("paper_uid", props)
        for consumer_field in ("doc_id", "node_id", "snapshot_id", "order_index"):
            self.assertNotIn(consumer_field, props)

    def test_system_declares_csv_as_compatibility_not_primary_artifact(self) -> None:
        system = (REPO_ROOT / "SYSTEM.yaml").read_text(encoding="utf-8")
        self.assertIn("artifact:paper.review-record@1", system)
        self.assertIn("compatibility:", system)
        self.assertIn("format:review-csv", system)
        self.assertIn("compatibility_commands:", system)


if __name__ == "__main__":
    unittest.main()
