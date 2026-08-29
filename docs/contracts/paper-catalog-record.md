# `paper.catalog-record@1`

`paper.catalog-record@1` is a producer-owned Paper KB projection for bibliography/catalog experiences. It exists because review-oriented `paper.review-record@1` should not absorb browsing requirements such as author facets.

## Authority

Paper KB owns this contract. `kb-contracts`, Knowledge Experiences and renderers do not redefine paper metadata.

The canonical projection is:

```text
governed chunk_set paper_meta
        ↓
pipeline.projections.catalog_records
        ↓
paper.catalog-record@1 JSONL
```

The projection copies only metadata already present in `paper_meta`; it does not infer missing authors, dates or venues from filenames, chunks or consumer context.

Required identity/display fields:

- `paper_uid` — canonical Paper KB identity;
- `title`;
- `authors` — an array of author display names; it may be empty when the producer lacks author metadata.

Optional fields include `paper_id`, abstract, date/year, venue, DOI/arXiv/RePEc identifiers, tags and a source URL.

## Operator command

```bash
make export-catalog-records CORPUS=tesislcd
```

Default output:

```text
corpora/<corpus>/catalog/paper.catalog-record.v1.jsonl
```

The output is sorted by `paper_uid`, rejects duplicate canonical identity and validates each record before atomic write.

## Consumer rule

Consumers may project this record into their own display/facet shape. They must not write consumer fields back into this contract or guess absent paper semantics.
