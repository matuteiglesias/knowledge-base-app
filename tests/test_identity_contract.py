from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pipeline.identity import make_paper_uid, normalize_source_ref, normalize_title, safe_artifact_key


def test_make_paper_uid_prefers_source_file_and_is_short():
    uid = make_paper_uid(source_file="Deep Contrastive Learning.tei.xml", title="A title")
    assert uid.startswith("paper_")
    assert len(uid) == len("paper_") + 10


def test_normalizers_and_artifact_key():
    assert normalize_title("  Hello   World ") == "hello world"
    assert normalize_source_ref("/tmp/My File.TEI.XML") == "my file.tei.xml"
    assert safe_artifact_key("paper_AA--11") == "paper_aa_11"
