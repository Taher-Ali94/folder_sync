"""Conflict file handling utilities."""

from __future__ import annotations

import shutil
from pathlib import Path


def conflict_name(path: Path, source_label: str) -> Path:
    """Build renamed conflict file path."""
    suffix = f".conflict-{source_label}"
    if path.suffix:
        return path.with_name(f"{path.stem}{suffix}{path.suffix}")
    return path.with_name(f"{path.name}{suffix}")


def materialize_conflict(file_a: Path, file_b: Path) -> tuple[Path, Path]:
    """Write conflict files for both versions and preserve originals."""
    out_a = conflict_name(file_a, "A")
    out_b = conflict_name(file_b, "B")
    out_a.parent.mkdir(parents=True, exist_ok=True)
    out_b.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file_a, out_a)
    shutil.copy2(file_b, out_b)
    return out_a, out_b
