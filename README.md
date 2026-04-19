# Folder Sync Tool

A cross-platform, bidirectional folder synchronization service built in Python with a FastAPI wrapper.

It synchronizes two folders safely:

- **Folder A ⇄ Folder B**

The design follows a lightweight **rsync + git-merge hybrid** approach focused on correctness and data safety.

## 1. Project Overview

This project provides:

- A modular sync core (`sync_tool/sync`) for scanning, comparing, conflict detection, and execution.
- Persistent sync state (`.sync_state.json`) to track file history and prevent sync loops.
- A FastAPI REST layer (`sync_tool/api`) exposing sync controls, configuration, preview, and observability endpoints.

### Architecture

- `sync_tool/sync/scanner.py`: scans file metadata (mtime, optional hash)
- `sync_tool/sync/comparator.py`: computes actions and conflicts from snapshots + previous state
- `sync_tool/sync/executor.py`: applies copies/deletions/conflict actions in parallel
- `sync_tool/sync/state.py`: reads/writes `.sync_state.json`
- `sync_tool/sync/engine.py`: orchestrates one-shot and background sync loops
- `sync_tool/utils/*`: hashing, logging, and configuration persistence
- `sync_tool/api/*`: FastAPI models and route modules

## 2. Features

- Bidirectional sync (A → B and B → A)
- New file detection
- Modified file detection (timestamp + optional hash mode)
- Deletion propagation with safety threshold guard
- Conflict detection when both sides changed since last sync
- Conflict strategies:
  - `manual` (creates conflict files)
  - `prefer_a`
  - `prefer_b`
- Persistent state tracking in `.sync_state.json`
- ThreadPool-based parallel file operations
- Logging to `sync.log`
- FastAPI wrapper for external integrations (including UI platforms like Lovable)

## 3. Installation

```bash
pip install -r requirements.txt
```

## 4. Running the Server

```bash
uvicorn api.main:app --reload
```

> Compatibility entrypoint `api.main:app` forwards to `sync_tool.api.main:app`.

## 4.1 Running the App (Streamlit UI)

```bash
streamlit run app.py
```

---

## 4.2 How to Use (Step-by-step)

1. Set **Folder A path** and **Folder B path** in the Streamlit UI.
2. Click **Refresh Preview** to inspect planned changes before execution.
3. Click **Run One Sync** for one cycle, or **Start Continuous Sync** for background sync.
4. Review **Metrics**, **Conflict Panel**, and **Logs Panel** to monitor results.

---

## 4.3 Testing Tools (Built-in)

The Streamlit app includes built-in testing buttons:

- **Generate Sample Data**: creates `test_data/folderA` and `test_data/folderB` with sample files.
- **Run Test: New File**: creates a new file and verifies propagation.
- **Run Test: Conflict**: creates concurrent edits and exercises conflict handling.
- **Run Test: Deletion**: verifies deletion propagation behavior.

---

## 4.4 Troubleshooting

- **Invalid paths**: confirm both folders are absolute and accessible.
- **Permission errors**: check read/write permissions for both folders and project files.
- **Sync issues**: run **Refresh Preview**, review **Conflict Panel**, then inspect **Logs Panel** (`sync.log`).

## 5. 🔥 FULL API DOCUMENTATION

Base URL: `http://localhost:8000`

---

### POST `/sync/start`

**Description:** Start continuous background synchronization using configured interval.

**Request Body:** None

**Response Example:**

```json
{
  "message": "Synchronization started"
}
```

---

### POST `/sync/stop`

**Description:** Stop background synchronization.

**Request Body:** None

**Response Example:**

```json
{
  "message": "Synchronization stopped"
}
```

---

### GET `/sync/status`

**Description:** Get sync service status and latest metrics.

**Request Body:** None

**Response Example:**

```json
{
  "state": "running",
  "last_run": 1776500000.123,
  "metrics": {
    "files_synced": 10,
    "deletions": 2,
    "conflicts": 1,
    "last_sync_time": 1776500000.123
  }
}
```

---

### POST `/config`

**Description:** Set or update synchronization configuration.

**Request Body Example:**

```json
{
  "dir_a": "/absolute/path/to/folderA",
  "dir_b": "/absolute/path/to/folderB",
  "interval_seconds": 30,
  "use_hash": true,
  "conflict_strategy": "manual",
  "deletion_threshold": 0.3
}
```

**Response Example:**

