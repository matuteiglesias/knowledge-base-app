from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipeline.contracts.catalog_record import (
    CatalogRecordValidationError,
    load_catalog_record_schema,
    validate_catalog_record_dict,
)


class CatalogRecordContractTest(unittest.TestCase):
    def valid_record(self) -> dict:
        return {
            "schema_id": "paper.catalog-record",
            "schema_version": 1,
            "paper_uid": "paper:test",
            "paper_id": "legacy-test",
            "title": "A governed paper",
            "authors": ["Ada Example", "Ben Builder"],
            "abstract": "Short sanitized abstract.",
            "date": "2026-08-29",
            "year": 2026,
            "venue": "Example Working Papers",
            "doi": None,
            "arxiv_id": None,
            "repec_id": None,
            "tags": ["example"],
            "source_url": "https://example.org/paper",
        }

    def test_schema_identity_and_closed_shape(self) -> None:
        schema = load_catalog_record_schema()
        self.assertEqual(schema["$id"], "paper.catalog-record@1")
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("authors", schema["required"])

    def test_valid_record(self) -> None:
        validate_catalog_record_dict(self.valid_record())

    def test_authors_must_be_string_array(self) -> None:
        record = self.valid_record()
        record["authors"] = [{"name": "Ada"}]
        with self.assertRaises(CatalogRecordValidationError):
            validate_catalog_record_dict(record)

    def test_unknown_fields_fail_closed(self) -> None:
        record = self.valid_record()
        record["consumer_card_color"] = "blue"
        with self.assertRaises(CatalogRecordValidationError):
            validate_catalog_record_dict(record)


if __name__ == "__main__":
    unittest.main()
