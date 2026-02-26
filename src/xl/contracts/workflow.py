"""Workflow spec models for ``xl run``."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class WorkflowDefaults(BaseModel):
    output: str = "json"
    recalc: str = "cached"
    dry_run: bool = False
    stop_on_error: bool = False


class WorkflowStep(BaseModel):
    id: str
    run: str
    args: dict[str, Any] = Field(default_factory=dict)

    @field_validator("run")
    @classmethod
    def validate_run_command(cls, v: str) -> str:
        from xl.engine.workflow import WORKFLOW_COMMANDS

        if v not in WORKFLOW_COMMANDS:
            raise ValueError(
                f"Unknown workflow step command: '{v}'. "
                f"Supported: {', '.join(sorted(WORKFLOW_COMMANDS))}"
            )
        return v


class WorkflowSpec(BaseModel):
    schema_version: str = "1.0"
    name: str = ""
    target: dict[str, str] = Field(default_factory=dict)
    defaults: WorkflowDefaults = Field(default_factory=WorkflowDefaults)
    steps: list[WorkflowStep] = Field(default_factory=list)
