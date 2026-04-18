"""Directory scanning primitives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sync_tool.utils.hashing import file_sha256


@dataclass(slots=True)
class FileSnapshot:
    """Current state of a file in a directory."""

    relative_path: str
    absolute_path: Path
    mtime: float
    size: int
    hash_value: str | None


class DirectoryScanner:
    """Scan directories into normalized file snapshots."""

    def __init__(self, use_hash: bool = False) -> None:
        self.use_hash = use_hash

    def scan(self, root: Path) -> dict[str, FileSnapshot]:
        """Collect metadata for all files under a root path."""
        snapshots: dict[str, FileSnapshot] = {}
        if not root.exists():
            return snapshots

        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            rel = str(file_path.relative_to(root)).replace("\\", "/")
            stat = file_path.stat()
            digest = file_sha256(file_path) if self.use_hash else None
            snapshots[rel] = FileSnapshot(
                relative_path=rel,
                absolute_path=file_path,
                mtime=stat.st_mtime,
                size=stat.st_size,
                hash_value=digest,
            )
        return snapshots
