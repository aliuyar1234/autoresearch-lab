from __future__ import annotations

from pathlib import Path
from typing import Any

from .json_io import read_json


class SchemaValidationError(ValueError):
    pass


def load_schema(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise SchemaValidationError(f"schema at {path} is not an object")
    return payload


def validate_payload(payload: Any, schema: dict[str, Any], *, path: str = "$") -> None:
    _validate_node(payload, schema, path)


def _validate_node(value: Any, schema: dict[str, Any], path: str) -> None:
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        raise SchemaValidationError(f"{path} expected type {expected_type!r}, got {type(value).__name__}")

    enum_values = schema.get("enum")
    if enum_values is not None and value not in enum_values:
        raise SchemaValidationError(f"{path} must be one of {enum_values!r}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise SchemaValidationError(f"{path}.{key} is required")

        if schema.get("additionalProperties") is False:
            allowed = set(schema.get("properties", {}).keys())
            extras = sorted(key for key in value if key not in allowed)
            if extras:
                raise SchemaValidationError(f"{path} has unexpected keys: {', '.join(extras)}")

        for key, child_schema in schema.get("properties", {}).items():
            if key in value:
                _validate_node(value[key], child_schema, f"{path}.{key}")

    if isinstance(value, list):
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                _validate_node(item, item_schema, f"{path}[{index}]")

    minimum = schema.get("minimum")
    if minimum is not None and isinstance(value, (int, float)) and not isinstance(value, bool) and value < minimum:
        raise SchemaValidationError(f"{path} must be >= {minimum}")

    maximum = schema.get("maximum")
    if maximum is not None and isinstance(value, (int, float)) and not isinstance(value, bool) and value > maximum:
        raise SchemaValidationError(f"{path} must be <= {maximum}")

    min_length = schema.get("minLength")
    if min_length is not None and isinstance(value, str) and len(value) < min_length:
        raise SchemaValidationError(f"{path} must have length >= {min_length}")


def _matches_type(value: Any, expected: str | list[str]) -> bool:
    expected_types = expected if isinstance(expected, list) else [expected]
    return any(_matches_single_type(value, item) for item in expected_types)


def _matches_single_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True
