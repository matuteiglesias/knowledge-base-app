# AGENTS.md — Paper KB

## Mission

Maintain the bounded paper-corpus producer: parsing approved papers, producing structured chunks and summaries, exporting review material, and serving the repository's own corpus API.

This repository does not own shared interoperability contracts, general chat ingestion, evidence-selection policy, context routing, MCP access policy, or portfolio topology.

## Authority boundary

Matías owns corpus selection, paper-use rights, parsing acceptance, summary meaning, publication decisions, and any change to the paper knowledge model.

Agents may:

- repair a reproduced parser, corpus, export, or API defect;
- improve deterministic validation and sanitized fixtures;
- implement an explicitly approved corpus or schema change;
- prepare a decision packet for ambiguous document rights or parsing behavior.

Agents must not independently:

- ingest additional papers or directories;
- publish source PDFs, full text, chunks, summaries, annotations, or review exports;
- copy shared schemas from `kb-contracts` into a local competing authority;
- add general chat ingestion, routing, selection, MCP, or orchestration behavior;
- replace missing source material with synthetic content while claiming reproduction;
- rewrite archival/legacy evidence to resemble a clean modern pipeline;
- start external services or process a real corpus merely to validate a documentation change.

## Corpus and rights rules

Treat source papers, extracted text, chunks, structured summaries, review exports, and annotations as rights-sensitive.

- Use only explicitly approved corpora.
- Keep source provenance and document identity stable.
- Do not commit private, licensed, embargoed, or unnecessarily large source material.
- Sanitized fixtures must not reproduce substantial source text or expose local physical paths.
- Generated chunks and summaries do not become freely publishable merely because the parser produced them.
- Record parser, source, version, corpus, run, and output identifiers for accepted artifacts.

## Canonical and generated paths

The repository-local corpus directories and chunk sets are generated evidence from specific inputs and commands. Do not hand-edit them to repair a parser result.

Fix source logic or approved configuration, rerun the bounded stage, validate, and preserve provenance.

Legacy targets and placeholders remain explicit history. Do not silently map them to new behavior.

## Commands

Inspect and validate an existing corpus with the bounded commands:

```bash
make corpus-doctor CORPUS=<corpus>
make corpus-validate CORPUS=<corpus>
```

Consequential corpus-generation commands:

```bash
make corpus-grobid CORPUS=<corpus> MAX_FILES=<bounded-count>
make corpus-parse CORPUS=<corpus>
make export-review CORPUS=<corpus>
```

Runtime surfaces:

```bash
make api-corpus CORPUS=<corpus> PORT=<port>
make frontend-dev PORT=<port>
```

Rules:

- `corpus-grobid` may depend on an external GROBID service and creates parsed artifacts.
- `corpus-parse` and `export-review` write generated outputs.
- `api-corpus` starts a local server and requires a free port.
- `frontend-dev` starts a development process.
- Do not run these commands against a real or large corpus unless the task explicitly authorizes it.
- The `legacy-*` targets deliberately fail and must not be presented as validation commands.

## Contract changes

When changing a corpus manifest, chunk schema, identifier, API response, or export contract:

1. identify the repository-local contract affected;
2. verify whether a shared `kb-contracts` interface is involved;
3. preserve stable document and chunk identity where required;
4. add sanitized valid and invalid fixtures;
5. state migration and regeneration consequences;
6. verify downstream consumers explicitly;
7. do not broaden shared contract authority by implication.

## Change discipline

- Prefer small parser/API modules and fixtures over notebook or corpus-wide edits.
- Preserve original source and archival outputs.
- Avoid broad dependency, frontend, or infrastructure upgrades during corpus repair.
- Never claim a paper, corpus, parser result, API, or external service was inspected or run unless it actually was.
- Unknown rights, missing papers, unavailable GROBID, and malformed source files are valid blocked outcomes.

## Completion report

```text
Changed:
Corpus/source accessed:
Rights basis:
Commands run:
External services used:
Generated outputs:
Contracts changed:
Fixtures/tests:
Source text committed:
Downstream compatibility:
Blocked:
Next:
```
