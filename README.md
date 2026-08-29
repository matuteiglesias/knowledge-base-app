# Paper KB

Paper KB is a modular paper-knowledge monorepo. The durable center is the governed paper corpus; API, paper-specific derivations, review projections and the workbench are consumers or projections of that corpus rather than alternate sources of truth.

Start with:
- [`docs/architecture/paper-kb-component-boundaries.md`](docs/architecture/paper-kb-component-boundaries.md) — component authority and dependency direction;
- [`pipeline/OWNERSHIP.md`](pipeline/OWNERSHIP.md) — corpus-pipeline ownership;
- [`docs/contracts/paper-review-record.md`](docs/contracts/paper-review-record.md) — producer-owned review contract.

## Operator Make targets

Run all commands from repo root.

```bash
make corpus-doctor CORPUS=tesislcd
make corpus-grobid CORPUS=tesislcd MAX_FILES=2
make corpus-parse CORPUS=tesislcd
make corpus-validate CORPUS=tesislcd
make contract-review-record
make export-review-records CORPUS=tesislcd
make api-corpus CORPUS=tesislcd PORT=9000
make kill-port PORT=9000
make frontend-dev PORT=9000
```

`export-review-records` is the preferred machine review interface. It projects governed `chunk_set` artifacts directly to deterministic, validated `paper.review-record@1` JSONL while preserving canonical `paper_uid`.

Compatibility remains explicit rather than silent:

```bash
make export-review-csv CORPUS=tesislcd
make export-review CORPUS=tesislcd   # deprecated alias
```

The CSV field layout is supported for existing consumers but is not the authority for paper-review semantics. New machine integrations should consume `paper.review-record@1`.

Canonical API port is `9000`. `api-corpus` preflights the port. Legacy placeholder targets remain explicit `legacy-*` failures rather than aliases to modern behavior.
