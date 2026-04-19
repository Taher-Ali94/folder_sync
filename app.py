from __future__ import annotations

import shutil
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import streamlit as st

from sync_tool.sync.engine import SyncEngine
from sync_tool.sync.scanner import DirectoryScanner
from sync_tool.utils.test_tools import (
    generate_test_data,
    test_conflict_case,
    test_deletion_sync,
    test_new_file_sync,
)


def _engine() -> SyncEngine:
    if "engine" not in st.session_state:
        st.session_state.engine = SyncEngine()
    return st.session_state.engine


def _safe_read_logs(lines: int = 200) -> list[str]:
    path = Path("sync.log")
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()[-max(lines, 1) :]


def _direction(action: str) -> str:
    mapping = {
        "copy_a_to_b": "A → B",
        "copy_b_to_a": "B → A",
        "delete_a": "B → A",
        "delete_b": "A → B",
        "conflict": "A ⇄ B",
        "state_cleanup": "-",
    }
    return mapping.get(action, "-")


def _ensure_config(engine: SyncEngine, dir_a: str, dir_b: str, strategy: str) -> None:
    engine.config_manager.update(
        dir_a=dir_a.strip(),
        dir_b=dir_b.strip(),
        conflict_strategy=strategy,
    )


def _run_sync(engine: SyncEngine, dry_run: bool, enable_delete_sync: bool) -> dict[str, object]:
    started = time.perf_counter()
    if dry_run:
        actions = engine.preview()
        st.session_state.last_sync_duration = time.perf_counter() - started
        return {"dry_run": True, "actions": [{"action": a.action, "path": a.path, "reason": a.reason} for a in actions]}

    if enable_delete_sync:
        metrics = engine.run_once(confirm_mass_deletions=True)
        st.session_state.last_sync_duration = time.perf_counter() - started
        return {"dry_run": False, "metrics": asdict(metrics)}

    cfg = engine.config_manager.get()
    dir_a = Path(cfg.dir_a)
    dir_b = Path(cfg.dir_b)
    scanner = DirectoryScanner(use_hash=cfg.use_hash)
    snap_a = scanner.scan(dir_a)
    snap_b = scanner.scan(dir_b)
    previous = {path: engine.state_store.get(path) for path in engine.state_store.all_paths()}
    compare = engine.comparator.compare(snap_a, snap_b, previous)
    filtered = [a for a in compare.actions if a.action not in {"delete_a", "delete_b"}]
    engine.last_changes = [{"action": a.action, "path": a.path, "reason": a.reason} for a in filtered]
    engine.last_conflicts = compare.conflicts
    metrics = engine.executor.execute(
        actions=filtered,
        dir_a=dir_a,
        dir_b=dir_b,
        store=engine.state_store,
        snapshots_a=snap_a,
        snapshots_b=snap_b,
        conflict_strategy=cfg.conflict_strategy,
        confirm_mass_deletions=True,
        deletion_threshold=1.0,
        logger=engine.logger,
    )
    engine.last_metrics = metrics
    engine.last_run_at = time.time()
    st.session_state.last_sync_duration = time.perf_counter() - started
    return {"dry_run": False, "metrics": asdict(metrics), "deletions_skipped": True}


def _resolve_conflict(path: str, prefer: str, engine: SyncEngine) -> None:
    cfg = engine.config_manager.get()
    if not cfg.dir_a or not cfg.dir_b:
        raise ValueError("Set folder paths first.")
    a_path = Path(cfg.dir_a) / path
    b_path = Path(cfg.dir_b) / path
    if prefer == "A":
        b_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(a_path, b_path)
    else:
        a_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(b_path, a_path)
    engine.logger.warning("conflict resolved in UI prefer_%s: %s", prefer.lower(), path)


