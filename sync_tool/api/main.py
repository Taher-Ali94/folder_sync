"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from sync_tool.api.routes import config as config_routes
from sync_tool.api.routes import insights as insights_routes
from sync_tool.api.routes import sync as sync_routes
from sync_tool.sync.engine import SyncEngine

app = FastAPI(title="Folder Sync API", version="1.0.0")
engine = SyncEngine()

app.include_router(config_routes.build_router(engine))
app.include_router(sync_routes.build_router(engine))
app.include_router(insights_routes.build_router(engine))
