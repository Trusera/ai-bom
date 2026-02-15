"""JSON Schema validation for AI-BOM output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import validate


def get_schema() -> dict[str, Any]:
    """Load the AI-BOM JSON schema."""
    schema_path = Path(__file__).parent.parent / "schema" / "bom-schema.json"
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def validate_output(data: dict[str, Any]) -> None:
    """Validate scan output against the JSON schema.

    Args:
        data: The JSON-compatible dict to validate.

    Raises:
        jsonschema.ValidationError: If validation fails.
    """
    schema = get_schema()
    validate(instance=data, schema=schema)