```json
{
  "config": {
    "dir_a": "/absolute/path/to/folderA",
    "dir_b": "/absolute/path/to/folderB",
    "interval_seconds": 30,
    "use_hash": true,
    "conflict_strategy": "manual",
    "deletion_threshold": 0.3
  }
}
```

---

### GET `/config`

**Description:** Fetch current config.

**Request Body:** None

**Response Example:**

```json
{
  "config": {
    "dir_a": "/absolute/path/to/folderA",
    "dir_b": "/absolute/path/to/folderB",
    "interval_seconds": 30,
    "use_hash": false,
    "conflict_strategy": "manual",
    "deletion_threshold": 0.3
  }
}
```

---

### POST `/sync/run-once`

**Description:** Trigger exactly one synchronization cycle.

**Request Body Example:**

```json
{
  "confirm_mass_deletions": false
}
```

**Response Example:**

```json
{
  "message": "Sync cycle completed",
  "metrics": {
    "files_synced": 4,
    "deletions": 1,
    "conflicts": 0,
    "last_sync_time": 1776500000.123
  }
}
```

**Error (400) Example:**

```json
{
  "detail": "Deletion safety threshold exceeded: 45.00% > 30%. Set confirm_mass_deletions=true to proceed."
}
```

---

### GET `/sync/preview`

**Description:** Dry-run preview showing planned actions and detected conflicts.

**Request Body:** None

**Response Example:**

```json
{
  "changes": [
    {
      "action": "copy_a_to_b",
      "path": "docs/report.txt",
      "reason": "Only exists in A"
    },
    {
      "action": "conflict",
      "path": "notes/todo.md",
      "reason": "both sides changed"
    }
  ],
  "conflicts": [
    "notes/todo.md"
  ]
}
```

---

### GET `/changes`

**Description:** List most recently detected/planned changes.

**Request Body:** None

**Response Example:**

```json
{
  "changes": [
    {
      "action": "copy_b_to_a",
      "path": "img/logo.png",
      "reason": "B newer than last sync"
    }
  ]
}
```

---

### GET `/conflicts`

**Description:** List conflicts from latest preview/run.

**Request Body:** None

**Response Example:**

```json
{
  "conflicts": [
    "notes/todo.md"
  ]
}
```

---

### GET `/logs`

**Description:** Fetch recent log lines from `sync.log`.

**Query Params:**

- `lines` (optional, default `100`): number of lines from end of log file.

**Request Body:** None

**Response Example:**

```json
{
  "logs": [
    "2026-04-18 10:00:01,001 | INFO | sync_tool | copy A->B: docs/report.txt",
    "2026-04-18 10:00:01,120 | WARNING | sync_tool | conflict manual: notes/todo.md"
  ]
}
```

---

### GET `/metrics`

**Description:** Fetch latest sync metrics snapshot.

**Request Body:** None

**Response Example:**

```json
{
  "files_synced": 12,
  "deletions": 3,
  "conflicts": 1,
  "last_sync_time": 1776500000.123
}
```

## 6. Example Workflow

1. **Configure directories**

```bash
curl -X POST http://localhost:8000/config \
  -H "Content-Type: application/json" \
  -d '{
    "dir_a": "/data/folderA",
    "dir_b": "/data/folderB",
    "interval_seconds": 20,
    "use_hash": true,
    "conflict_strategy": "manual",
    "deletion_threshold": 0.3
  }'
```

2. **Preview changes (dry run)**

```bash
curl http://localhost:8000/sync/preview
```

3. **Run one sync cycle**

```bash
curl -X POST http://localhost:8000/sync/run-once \
  -H "Content-Type: application/json" \
  -d '{"confirm_mass_deletions": false}'
```

4. **Start continuous sync**

```bash
curl -X POST http://localhost:8000/sync/start
```

5. **Fetch logs**

```bash
curl "http://localhost:8000/logs?lines=50"
```

## 7. Sample Config

```json
{
  "dir_a": "/absolute/path/to/folderA",
  "dir_b": "/absolute/path/to/folderB",
  "interval_seconds": 30,
  "use_hash": false,
  "conflict_strategy": "manual",
  "deletion_threshold": 0.3
}
```

## 8. Future Improvements

- GUI integration support (including Lovable-centric workflows)
- Real-time sync mode using filesystem events (`watchdog`)
- Cloud sync connectors (S3/Drive/Dropbox abstractions)
