"""Dependency-light validation for producer-owned paper.catalog-record@1."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "paper.catalog_record.v1.schema.json"


class CatalogRecordValidationError(ValueError):
    """Raised when a paper.catalog-record@1 payload violates the local contract."""


def load_catalog_record_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _fallback_validate(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    for field in schema.get("required", []):
        if field not in payload:
            raise CatalogRecordValidationError(f"missing required field: {field}")

    if payload.get("schema_id") != "paper.catalog-record":
        raise CatalogRecordValidationError("schema_id must be paper.catalog-record")
    if payload.get("schema_version") != 1:
        raise CatalogRecordValidationError("schema_version must be 1")

    for field in ("paper_uid", "title"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CatalogRecordValidationError(f"{field} must be a non-empty string")

    nullable_strings = ("paper_id", "abstract", "date", "venue", "doi", "arxiv_id", "repec_id", "source_url")
    for field in nullable_strings:
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            raise CatalogRecordValidationError(f"{field} must be a string or null")

    year = payload.get("year")
    if year is not None and (not isinstance(year, int) or isinstance(year, bool)):
        raise CatalogRecordValidationError("year must be an integer or null")

    for field in ("authors", "tags"):
        value = payload.get(field)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            raise CatalogRecordValidationError(f"{field} must be an array of non-empty strings")

    allowed = set(schema.get("properties", {}))
    extras = sorted(set(payload) - allowed)
    if extras:
        raise CatalogRecordValidationError("unexpected fields: " + ", ".join(extras))


def validate_catalog_record_dict(payload: dict[str, Any]) -> None:
    schema = load_catalog_record_schema()
    try:
        import jsonschema  # type: ignore
    except ImportError:
        _fallback_validate(payload, schema)
        return

    try:
        jsonschema.validate(instance=payload, schema=schema)
    except Exception as exc:
        raise CatalogRecordValidationError(str(exc)) from exc
