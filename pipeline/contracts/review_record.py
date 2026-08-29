"""Dependency-light validation for the producer-owned paper review record."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "paper.review_record.v1.schema.json"


class ReviewRecordValidationError(ValueError):
    """Raised when a paper.review-record@1 payload violates the local contract."""


def load_review_record_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _fallback_validate(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    required = schema.get("required", [])
    for field in required:
        if field not in payload:
            raise ReviewRecordValidationError(f"missing required field: {field}")

    if payload.get("schema_id") != "paper.review-record":
        raise ReviewRecordValidationError("schema_id must be paper.review-record")
    if payload.get("schema_version") != 1:
        raise ReviewRecordValidationError("schema_version must be 1")

    for field in ("paper_uid", "title"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ReviewRecordValidationError(f"{field} must be a non-empty string")

    nullable_strings = ("paper_id", "abstract", "date", "venue", "doi", "arxiv_id", "repec_id", "source_url")
    for field in nullable_strings:
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            raise ReviewRecordValidationError(f"{field} must be a string or null")

    year = payload.get("year")
    if year is not None and (not isinstance(year, int) or isinstance(year, bool)):
        raise ReviewRecordValidationError("year must be an integer or null")

    for field in ("tags", "badges"):
        value = payload.get(field)
        if value is None:
            continue
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ReviewRecordValidationError(f"{field} must be an array of strings")

    allowed = set(schema.get("properties", {}))
    extras = sorted(set(payload) - allowed)
    if extras:
        raise ReviewRecordValidationError("unexpected fields: " + ", ".join(extras))


def validate_review_record_dict(payload: dict[str, Any]) -> None:
    """Validate a review record without making jsonschema a runtime dependency.

    When jsonschema is already installed it is used for full schema validation;
    otherwise the contract's required, identity, type and closed-shape invariants
    are enforced locally.
    """
    schema = load_review_record_schema()
    try:
        import jsonschema  # type: ignore
    except ImportError:
        _fallback_validate(payload, schema)
        return

    try:
        jsonschema.validate(instance=payload, schema=schema)
    except Exception as exc:
        raise ReviewRecordValidationError(str(exc)) from exc
