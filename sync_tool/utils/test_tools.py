"""Built-in sample data and test scenario utilities for the sync engine."""

from __future__ import annotations

import time
from pathlib import Path

from sync_tool.sync.engine import SyncEngine


def generate_test_data(base_path: str | Path) -> dict[str, str]:
    """Create sample test folders/files under base_path/test_data."""
    root = Path(base_path).resolve() / "test_data"
    folder_a = root / "folderA"
    folder_b = root / "folderB"
    folder_a.mkdir(parents=True, exist_ok=True)
    folder_b.mkdir(parents=True, exist_ok=True)

    (folder_a / "file1.txt").write_text("file1 from folderA\n", encoding="utf-8")
    (folder_a / "file2.txt").write_text("file2 from folderA\n", encoding="utf-8")
    (folder_b / "file2.txt").write_text("file2 from folderB (different content)\n", encoding="utf-8")
    (folder_b / "file3.txt").write_text("file3 from folderB\n", encoding="utf-8")

    return {"base": str(root), "folder_a": str(folder_a), "folder_b": str(folder_b)}


def _require_dirs(engine: SyncEngine) -> tuple[Path, Path]:
    cfg = engine.config_manager.get()
    if not cfg.dir_a or not cfg.dir_b:
        raise ValueError("Set folder paths before running built-in tests.")
    dir_a = Path(cfg.dir_a)
    dir_b = Path(cfg.dir_b)
    dir_a.mkdir(parents=True, exist_ok=True)
    dir_b.mkdir(parents=True, exist_ok=True)
    return dir_a, dir_b


def test_new_file_sync(engine: SyncEngine) -> dict[str, object]:
    """Create a new file in A, sync once, and return the result snapshot."""
    dir_a, dir_b = _require_dirs(engine)
    filename = f"new_file_{int(time.time() * 1000)}.txt"
    (dir_a / filename).write_text("new file from test_new_file_sync\n", encoding="utf-8")

    preview = [{"action": a.action, "path": a.path, "reason": a.reason} for a in engine.preview()]
    metrics = engine.run_once(confirm_mass_deletions=True)
    exists_in_b = (dir_b / filename).exists()

    return {"scenario": "new_file_sync", "file": filename, "preview": preview, "metrics": metrics.__dict__, "success": exists_in_b}


def test_conflict_case(engine: SyncEngine) -> dict[str, object]:
    """Force a conflict by changing same file in both folders, then sync."""
    dir_a, dir_b = _require_dirs(engine)
    filename = "conflict_case.txt"
    now = int(time.time())
    (dir_a / filename).write_text(f"A version {now}\n", encoding="utf-8")
    (dir_b / filename).write_text(f"B version {now}\n", encoding="utf-8")

    cfg = engine.config_manager.get()
    previous_strategy = cfg.conflict_strategy
    engine.config_manager.update(conflict_strategy="manual")
    try:
        preview = [{"action": a.action, "path": a.path, "reason": a.reason} for a in engine.preview()]
        metrics = engine.run_once(confirm_mass_deletions=True)
    finally:
        engine.config_manager.update(conflict_strategy=previous_strategy)

    return {
        "scenario": "conflict_case",
        "file": filename,
        "preview": preview,
        "conflicts": engine.last_conflicts,
        "metrics": metrics.__dict__,
        "success": filename in engine.last_conflicts or metrics.conflicts > 0,
    }


def test_deletion_sync(engine: SyncEngine) -> dict[str, object]:
    """Create and sync a file, then delete in A and sync deletion to B."""
    dir_a, dir_b = _require_dirs(engine)
    filename = "deletion_case.txt"
    path_a = dir_a / filename
    path_b = dir_b / filename

    path_a.write_text("seed file for deletion scenario\n", encoding="utf-8")
    engine.run_once(confirm_mass_deletions=True)

    if path_a.exists():
        path_a.unlink()

    preview = [{"action": a.action, "path": a.path, "reason": a.reason} for a in engine.preview()]
    metrics = engine.run_once(confirm_mass_deletions=True)

    return {
        "scenario": "deletion_sync",
        "file": filename,
        "preview": preview,
        "metrics": metrics.__dict__,
        "success": not path_b.exists(),
    }
