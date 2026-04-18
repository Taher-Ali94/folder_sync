"""Hashing utilities for file synchronization."""

from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA256 hash for a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()