def main() -> None:
    st.set_page_config(page_title="Folder Sync Tool", layout="wide")
    engine = _engine()

    cfg = engine.config_manager.get()
    status = engine.status()
    last_run = status.get("last_run")
    last_run_label = datetime.fromtimestamp(last_run).strftime("%Y-%m-%d %H:%M:%S") if last_run else "Never"
    st.title("Folder Sync Tool")
    c1, c2 = st.columns(2)
    c1.metric("Status", "Running" if status.get("state") == "running" else "Idle")
    c2.metric("Last sync time", last_run_label)

    st.subheader("Folder Selection")
    dir_col1, dir_col2, sample_col = st.columns([2, 2, 1])
    folder_a = dir_col1.text_input("Folder A path", value=st.session_state.get("folder_a", cfg.dir_a))
    folder_b = dir_col2.text_input("Folder B path", value=st.session_state.get("folder_b", cfg.dir_b))
    if sample_col.button("Load Sample Test Folders", use_container_width=True):
        sample = generate_test_data(Path.cwd())
        folder_a = sample["folder_a"]
        folder_b = sample["folder_b"]
        st.session_state.folder_a = folder_a
        st.session_state.folder_b = folder_b
        st.success(f"Loaded sample folders: {sample['base']}")

    st.subheader("Options")
    o1, o2, o3 = st.columns(3)
    dry_run = o1.checkbox("Dry Run", value=st.session_state.get("dry_run", True))
    enable_delete_sync = o2.checkbox("Enable Delete Sync", value=st.session_state.get("enable_delete_sync", True))
    strategy_label = o3.selectbox("Conflict Strategy", ["Prefer A", "Prefer B", "Manual"], index=2)
    strategy = {"Prefer A": "prefer_a", "Prefer B": "prefer_b", "Manual": "manual"}[strategy_label]

    st.subheader("Controls")
    b1, b2, b3 = st.columns(3)
    if b1.button("Run One Sync", use_container_width=True):
        try:
            _ensure_config(engine, folder_a, folder_b, strategy)
            with st.spinner("Running sync..."):
                result = _run_sync(engine, dry_run=dry_run, enable_delete_sync=enable_delete_sync)
            if result.get("dry_run"):
                st.info("Dry run completed. See Preview Panel.")
            else:
                msg = "Sync completed."
                if result.get("deletions_skipped"):
                    msg += " Deletion actions were skipped."
                st.success(msg)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Sync failed: {exc}")

    if b2.button("Start Continuous Sync", use_container_width=True):
        try:
            _ensure_config(engine, folder_a, folder_b, strategy)
            engine.start()
            st.success("Continuous sync started.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to start continuous sync: {exc}")

    if b3.button("Stop Sync", use_container_width=True):
        engine.stop()
        st.info("Sync stopped.")

    st.subheader("Built-in Testing Tools")
    t1, t2, t3, t4 = st.columns(4)
    if t1.button("Generate Sample Data", use_container_width=True):
        try:
            sample = generate_test_data(Path.cwd())
            st.success(f"Created sample data at {sample['base']}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to generate sample data: {exc}")
    if t2.button("Run Test: New File", use_container_width=True):
        try:
            _ensure_config(engine, folder_a, folder_b, strategy)
            st.json(test_new_file_sync(engine))
        except Exception as exc:  # noqa: BLE001
            st.error(f"New file test failed: {exc}")
    if t3.button("Run Test: Conflict", use_container_width=True):
        try:
            _ensure_config(engine, folder_a, folder_b, strategy)
            st.json(test_conflict_case(engine))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Conflict test failed: {exc}")
    if t4.button("Run Test: Deletion", use_container_width=True):
        try:
            _ensure_config(engine, folder_a, folder_b, strategy)
            st.json(test_deletion_sync(engine))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Deletion test failed: {exc}")

    st.subheader("Metrics")
    latest = engine.status().get("metrics", {})
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Files synced", latest.get("files_synced", 0))
    m2.metric("Conflicts", latest.get("conflicts", 0))
    m3.metric("Deleted files", latest.get("deletions", 0))
    m4.metric("Last sync duration (s)", f"{st.session_state.get('last_sync_duration', 0.0):.3f}")

    st.subheader("Preview Panel")
    if st.button("Refresh Preview"):
        try:
            _ensure_config(engine, folder_a, folder_b, strategy)
            engine.preview()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Preview failed: {exc}")
    preview_rows = [
        {"File": c["path"], "Action": c["action"], "Direction": _direction(c["action"])}
        for c in engine.last_changes
    ]
    st.dataframe(preview_rows, use_container_width=True)

    st.subheader("Conflict Panel")
    if not engine.last_conflicts:
        st.info("No conflicts detected.")
    else:
        for rel in engine.last_conflicts:
            cc1, cc2, cc3 = st.columns([3, 1, 1])
            cc1.write(rel)
            if cc2.button("Prefer A", key=f"prefer_a_{rel}"):
                try:
                    _resolve_conflict(rel, "A", engine)
                    st.success(f"Resolved {rel} with Prefer A")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Resolution failed: {exc}")
            if cc3.button("Prefer B", key=f"prefer_b_{rel}"):
                try:
                    _resolve_conflict(rel, "B", engine)
                    st.success(f"Resolved {rel} with Prefer B")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Resolution failed: {exc}")

    st.subheader("Logs Panel")
    auto_refresh_logs = st.checkbox("Auto-refresh logs", value=True)
    refresh_seconds = st.slider("Log refresh interval (seconds)", min_value=2, max_value=30, value=5)
    if auto_refresh_logs:
        st.markdown(f"<meta http-equiv='refresh' content='{refresh_seconds}'>", unsafe_allow_html=True)
    st.text_area("Recent logs", value="\n".join(_safe_read_logs(300)), height=220)

    st.subheader("How to Use This Tool")
    st.markdown(
        "1. Select **Folder A** and **Folder B** paths.\n"
        "2. Click **Refresh Preview** to see planned changes.\n"
        "3. Click **Run One Sync** (or start continuous sync).\n"
        "4. Monitor **Metrics**, **Conflict Panel**, and **Logs Panel**."
    )


if __name__ == "__main__":
    main()
