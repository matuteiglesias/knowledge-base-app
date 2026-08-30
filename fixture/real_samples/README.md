# Real-world Paper KB fixtures

Small, intentionally bounded real inputs for parser, identity, writer,
corpus, and cross-repository integration tests.

- `raw/` contains redistributable source samples only.
- `expected/` contains exact producer outputs associated with those inputs,
  where historical outputs are available.

These files are test fixtures, not a representative research corpus.

Do not add private papers, bulk corpora, Chroma state, embedding caches,
SQLite databases, logs, or generated development state here.
