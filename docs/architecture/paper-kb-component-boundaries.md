# Paper KB component boundaries

Status: **current reference for repository-internal responsibilities**  
Updated: 2026-08-29

`paper-kb` is a **modular monorepo**, not one undifferentiated application and not yet a set of repositories to split apart. Folder names are implementation locations; authority follows the component boundaries and contracts below.

## Governing rule

The governed paper corpus is the durable center. Parsing produces corpus artifacts. API, summaries, review projections and user interfaces consume or derive from those artifacts; they do not redefine corpus truth.

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
        Abstract Scroller / compatible consumers
```

## Component map

### 1. Source acquisition and parser adapters

Current implementation includes `pipeline/sources/` and `pipeline/adapter/`, including GROBID integration.

Owns approved source acquisition mechanics, source-specific parser invocation, and preservation of source identity/provenance required by the corpus producer. Downloaded files and TEI XML are staging inputs, not public knowledge artifacts by default.

Does not own canonical paper identity, review presentation, or shared interoperability contracts.

### 2. Paper corpus core

Current implementation includes `pipeline/parsers/`, `pipeline/identity.py`, `pipeline/producer/`, `pipeline/writers/`, and `pipeline/corpus.py`.

Owns canonical `paper_uid`, chunk identity, paper-specific parsing/canonicalization semantics, named corpus layout, and governed paper chunk artifacts.

The canonical public parsing output is the chunk-set artifact. Legacy filesystem chunks, caches, Chroma materializations and backend compatibility files are not public contracts merely because they exist.

### 3. Paper read service

Current implementation includes `backend/app/`, especially `storage_adapter.py`, `services.py`, `schemas.py` and `main.py`.

Owns the repository-local read/query model, HTTP behavior, diagnostics and workbench compatibility adapters.

Does not own source acquisition, canonical corpus production, or paper identity semantics independently from the corpus core. The service should consume canonical corpus artifacts and preserve corpus identity rather than minting a competing identity layer.

Known P5 debt: the current chunk-set read model does not consistently elevate `paper_uid` to paper-level API objects even though the source artifact preserves it.

### 4. Paper-specific derivations

Current implementation includes `backend/exports/generate_summaries.py`, `backend/exports/summary_artifacts.py`, `backend/llm/` and experimental summary workflows.

Owns explicitly paper-specific derived summaries/analyses and their repository-local run semantics. A successful derivation never rewrites source corpus artifacts.

Does not own corpus truth, general-purpose knowledge inspection, review projection semantics, or evidence promotion.

### 5. Review projection

Canonical implementation is `pipeline/projections/review_records.py`.

Owns mapping governed paper corpus artifacts into bounded review-oriented domain records and producer-owned semantics of `paper.review-record@1`.

The preferred machine seam is:

```text
chunk_set artifacts
      -> pipeline.projections.review_records
      -> paper.review-record@1 JSONL
```

The projection is deterministic, validates every output record, requires canonical `paper_uid`, fails on duplicate identity, and does not depend on FastAPI, Chroma, the workbench, or Abstract Scroller internals.

`backend/exports/export_review_csv.py` is a retained **compatibility surface**. Its CSV field layout is not domain authority. `make export-review-csv` is the explicit compatibility command; `make export-review` is a deprecated alias.

P3 proved that Abstract Scroller can consume canonical `paper.review-record@1` while preserving `paper_uid` as snapshot identity. The historical CSV edge remains tested only as backwards compatibility.

### 6. Paper workbench

Current implementation is `frontend/` (Next.js).

Owns interactive paper-workbench UX over the paper read service, frontend state and presentation behavior.

Does not own corpus identity, parsing, review-record contracts or snapshot publication semantics.

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
- canonical review projection importing API, LLM, Chroma or consumer snapshot internals;
- the API becoming the only source of corpus truth;
- LLM summaries mutating canonical paper/chunk artifacts.

P5 turns the most important of these rules into executable architecture checks.

## Public and compatibility seams

Proven public seams:
- `chunk_set@1` from Paper KB to Knowledge Inspect;
- `paper.review-record@1` from Paper KB to Abstract Scroller.

Producer-owned review contract:
- `contracts/paper.review_record.v1.schema.json`.

Compatibility seam:
- review CSV exposed explicitly through `export-review-csv` and the historical `backend.exports.export_review_csv` module.

## Identity rule

`paper_uid` is canonical paper identity for review interoperability. `paper_id` may be carried as a source/legacy identifier but does not replace `paper_uid` in the review contract.

The review projection reads canonical corpus artifacts directly, so API/read-model identity loss is not an interoperability blocker. P5 should nevertheless repair the read model so API and workbench surfaces faithfully expose the same canonical identity.

## When to split repositories

Do **not** split because directories are large. Physical extraction becomes justified when a component demonstrates at least two of:
- an independent release/deployment cadence;
- multiple upstream producers or downstream consumers;
- a stable public contract independent of Paper KB internals;
- materially different dependency/runtime requirements;
- governance or rights boundaries that benefit from isolation.

Until then, explicit component ownership, dependency tests and contract proofs are cheaper and safer than repository churn.
