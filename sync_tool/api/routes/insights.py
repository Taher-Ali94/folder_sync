"""Changes, conflicts, logs, and metrics routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from sync_tool.api.models.schemas import MetricsResponse
from sync_tool.sync.engine import SyncEngine


def build_router(engine: SyncEngine) -> APIRouter:
    """Build insights router."""
    router = APIRouter(tags=["insights"])

    @router.get("/changes")
    async def changes() -> dict[str, object]:
        return {"changes": engine.last_changes}

    @router.get("/conflicts")
    async def conflicts() -> dict[str, object]:
        return {"conflicts": engine.last_conflicts}

    @router.get("/logs")
    async def logs(lines: int = 100) -> dict[str, object]:
        log_path = Path("sync.log")
        if not log_path.exists():
            return {"logs": []}
        content = log_path.read_text(encoding="utf-8").splitlines()
        return {"logs": content[-max(lines, 1):]}

    @router.get("/metrics", response_model=MetricsResponse)
    async def metrics() -> MetricsResponse:
        return MetricsResponse(**engine.last_metrics.__dict__)

    return router
