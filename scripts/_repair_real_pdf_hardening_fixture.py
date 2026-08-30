from pathlib import Path

p = Path('tests/test_tei_bibliographic_metadata.py')
text = p.read_text()
old = '<titleStmt><title>Metadata Proof</title><author><persName><forename>Ada</forename><surname>Lovelace</surname></persName></author></titleStmt><publicationStmt><date when="2024-01-04"/></publicationStmt><sourceDesc><biblStruct><analytic><idno type="arXiv">'
new = '<titleStmt><title>Metadata Proof</title></titleStmt><publicationStmt><date when="2024-01-04"/></publicationStmt><sourceDesc><biblStruct><analytic><author><persName><forename>Ada</forename><surname>Lovelace</surname></persName></author><idno type="arXiv">'
if text.count(old) != 1:
    raise SystemExit(f'expected one synthetic TEI author-layout target, got {text.count(old)}')
p.write_text(text.replace(old, new, 1))
