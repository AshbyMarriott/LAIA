"""Single-call schema for Phase 3 pipeline bakeoff."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from laia.schemas.assistant import CommandName


class SingleCallResult(BaseModel):
    """One-shot classify + slot fill for bakeoff comparison."""

    command: CommandName
    args: dict[str, Any] = Field(default_factory=dict)
