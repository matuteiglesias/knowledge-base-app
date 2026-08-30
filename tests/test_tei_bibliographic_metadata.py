from pipeline.parsers.tei_parser import parse_tei_text
from pipeline.identity import make_paper_uid

TEI = """<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt><title>Metadata Proof</title></titleStmt><publicationStmt><date when="2024-01-04"/></publicationStmt><sourceDesc><biblStruct><analytic><author><persName><forename>Ada</forename><surname>Lovelace</surname></persName></author><idno type="arXiv">arXiv:2401.02013v1[cs.LG]</idno></analytic></biblStruct></sourceDesc></fileDesc><profileDesc><abstract><p>A structured abstract.</p></abstract><textClass><keywords><term>tabular learning</term></keywords></textClass></profileDesc></teiHeader><text><body><div><head>Intro</head><p>Long enough paragraph content for a parser test that exercises one canonical body chunk.</p></div></body></text></TEI>"""

def test_parser_preserves_grobid_bibliographic_metadata():
    parsed = parse_tei_text(TEI)
    assert parsed["title"] == "Metadata Proof"
    assert parsed["authors"] == ["Ada Lovelace"]
    assert parsed["arxiv_id"] == "2401.02013"
    assert parsed["date"] == "2024-01-04"
    assert parsed["year"] == 2024
    assert parsed["abstract"] == "A structured abstract."
    assert parsed["keywords"] == ["tabular learning"]

def test_arxiv_identity_is_stable_across_source_filenames():
    left = make_paper_uid(arxiv_id="2401.02013", source_file="first.tei.xml", title="Metadata Proof")
    right = make_paper_uid(arxiv_id="2401.02013", source_file="renamed.tei.xml", title="Metadata Proof")
    assert left == right
