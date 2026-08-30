# Paper Corpus Workbench

The Paper KB frontend is the repository's interactive paper-corpus workbench. It consumes the Paper KB read service; it does not parse papers or redefine corpus identity.

## Run against a governed corpus

From the repository root, start the read service over one named corpus:

```bash
make api-corpus CORPUS=tesis-cited PORT=9000
```

In another terminal:

```bash
make frontend-dev PORT=9000
```

The frontend defaults to `http://127.0.0.1:9000` and can be pointed at another compatible Paper KB API with `NEXT_PUBLIC_API_BASE`.

## Workbench tabs

The canonical Paper KB product is composed from five code-owned tabs:

- **Corpus** — browse papers and see metadata coverage;
- **Authors** — navigate author-centered groupings;
- **Abstracts** — scan available abstracts and expose missing upstream metadata;
- **Search** — query canonical chunks through the real `/api/search` endpoint;
- **Paper** — inspect canonical identity, metadata, chunks and bounded summary derivations.

A deployment can select/reorder existing tabs without creating a new frontend:

```bash
NEXT_PUBLIC_WORKBENCH_TABS=corpus,authors,paper npm run dev
```

This is deliberately a bounded product-composition seam, not a plugin framework. See [`ARCHITECTURE/tab-composition.md`](ARCHITECTURE/tab-composition.md).

## Deep links

Workbench state is represented in the URL:

```text
/?tab=paper&paper=<paper_id>
```

`/papers/<paper_id>` redirects to the same Paper tab instead of maintaining a duplicate detail implementation.

## Summary writes

Summary artifacts are derived outputs, not corpus truth. The workbench never creates mock summaries. Existing summaries can be inspected by default. Experimental Agent Framework write actions are hidden unless explicitly enabled:

```bash
NEXT_PUBLIC_ENABLE_SUMMARY_WRITES=1 npm run dev
```

The backend still controls provider/runtime availability and may reject generation when credentials or dependencies are absent.

## Verification

```bash
npm ci
npm run lint
npm run build
```

Frontend verification is also run in GitHub Actions so the workbench remains inside the repository evidence loop as the corpus/read model evolves.
