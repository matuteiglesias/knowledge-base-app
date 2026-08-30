# Corpus fixtures

Paper KB keeps local governed corpora under `corpora/<name>/`. Those working corpora are ignored by Git by default because they can contain copyrighted PDFs, TEI full text, chunk text, and bulky generated state.

For durable downstream-product tests, a local corpus may instead be promoted into a deliberately bounded fixture under `fixture/corpora/<name>/`.

Two fixture levels are supported:

- `metadata` (default): exact source-PDF inventory by filename/size/SHA-256 plus catalog and review records. This is suitable for bibliography/navigation/review consumers and is the safest public-repository default.
- `consumer`: everything in `metadata` plus canonical `chunk_set` artifacts. `chunk_set` files can contain substantial source text, so this level requires an explicit `ALLOW_TEXT_DERIVATIVES=1` operator acknowledgement and should only be committed when redistribution is permitted.

The promotion intentionally does **not** copy PDFs, TEI XML, legacy chunks, caches, databases or runtime logs. Parser/GROBID reproducibility is already covered by the small `fixture/real_samples` lane; corpus fixtures exist to exercise downstream consumers over realistic corpus shape and metadata.

Examples:

```bash
make corpus-fixture CORPUS=tesis-cited
make corpus-fixture CORPUS=eric-mv

# Only for corpora whose text derivatives are safe to publish:
make corpus-fixture CORPUS=tesis-cited FIXTURE_LEVEL=consumer ALLOW_TEXT_DERIVATIVES=1
```

Each promoted fixture gets `fixture-manifest.json` with source PDF hashes, copied artifact hashes, counts, and the selected fixture level. Absolute local paths are never recorded.

A corpus does not need to have been created by the newer intake command to be promoted: the fixture builder independently inventories the existing local `corpora/<name>/pdfs/` directory. This lets older but already-built corpora be adopted without rewriting their source bytes.
