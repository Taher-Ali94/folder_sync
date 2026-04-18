"""Persistent synchronization state tracking."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class TrackedFileState:
    """Last known sync metadata for a file."""

    path: str
    a_mtime: float | None = None
    b_mtime: float | None = None
    a_hash: str | None = None
    b_hash: str | None = None
    last_sync_timestamp: float | None = None


class SyncStateStore:
    """Manages read/write operations for .sync_state.json."""

    def __init__(self, state_file: Path | None = None) -> None:
        self.state_file = state_file or Path(".sync_state.json")
        self._files: dict[str, TrackedFileState] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_file.exists():
            self._files = {}
            return
        with self.state_file.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        files = raw.get("files", {})
        self._files = {path: TrackedFileState(**payload) for path, payload in files.items()}

    def save(self) -> None:
        """Persist current state to file."""
        payload = {"files": {path: asdict(data) for path, data in self._files.items()}}
        self.state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get(self, relative_path: str) -> TrackedFileState | None:
        """Get tracked data for a path."""
        return self._files.get(relative_path)

    def upsert(self, state: TrackedFileState) -> None:
        """Insert or update tracked metadata."""
        self._files[state.path] = state

    def remove(self, relative_path: str) -> None:
        """Delete tracked metadata for a removed file."""
        self._files.pop(relative_path, None)

    def all_paths(self) -> set[str]:
        """Return all tracked paths."""
        return set(self._files.keys())
