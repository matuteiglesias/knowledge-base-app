# Paper KB

Paper KB is a modular paper-knowledge monorepo. The durable center is the governed paper corpus; API, paper-specific derivations, review projections and the workbench are consumers or projections of that corpus rather than alternate sources of truth.

Start with:
- [`docs/architecture/paper-kb-component-boundaries.md`](docs/architecture/paper-kb-component-boundaries.md) — component authority and dependency direction;
- [`docs/architecture/component-manifest.json`](docs/architecture/component-manifest.json) — machine-readable component map and enforced rules;
- [`pipeline/OWNERSHIP.md`](pipeline/OWNERSHIP.md) — corpus-pipeline ownership;
- [`docs/contracts/paper-review-record.md`](docs/contracts/paper-review-record.md) — producer-owned review contract.

## Operator Make targets

Run all commands from repo root.

```bash
make corpus-doctor CORPUS=tesislcd
make corpus-grobid CORPUS=tesislcd MAX_FILES=2
make corpus-parse CORPUS=tesislcd
make corpus-validate CORPUS=tesislcd

make architecture-check
make read-model-identity
make contract-review-record

make export-review-records CORPUS=tesislcd
make api-corpus CORPUS=tesislcd PORT=9000
make kill-port PORT=9000
make frontend-dev PORT=9000
```

`architecture-check` enforces the highest-value modular-monorepo dependency boundaries without attempting to freeze every internal import. `read-model-identity` proves that canonical `paper_uid` survives `chunk_set -> storage/read model -> PaperMeta` while legacy `paper_id` remains available.

`export-review-records` is the preferred machine review interface. It projects governed `chunk_set` artifacts directly to deterministic, validated `paper.review-record@1` JSONL while preserving canonical `paper_uid`.

Compatibility remains explicit rather than silent:

```bash
make export-review-csv CORPUS=tesislcd
make export-review CORPUS=tesislcd   # deprecated alias
```

The CSV field layout is supported for existing consumers but is not the authority for paper-review semantics. New machine integrations should consume `paper.review-record@1`.

Paper-specific summaries and LLM implementation remain an explicit derivation component inside this monorepo. P5 does not split repositories or move those workflows merely for structural neatness; extraction remains evidence-driven.

Canonical API port is `9000`. `api-corpus` preflights the port. Legacy placeholder targets remain explicit `legacy-*` failures rather than aliases to modern behavior.
