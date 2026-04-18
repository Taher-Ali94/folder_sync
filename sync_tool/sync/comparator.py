"""Comparison logic to derive sync actions."""

from __future__ import annotations

import time
from dataclasses import dataclass

from sync_tool.sync.scanner import FileSnapshot
from sync_tool.sync.state import TrackedFileState


@dataclass(slots=True)
class SyncAction:
    """Planned action for a file during sync."""

    action: str
    path: str
    reason: str


@dataclass(slots=True)
class CompareResult:
    """Result object containing calculated actions and conflicts."""

    actions: list[SyncAction]
    conflicts: list[str]


def _changed(snapshot: FileSnapshot | None, previous_mtime: float | None, previous_hash: str | None) -> bool:
    if snapshot is None:
        return previous_mtime is not None
    if previous_mtime is None:
        return True
    if snapshot.mtime != previous_mtime:
        return True
    if snapshot.hash_value is not None and previous_hash is not None and snapshot.hash_value != previous_hash:
        return True
    return False


class Comparator:
    """Decide synchronization actions from two directory snapshots and state."""

    def compare(
        self,
        files_a: dict[str, FileSnapshot],
        files_b: dict[str, FileSnapshot],
        previous: dict[str, TrackedFileState],
    ) -> CompareResult:
        """Generate action list and conflicts."""
        all_paths = set(files_a.keys()) | set(files_b.keys()) | set(previous.keys())
        actions: list[SyncAction] = []
        conflicts: list[str] = []
        _ = time.time()

        for rel in sorted(all_paths):
            a = files_a.get(rel)
            b = files_b.get(rel)
            state = previous.get(rel)

            prev_a_mtime = state.a_mtime if state else None
            prev_b_mtime = state.b_mtime if state else None
            prev_a_hash = state.a_hash if state else None
            prev_b_hash = state.b_hash if state else None

            changed_a = _changed(a, prev_a_mtime, prev_a_hash)
            changed_b = _changed(b, prev_b_mtime, prev_b_hash)

            if a and b:
                if changed_a and changed_b:
                    if a.mtime != b.mtime or (a.hash_value is not None and b.hash_value is not None and a.hash_value != b.hash_value):
                        conflicts.append(rel)
                        actions.append(SyncAction(action="conflict", path=rel, reason="both sides changed"))
                    continue
                if changed_a and not changed_b:
                    actions.append(SyncAction(action="copy_a_to_b", path=rel, reason="A newer than last sync"))
                    continue
                if changed_b and not changed_a:
                    actions.append(SyncAction(action="copy_b_to_a", path=rel, reason="B newer than last sync"))
                    continue
                if a.mtime > b.mtime:
                    actions.append(SyncAction(action="copy_a_to_b", path=rel, reason="A timestamp newer"))
                elif b.mtime > a.mtime:
                    actions.append(SyncAction(action="copy_b_to_a", path=rel, reason="B timestamp newer"))
                continue

            if a and not b:
                if state and prev_b_mtime is not None:
                    actions.append(SyncAction(action="delete_a", path=rel, reason="Deleted in B"))
                else:
                    actions.append(SyncAction(action="copy_a_to_b", path=rel, reason="Only exists in A"))
                continue

            if b and not a:
                if state and prev_a_mtime is not None:
                    actions.append(SyncAction(action="delete_b", path=rel, reason="Deleted in A"))
                else:
                    actions.append(SyncAction(action="copy_b_to_a", path=rel, reason="Only exists in B"))
                continue

            if state:
                actions.append(SyncAction(action="state_cleanup", path=rel, reason="Missing from both roots"))

        return CompareResult(actions=actions, conflicts=conflicts)
