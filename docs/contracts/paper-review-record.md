# `paper.review-record@1`

Status: **producer-owned candidate contract (P1)**  
Owner: `paper-kb` paper review-projection component  
Machine schema: `contracts/paper.review_record.v1.schema.json`

## Purpose

`paper.review-record@1` is a bounded paper-domain projection suitable for review/browse consumers. It is deliberately smaller than a `chunk_set`: a review surface needs stable paper identity and descriptive metadata, not the full parsed paper corpus.

It is also deliberately independent of Abstract Scroller snapshot fields. A consumer may map `paper_uid` to its own `doc_id` or node identity, but those consumer-specific names do not belong in this producer-owned contract.

## Required fields

- `schema_id = "paper.review-record"`
- `schema_version = 1`
- `paper_uid`: canonical Paper KB identity
- `title`: human-facing paper title

Optional descriptive fields include `paper_id`, `abstract`, `date`, `year`, `venue`, DOI/arXiv/RePEc identifiers, tags, badges and `source_url`.

## Identity

`paper_uid` is authoritative for this contract. `paper_id` is retained only as a useful source/legacy identifier when available.

The current chunk-set writer already preserves `paper_uid`; therefore the corpus artifact can support this projection without changing canonical parsing semantics. The current paper-level `ChunkSetStorageAdapter` does not yet preserve every review field, including explicit `paper_uid`, so P2 must not blindly use that read model until the gap is repaired.

## Authority boundary

Paper KB owns the meaning of paper fields in this schema because they are paper-domain semantics. `kb-contracts` may later register/pin the producer-owned schema for interoperability without copying or redefining it.

Abstract Scroller or another review consumer owns its own snapshot/tile representation and must adapt from this contract rather than making Paper KB emit consumer-specific fields.

## P1 vs P2

P1 provides:
- schema;
- valid and invalid sanitized fixtures;
- dependency-free validation helper;
- proof that the current chunk-set writer preserves enough canonical paper information to construct a conforming record.

P1 does **not** make `paper.review-record` a canonical generated output.

P2 should add deterministic JSONL emission and preserve the schema identity exactly. CSV may remain as a legacy/convenience export during migration.
