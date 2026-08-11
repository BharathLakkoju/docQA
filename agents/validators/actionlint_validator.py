"""Real `actionlint` subprocess validation for generated GitHub Actions
YAML — per AGENTS.md's Fix Agent spec, this is an actual parse/lint call,
never the LLM asserting its own output is valid.

Install: `go install github.com/rhysd/actionlint/cmd/actionlint@latest`
(requires Go; see https://github.com/rhysd/actionlint for prebuilt
binaries if Go isn't available in the deploy environment).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]


def _find_actionlint() -> str | None:
    found = shutil.which("actionlint")
    if found:
        return found
    candidates = [
        Path.home() / "go" / "bin" / "actionlint.exe",
        Path.home() / "go" / "bin" / "actionlint",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def validate_yaml(yaml_text: str) -> ValidationResult:
    binary = _find_actionlint()
    if binary is None:
        return ValidationResult(
            valid=False,
            errors=[
                "actionlint is not installed — cannot validate. "
                "Install with: go install github.com/rhysd/actionlint/cmd/actionlint@latest"
            ],
        )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, encoding="utf-8") as f:
        f.write(yaml_text)
        temp_path = f.name

    try:
        result = subprocess.run(
            [binary, "-format", "{{json .}}", temp_path],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        Path(temp_path).unlink(missing_ok=True)

    if result.returncode == 0:
        return ValidationResult(valid=True, errors=[])

    try:
        issues = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        return ValidationResult(valid=False, errors=[result.stdout or result.stderr or "actionlint failed"])

    errors = [f"line {i['line']}, col {i['column']}: {i['message']} [{i['kind']}]" for i in issues]
    return ValidationResult(valid=False, errors=errors or ["actionlint reported a failure with no parseable detail"])
