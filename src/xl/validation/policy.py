"""Policy engine — load and enforce xl-policy.yaml rules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from xl.contracts.common import ErrorDetail, WarningDetail
from xl.io.fileops import read_text_safe
from xl.contracts.plans import PatchPlan


class Policy:
    """Represents a loaded policy configuration."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.protected_sheets: list[str] = data.get("protected_sheets", [])
        self.protected_ranges: list[str] = data.get("protected_ranges", [])
        self.mutation_thresholds: dict[str, int] = data.get("mutation_thresholds", {})
        self.allowed_commands: list[str] = data.get("allowed_commands", [])
        self.redaction: dict[str, Any] = data.get("redaction", {})

    @classmethod
    def load(cls, path: str | Path) -> "Policy":
        """Load policy from a YAML file."""
        text = read_text_safe(path)
        data = yaml.safe_load(text) or {}
        return cls(data)

    @classmethod
    def load_from_dir(cls, directory: str | Path) -> "Policy | None":
        """Try to load xl-policy.yaml from a directory. Returns None if not found."""
        path = Path(directory) / "xl-policy.yaml"
        if path.exists():
            return cls.load(path)
        return None


def check_plan_policy(policy: Policy, plan: PatchPlan) -> list[dict[str, Any]]:
    """Check a plan against policy rules. Returns list of violations."""
    violations: list[dict[str, Any]] = []

    # Check protected sheets
    for op in plan.operations:
        sheet = op.sheet
        if sheet and sheet in policy.protected_sheets:
            violations.append({
                "type": "protected_sheet",
                "severity": "error",
                "op_id": op.op_id,
                "message": f"Operation {op.op_id} targets protected sheet '{sheet}'",
            })

    # Check protected ranges
    for op in plan.operations:
        if op.ref:
            full_ref = f"{op.sheet}!{op.ref}" if op.sheet else op.ref
            for protected in policy.protected_ranges:
                if full_ref.startswith(protected.split("!")[0] if "!" in protected else ""):
                    violations.append({
                        "type": "protected_range",
                        "severity": "error",
                        "op_id": op.op_id,
                        "message": f"Operation {op.op_id} may affect protected range '{protected}'",
                    })

    # Check mutation thresholds
    max_cells = policy.mutation_thresholds.get("max_cells")
    max_rows = policy.mutation_thresholds.get("max_rows")
    total_rows = 0
    for op in plan.operations:
        if op.rows:
            total_rows += len(op.rows)

    if max_rows and total_rows > max_rows:
        violations.append({
            "type": "mutation_threshold",
            "severity": "error",
            "message": f"Plan mutates {total_rows} rows, exceeding threshold of {max_rows}",
        })

    return violations
