# Paper projection ownership

This package is the Paper KB **paper-domain projection layer**.

It may consume governed corpus artifacts and producer-owned paper contracts. It must remain independent of:

- `backend.app` runtime/read-service state;
- FastAPI and frontend concerns;
- Chroma or embedding stores;
- LLM/summarization implementations;
- Abstract Scroller, Knowledge Experiences or any other consumer-specific identity/UI semantics.

Canonical projections currently owned here:

- `review_records.py`: `chunk_set -> paper.review-record@1` for bounded review consumers;
- `catalog_records.py`: `chunk_set -> paper.catalog-record@1` for bibliography/catalog consumers.

These are sibling projections of the governed paper corpus. Neither is an export of backend runtime state and neither should absorb consumer-specific fields.

Compatibility formats may remain elsewhere while explicitly classified as legacy.
