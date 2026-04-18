"""Pydantic request/response models for API contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ConfigPayload(BaseModel):
    """Config update payload."""

    dir_a: str
    dir_b: str
    interval_seconds: int = Field(default=30, ge=1)
    use_hash: bool = False
    conflict_strategy: Literal["manual", "prefer_a", "prefer_b"] = "manual"
    deletion_threshold: float = Field(default=0.30, ge=0.0, le=1.0)


class SyncRunRequest(BaseModel):
    """Single-run trigger payload."""

    confirm_mass_deletions: bool = False


class StatusResponse(BaseModel):
    """Status endpoint response."""

    state: str
    last_run: float | None
    metrics: dict[str, object]


class MessageResponse(BaseModel):
    """Standard message response."""

    message: str


class ChangeItem(BaseModel):
    """Change list item."""

    action: str
    path: str
    reason: str


class MetricsResponse(BaseModel):
    """Metrics endpoint response."""

    files_synced: int
    deletions: int
    conflicts: int
    last_sync_time: float | None
