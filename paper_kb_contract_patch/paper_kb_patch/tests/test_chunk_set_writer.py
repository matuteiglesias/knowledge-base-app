from pathlib import Path
import json

from pipeline.writers.chunk_set_writer import write_chunk_set_artifact


def test_write_chunk_set_artifact_schema(tmp_path: Path):
    path = write_chunk_set_artifact(
        [
            {
                "chunk_id": "p1::c1",
                "paper_id": "p1",
                "section_title": "Intro",
                "text": "hello world",
                "meta": {"source_file": "paper.tei.xml"},
            }
        ],
        source_items=["paper.tei.xml"],
        run_id="test_run",
        out_dir=tmp_path,
    )
    obj = json.loads(path.read_text(encoding="utf-8"))
    assert obj["artifact_family"] == "chunk_bus"
    assert obj["artifact_kind"] == "chunk_set"
    assert obj["producer"] == "paper-kb"
    assert obj["entrypoint"] == "paper_tei_parse"
    assert obj["chunk_count"] == 1
    assert obj["chunks"][0]["chunk_id"] == "p1::c1"
