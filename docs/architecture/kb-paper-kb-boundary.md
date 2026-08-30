# KB Boundary with paper-kb

## KB owns

- `chunk_set.v1` contract definition and evolution
- contract validation tooling and checks
- run record and manifest conventions
- generic embedding/vectorstore processing direction

## paper-kb owns

- paper source acquisition and TEI/GROBID adapter logic
- paper metadata extraction and curation
- paper API surface
- paper frontend
- temporary legacy stores during migration

## Dependency direction

- KB **must not** import `paper-kb`.
- `paper-kb` **may** consume KB contracts and lightweight KB validation helpers.

## Transitional compatibility outputs

The following remain compatibility outputs and are not the preferred integration surface:

- `store/chunks/*.jsonl`
- `store/chroma`
- `store/chroma_fallback`

## Preferred integration surface

Downstream integrations should prefer canonical chunk-set artifacts and related run metadata over Chroma-shaped or legacy `store/chunks` paths.
