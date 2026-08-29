# Paper KB

Paper KB is a modular paper-knowledge monorepo. The durable center is the governed paper corpus; API, paper-specific derivations, review projections and the workbench are consumers or projections of that corpus rather than alternate sources of truth.

Start with:
- [`docs/architecture/paper-kb-component-boundaries.md`](docs/architecture/paper-kb-component-boundaries.md) — P0 component authority;
- [`pipeline/OWNERSHIP.md`](pipeline/OWNERSHIP.md) — corpus-pipeline ownership;
- [`docs/contracts/paper-review-record.md`](docs/contracts/paper-review-record.md) — P1 producer-owned review contract.

## Operator Make targets

Run all commands from repo root.

```bash
make corpus-doctor CORPUS=tesislcd
make corpus-grobid CORPUS=tesislcd MAX_FILES=2
make corpus-parse CORPUS=tesislcd
make corpus-validate CORPUS=tesislcd
make contract-review-record
make export-review CORPUS=tesislcd
make api-corpus CORPUS=tesislcd PORT=9000
make kill-port PORT=9000
make frontend-dev PORT=9000
```

`contract-review-record` is dependency-light and uses only sanitized fixtures. `export-review` is still the legacy/convenience CSV projection; P1 does not yet replace it with canonical JSONL emission.

Canonical API port is `9000`. `api-corpus` preflights the port. Legacy placeholder targets remain explicit `legacy-*` failures rather than aliases to modern behavior.
