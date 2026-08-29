# Backend exports ownership

This directory is not a single architectural component.

Current responsibilities are deliberately classified as:

- `generate_summaries.py`, `summary_artifacts.py`, `build_summary_inputs.py`: **paper-specific derivations**;
- `export_review_csv.py`: **legacy review compatibility surface**.

Canonical review-domain projection logic must not be added here. It belongs in `pipeline/projections/` and is governed by `paper.review-record@1`.

The historical CSV module remains import-compatible because existing proofs/consumers use it. Its presence here is compatibility debt, not authority. A future move is justified only when it can preserve the old module path through a thin wrapper and does not change the CSV contract.
