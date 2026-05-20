## Operator Make targets

Run all commands from repo root.

```bash
make corpus-doctor CORPUS=tesislcd
make corpus-grobid CORPUS=tesislcd MAX_FILES=2
make corpus-parse CORPUS=tesislcd
make corpus-validate CORPUS=tesislcd
make export-review CORPUS=tesislcd
make api-corpus CORPUS=tesislcd PORT=9000
make kill-port PORT=9000
make frontend-dev PORT=9000
```

Notes:
- Canonical API port is `9000`.
- `api-corpus` preflights the port and fails clearly if occupied.
- `kill-port` is explicit and separate.
- Legacy placeholder targets were renamed to `legacy-*` and now fail with guidance.
