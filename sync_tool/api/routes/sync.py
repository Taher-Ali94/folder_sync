"""Synchronization control and operations routes."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from sync_tool.api.models.schemas import MessageResponse, StatusResponse, SyncRunRequest
from sync_tool.sync.engine import SyncEngine


def build_router(engine: SyncEngine) -> APIRouter:
    """Build synchronization router."""
    router = APIRouter(tags=["sync"])

    @router.post("/sync/start", response_model=MessageResponse)
    async def start_sync() -> MessageResponse:
        try:
            engine.start()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return MessageResponse(message="Synchronization started")

    @router.post("/sync/stop", response_model=MessageResponse)
    async def stop_sync() -> MessageResponse:
        engine.stop()
        return MessageResponse(message="Synchronization stopped")

    @router.get("/sync/status", response_model=StatusResponse)
    async def status() -> StatusResponse:
        return StatusResponse(**engine.status())

    @router.post("/sync/run-once")
    async def run_once(payload: SyncRunRequest) -> dict[str, object]:
        try:
            result = engine.run_once(confirm_mass_deletions=payload.confirm_mass_deletions)
            return {"message": "Sync cycle completed", "metrics": asdict(result)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/sync/preview")
    async def preview() -> dict[str, object]:
        try:
            actions = engine.preview()
            return {
                "changes": [{"action": item.action, "path": item.path, "reason": item.reason} for item in actions],
                "conflicts": engine.last_conflicts,
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
