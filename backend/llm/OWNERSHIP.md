# Paper derivation LLM ownership

`backend/llm` contains implementation support for **paper-specific derived outputs**.

It may help generate summaries or other explicitly derived artifacts. It does not own:

- paper/chunk identity;
- parsing or corpus truth;
- review-record contracts;
- evidence promotion;
- general-purpose knowledge inspection.

LLM success must never mutate or replace canonical paper/chunk artifacts. New cross-domain inspection capabilities should be evaluated against Knowledge Inspect rather than accumulated here by default.
