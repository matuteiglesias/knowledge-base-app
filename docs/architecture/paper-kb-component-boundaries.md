# Paper KB component boundaries — P0 architecture freeze

Status: **current reference for repository-internal responsibilities**  
Date: 2026-08-28

`paper-kb` is treated as a **modular monorepo**, not as one undifferentiated application and not yet as a set of repositories to split apart.

The purpose of this freeze is to make independent evolution possible before any physical extraction. Folder names are evidence of implementation location, not authority by themselves.

## Governing rule

The paper corpus is the durable center. Parsing produces governed corpus artifacts. API, summaries, review projections and user interfaces consume or derive from those artifacts; they do not redefine corpus truth.

```text
paper sources
    |
    v
source acquisition / parser adapters
    |
    v
PAPER CORPUS CORE
identity + canonicalization + chunk production
    |
    +----> chunk_set@1 --------------------> Knowledge Inspect
    |
    +----> paper read service ------------> Paper Workbench
    |
    +----> paper-specific derivations
    |
    +----> review projection
                |
                v
        paper.review-record@1
                |
                v
        compatible review consumers
        (Abstract Scroller candidate)
```

## Component map

### 1. Source acquisition and parser adapters

Current implementation includes `pipeline/sources/` and `pipeline/adapter/`, including GROBID integration.

Owns:
- approved paper-source acquisition mechanics;
- source-specific parser invocation;
- preservation of source identity/provenance needed by the corpus producer.

Does not own:
- canonical paper identity;
- review presentation;
- shared knowledge interoperability contracts.

Outputs such as downloaded files or TEI XML are staging inputs, not public knowledge artifacts by default.

### 2. Paper corpus core

Current implementation includes `pipeline/parsers/`, `pipeline/identity.py`, `pipeline/producer/`, `pipeline/writers/`, and `pipeline/corpus.py`.

Owns:
- canonical paper identity (`paper_uid`) and chunk identity;
- paper-specific parsing/canonicalization semantics;
- named corpus layout;
- production of governed paper chunk artifacts.

Canonical public parsing output remains the chunk-set artifact. Legacy filesystem chunks, caches, Chroma materializations and backend compatibility files are not promoted to public contracts merely because they exist.

### 3. Paper read service

Current implementation includes `backend/app/`, especially `storage_adapter.py`, `services.py`, `schemas.py` and `main.py`.

Owns:
- a read/query model over existing paper artifacts;
- repository-local API behavior and diagnostics;
- compatibility adapters needed to serve the workbench.

Does not own:
- source acquisition;
- canonical corpus production;
- paper identity semantics independently from the corpus core.

The read service should increasingly consume canonical corpus artifacts rather than legacy storage internals.

### 4. Paper-specific derivations

Current implementation includes `backend/exports/generate_summaries.py`, `backend/exports/summary_artifacts.py`, `backend/llm/` and experimental summary workflows.

Owns:
- paper-specific derived summaries or analyses that are explicitly produced here;
- their repository-local run/validation semantics.

Does not own:
- corpus truth;
- general-purpose knowledge inspection;
- evidence promotion.

A successful derivation never rewrites the source corpus artifact.

### 5. Review projection

Current implementation is concentrated in `backend/exports/export_review_csv.py`.

Owns:
- mapping paper-domain data into a bounded review-oriented projection;
- producer-owned semantics of `paper.review-record@1`.

Current CSV output is classified as a **legacy/convenience projection**. It remains supported until a replacement is proven, but its column layout is not the authority for the paper review domain.

P1 introduces the producer-owned `paper.review-record@1` contract. P2 is responsible for canonical JSONL emission. Until P2 exists, `paper-kb` declares the contract but does not claim to produce a canonical review-record artifact.

### 6. Paper workbench

Current implementation is `frontend/` (Next.js).

Owns:
- interactive paper-workbench UX over the paper read service;
- frontend state and presentation behavior.

Does not own:
- corpus identity;
- parsing;
- review snapshot publication semantics.

## Dependency direction

Allowed direction is generally:

```text
sources -> corpus core -> {read service, derivations, review projection}
read service -> workbench
review projection -> external review consumers
```

Avoid reverse dependencies such as:
- corpus parsing importing frontend concerns;
- corpus identity depending on Abstract Scroller fields;
- review projection reaching into consumer snapshot internals;
- the API becoming the only source of corpus truth;
- LLM summaries mutating canonical paper/chunk artifacts.

## Public and private seams

Current public/provable seam:
- `chunk_set@1` from Paper KB to Knowledge Inspect (cross-repo W3 proof).

New producer-owned seam declared by P1:
- `paper.review-record@1`, schema at `contracts/paper.review_record.v1.schema.json`.

Candidate downstream seam, not yet proven:
- `paper.review-record@1` -> Abstract Scroller review adapter -> immutable review snapshot.

Legacy/convenience seam:
- review CSV generated by `backend.exports.export_review_csv`.

## Identity rule for review projection

`paper_uid` is the canonical paper identity for the review contract. `paper_id` may be carried as a source/legacy identifier but must not replace `paper_uid` as the stable contract identity.

The chunk-set writer already preserves `paper_uid`. The current `ChunkSetStorageAdapter` does not yet elevate that field consistently into its paper-level read model. P2 must either project directly from canonical corpus artifacts or repair the read model before using it as the canonical review-record source.

## When to split repositories

Do **not** split only because directories are large. Physical extraction becomes justified when a component demonstrates at least two of:
- an independent release/deployment cadence;
- multiple upstream producers or downstream consumers;
- a stable public contract independent of Paper KB internals;
- materially different dependency/runtime requirements;
- governance or rights boundaries that benefit from isolation.

Until then, explicit internal boundaries plus contract tests are cheaper and safer than repository churn.

## P0 acceptance

P0 is satisfied when:
- a contributor can identify which component owns a proposed change;
- `chunk_set` is clearly separated from API/storage/UI concerns;
- review projection is explicitly separated from snapshot publication;
- no repository split is required to preserve those boundaries.
