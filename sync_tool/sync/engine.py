"""Top-level synchronization engine orchestration."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict
from pathlib import Path

from sync_tool.sync.comparator import Comparator, SyncAction
from sync_tool.sync.executor import ActionExecutor, SyncMetrics
from sync_tool.sync.scanner import DirectoryScanner
from sync_tool.sync.state import SyncStateStore
from sync_tool.utils.config import ConfigManager
from sync_tool.utils.logger import get_logger


class SyncEngine:
    """Bidirectional folder sync engine with optional background loop."""

    def __init__(self) -> None:
        self.config_manager = ConfigManager()
        self.state_store = SyncStateStore()
        self.comparator = Comparator()
        self.executor = ActionExecutor()
        self.logger = get_logger()

        self._running = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        self.last_run_at: float | None = None
        self.last_metrics = SyncMetrics()
        self.last_changes: list[dict[str, str]] = []
        self.last_conflicts: list[str] = []

    def _roots(self) -> tuple[Path, Path]:
        cfg = self.config_manager.get()
        if not cfg.dir_a or not cfg.dir_b:
            raise ValueError("Both dir_a and dir_b must be configured before syncing.")
        return Path(cfg.dir_a), Path(cfg.dir_b)

    def preview(self) -> list[SyncAction]:
        """Return planned actions without executing them."""
        cfg = self.config_manager.get()
        dir_a, dir_b = self._roots()
        scanner = DirectoryScanner(use_hash=cfg.use_hash)
        snap_a = scanner.scan(dir_a)
        snap_b = scanner.scan(dir_b)
        previous = {path: self.state_store.get(path) for path in self.state_store.all_paths()}
        result = self.comparator.compare(snap_a, snap_b, previous)

        self.last_changes = [{"action": a.action, "path": a.path, "reason": a.reason} for a in result.actions]
        self.last_conflicts = result.conflicts
        return result.actions

    def run_once(self, confirm_mass_deletions: bool = False) -> SyncMetrics:
        """Execute one full synchronization cycle."""
        cfg = self.config_manager.get()
        dir_a, dir_b = self._roots()
        dir_a.mkdir(parents=True, exist_ok=True)
        dir_b.mkdir(parents=True, exist_ok=True)

        scanner = DirectoryScanner(use_hash=cfg.use_hash)
        snapshots_a = scanner.scan(dir_a)
        snapshots_b = scanner.scan(dir_b)
        previous = {path: self.state_store.get(path) for path in self.state_store.all_paths()}

        compare_result = self.comparator.compare(snapshots_a, snapshots_b, previous)
        self.last_changes = [
            {"action": action.action, "path": action.path, "reason": action.reason}
            for action in compare_result.actions
        ]
        self.last_conflicts = compare_result.conflicts

        metrics = self.executor.execute(
            actions=compare_result.actions,
            dir_a=dir_a,
            dir_b=dir_b,
            store=self.state_store,
            snapshots_a=snapshots_a,
            snapshots_b=snapshots_b,
            conflict_strategy=cfg.conflict_strategy,
            confirm_mass_deletions=confirm_mass_deletions,
            deletion_threshold=cfg.deletion_threshold,
            logger=self.logger,
        )

        self.last_metrics = metrics
        self.last_run_at = time.time()
        return metrics

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once(confirm_mass_deletions=False)
            except Exception as exc:  # noqa: BLE001
                self.logger.exception("sync cycle failed: %s", exc)
            cfg = self.config_manager.get()
            self._stop_event.wait(cfg.interval_seconds)

    def start(self) -> None:
        """Start background synchronization."""
        if self._running:
            return
        self._roots()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._running = True

    def stop(self) -> None:
        """Stop background synchronization."""
        if not self._running:
            return
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._running = False

    def status(self) -> dict[str, object]:
        """Return service status and latest run stats."""
        return {
            "state": "running" if self._running else "idle",
            "last_run": self.last_run_at,
            "metrics": asdict(self.last_metrics),
        }
