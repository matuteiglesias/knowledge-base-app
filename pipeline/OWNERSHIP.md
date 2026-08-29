# paper-kb pipeline ownership map

The repository-wide component authority is frozen in [`docs/architecture/paper-kb-component-boundaries.md`](../docs/architecture/paper-kb-component-boundaries.md). This file narrows that architecture to the corpus pipeline.

## Pipeline roles

| Area | Role | Owner | Canonical output |
|---|---|---|---|
| `pipeline/sources/` | source adapters | `paper-kb` source-acquisition component | downloaded source files / metadata; staging only |
| `pipeline/adapter/grobid_ingest.py` | external parser adapter | source-acquisition component | TEI XML; staging output |
| `pipeline/parsers/tei_parser.py` | TEI/GROBID format parser | paper corpus core | raw TEI-derived chunks |
| `pipeline/parsers/canonicalize.py` | paper canonicalization bridge | paper corpus core | backend-compatible canonical chunks |
| `pipeline/identity.py` | stable paper identity | paper corpus core | canonical `paper_uid` |
| `pipeline/producer/tei_runner.py` | Chunk Bus producer plus legacy backend writer | paper corpus core | `*.chunk_set.json` |
| `pipeline/writers/chunk_set_writer.py` | governed chunk-set writer | paper corpus core | `chunk_set@1` artifact |
| `pipeline/producer/embed_runner.py` | internal Chroma materializer | paper-specific internal derivative | no public contract output |

## Contract rule

The canonical public output of paper parsing is the chunk-set artifact. Downstream consumers should prefer chunk-set artifacts over Chroma or backend filesystem internals.

Named corpora resolve under:

```text
corpora/<name>/
  pdfs/
  xmls/
  chunks/
  chunk_sets/
  review/
```

Legacy outputs may remain for backend compatibility but are not corpus authority.

## Review projection boundary

Review/browse output is **not** a parser responsibility. P1 defines the producer-owned paper-domain contract at:

```text
contracts/paper.review_record.v1.schema.json
```

The review projection component may consume canonical corpus artifacts to emit that contract in P2. Consumer-specific snapshot fields do not belong in the pipeline.

## Current non-goals

- no physical repository split;
- no backend schema move;
- no removal of legacy stores while an active compatibility path still depends on them;
- no promotion of Chroma to public corpus authority;
- no review-snapshot or frontend semantics inside the parser pipeline.
