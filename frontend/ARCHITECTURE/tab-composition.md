# Paper workbench tab composition

Status: bounded frontend composition seam.

The Paper KB frontend is a paper-corpus workbench over the repository-local read service. It is not a new source of paper truth, a generic plugin platform, or a replacement for Knowledge Experiences, Abstract Scroller, or Knowledge Inspect.

## Product model

A workbench product is a selected ordered subset of code-owned tabs:

```text
WorkbenchProduct
    |
    +-- corpus
    +-- authors
    +-- abstracts
    +-- search
    +-- paper
```

The canonical Paper KB product enables all five. A deployment can select/reorder implemented tabs through `NEXT_PUBLIC_WORKBENCH_TABS`, for example:

```bash
NEXT_PUBLIC_WORKBENCH_TABS=corpus,authors,paper npm run dev
```

This is intentionally a bounded configuration seam. Unknown tabs are ignored. No remote manifests, arbitrary component loading, schema ownership, or runtime plugin protocol is introduced.

## Tab responsibilities

- `corpus`: corpus-wide browse and metadata-coverage visibility;
- `authors`: author-centered projection over producer-provided author metadata;
- `abstracts`: rapid abstract scan and explicit missing-metadata visibility;
- `search`: real chunk search through `/api/search`, reporting the backend capability rather than claiming semantic search;
- `paper`: one-paper metadata/chunk/summary inspection with canonical `paper_uid` visible.

Tabs consume shared workbench context (`papers`, selected paper, corpus health and navigation). They may derive presentation groupings but do not mutate or infer corpus authority.

## Identity and URL state

The read model exposes both canonical `paper_uid` and compatibility `paper_id`. The frontend preserves both; `paper_id` remains the current route/API handle while `paper_uid` is shown as canonical interoperable identity.

Workbench state is deep-linkable:

```text
/?tab=<tab-id>&paper=<paper_id>
```

`/papers/<paper_id>` redirects to the canonical Paper tab link rather than maintaining a second detail implementation.

## Composition boundary

This seam is meant to answer a product question: can useful paper experiences be assembled cheaply from a small catalog of proven tabs?

Do not generalize it into a framework until real products require capabilities that cannot be represented as a bounded subset/order of existing tabs. In particular, do not add remote plugins, a manifest DSL, cross-repository renderer loading, or tab-owned storage merely to make the abstraction look more complete.
