"""Configuration routes."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from sync_tool.api.models.schemas import ConfigPayload
from sync_tool.sync.engine import SyncEngine


def build_router(engine: SyncEngine) -> APIRouter:
    """Build config router with engine dependency closure."""
    router = APIRouter(tags=["configuration"])

    @router.post("/config")
    async def set_config(payload: ConfigPayload) -> dict[str, object]:
        cfg = engine.config_manager.update(**payload.model_dump())
        return {"config": asdict(cfg)}

    @router.get("/config")
    async def get_config() -> dict[str, object]:
        return {"config": asdict(engine.config_manager.get())}

    return router
