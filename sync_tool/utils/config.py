"""Configuration helpers for the synchronization service."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class SyncConfig:
    """Runtime configuration for synchronization."""

    dir_a: str = ""
    dir_b: str = ""
    interval_seconds: int = 30
    use_hash: bool = False
    conflict_strategy: str = "manual"  # manual | prefer_a | prefer_b
    deletion_threshold: float = 0.30


class ConfigManager:
    """Persistent storage for synchronization settings."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("sync_config.json")
        self._config = self._load_or_default()

    def _load_or_default(self) -> SyncConfig:
        if not self.path.exists():
            return SyncConfig()
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return SyncConfig(**data)

    def get(self) -> SyncConfig:
        """Return current config."""
        return self._config

    def update(self, **changes: object) -> SyncConfig:
        """Update config values and persist."""
        payload = asdict(self._config)
        payload.update(changes)
        self._config = SyncConfig(**payload)
        self.save()
        return self._config

    def save(self) -> None:
        """Persist config to disk."""
        self.path.write_text(json.dumps(asdict(self._config), indent=2), encoding="utf-8")
