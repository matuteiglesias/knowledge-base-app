# Review projection ownership

This package is the Paper KB **paper-domain projection layer**.

It may consume governed corpus artifacts and producer-owned paper contracts. It must remain independent of:

- `backend.app` runtime/read-service state;
- FastAPI and frontend concerns;
- Chroma or embedding stores;
- LLM/summarization implementations;
- Abstract Scroller or any other consumer-specific identity/snapshot semantics.

`review_records.py` is the canonical `chunk_set -> paper.review-record@1` projection.

Compatibility formats may remain elsewhere while they are explicitly classified as legacy. New machine review semantics belong here only when they are producer-owned paper-domain semantics.
