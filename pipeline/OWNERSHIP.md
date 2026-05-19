# paper-kb pipeline ownership map

This repo is the paper-specific application/tooling layer. It should not duplicate
KB-core ownership where a reusable contract already exists.

## Fixed roles

| Area | Role | Owner | Canonical output |
|---|---|---|---|
| `pipeline/sources/` | source adapters | `paper-kb` | downloaded source files / metadata, not a bus artifact yet |
| `pipeline/adapter/grobid_ingest.py` | external parser adapter | `paper-kb` | TEI XML, transitional adapter output |
| `pipeline/parsers/tei_parser.py` | TEI/GROBID format parser | `paper-kb` | raw TEI-derived chunks |
| `pipeline/parsers/canonicalize.py` | bridge from TEI chunks to backend `CanonicalChunk` | `paper-kb` for now | backend-compatible CanonicalChunk records |
| `pipeline/producer/tei_runner.py` | Chunk Bus producer plus legacy backend writer | `paper-kb` | `artifacts/chunk_sets/*.chunk_set.json` |
| `pipeline/producer/embed_runner.py` | internal Chroma materializer | `paper-kb`, using `kb.embedding` | no public contract output |
| `kb.embedding.*` | reusable embedding runtime | `KB/kb` | reusable embedding API, not paper-specific |

## Contract rule

The canonical public output of paper parsing is the chunk-set artifact:

```text
artifacts/chunk_sets/<run_id>.chunk_set.json
```

Legacy outputs remain for backend compatibility:

```text
store/chunks/*_chunks.jsonl
store/chunks/.done/*.json
backend paper metadata files
Chroma collections
embedding cache
```

Those are internal or legacy side effects. Downstream consumers should prefer
chunk-set artifacts over Chroma or backend filesystem internals.

## Current non-goals

- Do not move backend schemas.
- Do not rewrite `canonicalize.py` yet.
- Do not remove `store/chunks` while backend depends on it.
- Do not promote `embed_runner.py` to public producer.
- Do not treat GROBID as a full bus-native producer yet.
