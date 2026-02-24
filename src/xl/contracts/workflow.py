"""Workflow spec models for ``xl run``."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkflowDefaults(BaseModel):
    output: str = "json"
    recalc: str = "cached"
    dry_run: bool = False


class WorkflowStep(BaseModel):
    id: str
    run: str
    args: dict[str, Any] = Field(default_factory=dict)


class WorkflowSpec(BaseModel):
    schema_version: str = "1.0"
    name: str = ""
    target: dict[str, str] = Field(default_factory=dict)
    defaults: WorkflowDefaults = Field(default_factory=WorkflowDefaults)
    steps: list[WorkflowStep] = Field(default_factory=list)
