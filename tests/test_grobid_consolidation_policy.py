from pathlib import Path
from unittest.mock import Mock, patch
import tempfile

from pipeline.adapter.grobid_ingest import post_pdf_to_grobid

def _response():
    r = Mock(); r.text = '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body/></text></TEI>'; r.raise_for_status = Mock(); return r

def test_grobid_can_disable_external_header_consolidation():
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / "paper.pdf"; pdf.write_bytes(b"%PDF-fixture")
        with patch("pipeline.adapter.grobid_ingest.requests.post", return_value=_response()) as post:
            post_pdf_to_grobid(pdf, consolidate_header=False)
        assert post.call_args.kwargs["data"]["consolidateHeader"] == "0"

def test_grobid_legacy_default_keeps_consolidation_enabled():
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / "paper.pdf"; pdf.write_bytes(b"%PDF-fixture")
        with patch("pipeline.adapter.grobid_ingest.requests.post", return_value=_response()) as post:
            post_pdf_to_grobid(pdf)
        assert post.call_args.kwargs["data"]["consolidateHeader"] == "1"
