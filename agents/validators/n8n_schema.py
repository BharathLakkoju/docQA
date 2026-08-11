"""n8n workflow JSON schema validation for the Fix Agent.

Honesty note (per CLAUDE.md — thin sources get said plainly, not papered
over): n8n does not publish an official standalone JSON Schema for the
workflow export format (confirmed by searching n8n-io/n8n's GitHub repo —
the format is defined only via internal TypeScript interfaces, not a
distributable schema file). This schema was derived by inspecting the
structure actually present across the 1,017 real templates pulled in
Phase 1a (see ingestion/n8n/) — required top-level keys (`nodes`,
`connections`) and required per-node fields (`id`, `name`, `type`,
`position`, `parameters`). It validates structural well-formedness, not
n8n's full internal business-logic rules (e.g. it can't know whether a
specific node type accepts a specific parameter key). This is a real,
if partial, safety net — not a claim of n8n's authoritative schema.
"""
from __future__ import annotations

from dataclasses import dataclass

import jsonschema

N8N_WORKFLOW_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["nodes", "connections"],
    "properties": {
        "name": {"type": "string"},
        "nodes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "name", "type", "position", "parameters"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "typeVersion": {"type": "number"},
                    "position": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 2,
                        "items": {"type": "number"},
                    },
                    "parameters": {"type": "object"},
                    "credentials": {"type": "object"},
                },
            },
        },
        "connections": {"type": "object"},
    },
}

_validator = jsonschema.Draft7Validator(N8N_WORKFLOW_SCHEMA)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]


def validate_workflow(workflow_obj: dict) -> ValidationResult:
    errors = [f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in _validator.iter_errors(workflow_obj)]
    return ValidationResult(valid=not errors, errors=errors)
