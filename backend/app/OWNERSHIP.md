# Paper read-service ownership

`backend/app` is the repository-local **read/query service** over governed paper artifacts.

Owns:
- runtime storage adapters and read models;
- HTTP/API behavior and diagnostics;
- compatibility behavior required by the Paper Workbench.

Does not own:
- source acquisition or parsing;
- canonical `paper_uid` semantics independently from the corpus core;
- `paper.review-record@1` projection semantics;
- snapshot publication;
- general knowledge inspection.

The read service should preserve canonical corpus identity and metadata. P5 makes `paper_uid` explicit in the paper-level read/API model while retaining `paper_id` for compatibility.
