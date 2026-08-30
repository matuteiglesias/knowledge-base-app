from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.schemas import PaperMeta
from backend.app.storage_adapter import ChunkSetStorageAdapter


class ReadModelIdentityTest(unittest.TestCase):
    def test_chunk_set_paper_uid_survives_storage_and_api_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "artifact_family": "chunk_bus",
                "artifact_kind": "chunk_set",
                "schema_version": 1,
                "run_id": "identity-proof",
                "producer": "paper-kb",
                "entrypoint": "paper_tei_parse",
                "source_items": ["paper.xml"],
                "chunk_count": 1,
                "paper_meta": {
                    "paper_uid": "doi:10.0000/p5.identity",
                    "paper_id": "legacy-paper-id",
                    "title": "Identity preservation proof",
                    "authors": ["Synthetic Author"],
                    "source_file": "paper.xml",
                    "abstract": "Governed abstract",
                    "date": "2024-01-04",
                    "year": 2024,
                    "venue": "Example Venue",
                    "arxiv_id": "2401.02013",
                    "tags": ["proof"]
                },
                "chunks": [
                    {
                        "chunk_id": "chunk-1",
                        "paper_uid": "doi:10.0000/p5.identity",
                        "paper_id": "legacy-paper-id",
                        "text": "Synthetic content.",
                        "chunk_index": 0,
                        "char_len": 18,
                        "source_file": "paper.xml",
                        "metadata": {}
                    }
                ]
            }
            (root / "identity.chunk_set.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )

            adapter = ChunkSetStorageAdapter(chunk_sets_dir=str(root))
            papers = adapter.list_papers()
            self.assertEqual(len(papers), 1)
            paper = papers[0]
            self.assertEqual(paper["paper_id"], "legacy-paper-id")
            self.assertEqual(paper["paper_uid"], "doi:10.0000/p5.identity")

            api_model = PaperMeta(**paper)
            self.assertEqual(api_model.paper_id, "legacy-paper-id")
            self.assertEqual(api_model.paper_uid, "doi:10.0000/p5.identity")
            self.assertEqual(api_model.abstract, "Governed abstract")
            self.assertEqual(api_model.year, 2024)
            self.assertEqual(api_model.arxiv_id, "2401.02013")
            self.assertEqual(api_model.tags, ["proof"])

            chunks = adapter.list_chunks("legacy-paper-id")["chunks"]
            self.assertEqual(chunks[0]["paper_uid"], "doi:10.0000/p5.identity")


if __name__ == "__main__":
    unittest.main()
