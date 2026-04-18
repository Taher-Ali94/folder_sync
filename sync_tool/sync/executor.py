"""Execution of file sync actions."""

from __future__ import annotations

import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from sync_tool.sync.comparator import SyncAction
from sync_tool.sync.conflict import materialize_conflict
from sync_tool.sync.scanner import FileSnapshot
from sync_tool.sync.state import SyncStateStore, TrackedFileState


@dataclass(slots=True)
class SyncMetrics:
    """Counters and metadata from a sync run."""

    files_synced: int = 0
    deletions: int = 0
    conflicts: int = 0
    last_sync_time: float | None = None


class ActionExecutor:
    """Apply sync actions in parallel using a thread pool."""

    def __init__(self, workers: int = 4) -> None:
        self.workers = workers

    @staticmethod
    def _copy(src: Path, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    @staticmethod
    def _delete(path: Path) -> None:
        if path.exists() and path.is_file():
            path.unlink()

    def execute(
        self,
        actions: list[SyncAction],
        dir_a: Path,
        dir_b: Path,
        store: SyncStateStore,
        snapshots_a: dict[str, FileSnapshot],
        snapshots_b: dict[str, FileSnapshot],
        conflict_strategy: str,
        confirm_mass_deletions: bool,
        deletion_threshold: float,
        logger,
    ) -> SyncMetrics:
        """Execute action list and update persisted state."""
        metrics = SyncMetrics(last_sync_time=time.time())

        deletion_actions = [a for a in actions if a.action in {"delete_a", "delete_b"}]
        tracked_total = max(len(store.all_paths()), 1)
        deletion_ratio = len(deletion_actions) / tracked_total
        if deletion_ratio > deletion_threshold and not confirm_mass_deletions:
            raise ValueError(
                f"Deletion safety threshold exceeded: {deletion_ratio:.2%} > {deletion_threshold:.0%}. "
                "Set confirm_mass_deletions=true to proceed."
            )

        def run(action: SyncAction) -> None:
            if action.action == "copy_a_to_b":
                src = dir_a / action.path
                dst = dir_b / action.path
                self._copy(src, dst)
                logger.info("copy A->B: %s", action.path)
            elif action.action == "copy_b_to_a":
                src = dir_b / action.path
                dst = dir_a / action.path
                self._copy(src, dst)
                logger.info("copy B->A: %s", action.path)
            elif action.action == "delete_a":
                self._delete(dir_a / action.path)
                logger.info("delete A: %s", action.path)
            elif action.action == "delete_b":
                self._delete(dir_b / action.path)
                logger.info("delete B: %s", action.path)
            elif action.action == "conflict":
                if conflict_strategy == "prefer_a":
                    self._copy(dir_a / action.path, dir_b / action.path)
                    logger.warning("conflict resolved prefer_a: %s", action.path)
                elif conflict_strategy == "prefer_b":
                    self._copy(dir_b / action.path, dir_a / action.path)
                    logger.warning("conflict resolved prefer_b: %s", action.path)
                else:
                    materialize_conflict(dir_a / action.path, dir_b / action.path)
                    logger.warning("conflict manual: %s", action.path)
            elif action.action == "state_cleanup":
                logger.info("state cleanup: %s", action.path)
            else:
                logger.warning("unknown action ignored: %s", action.action)

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = [pool.submit(run, action) for action in actions]
            for future in futures:
                future.result()

        for action in actions:
            rel = action.path
            if action.action in {"copy_a_to_b", "copy_b_to_a", "conflict"}:
                metrics.files_synced += 1
            if action.action in {"delete_a", "delete_b"}:
                metrics.deletions += 1
            if action.action == "conflict":
                metrics.conflicts += 1

            if action.action == "state_cleanup":
                store.remove(rel)
                continue

            a_path = dir_a / rel
            b_path = dir_b / rel
            a_stat = a_path.stat() if a_path.exists() else None
            b_stat = b_path.stat() if b_path.exists() else None

            store.upsert(
                TrackedFileState(
                    path=rel,
                    a_mtime=a_stat.st_mtime if a_stat else None,
                    b_mtime=b_stat.st_mtime if b_stat else None,
                    a_hash=snapshots_a.get(rel).hash_value if snapshots_a.get(rel) else None,
                    b_hash=snapshots_b.get(rel).hash_value if snapshots_b.get(rel) else None,
                    last_sync_timestamp=metrics.last_sync_time,
                )
            )

        store.save()
        return metrics
