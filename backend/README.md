# PW1 - Backend Service

FastAPI execution engine for Python and Java code running inside isolated Docker containers.

## Features
- `POST /execute` endpoint accepting code payload for Python or Java.
- Docker-based sandboxed execution (memory limit, CPU limits, no network access).
- Structured JSON response (`status`, `stdout`, `stderr`, `exit_code`, `execution_time`).

## Quick Start

### 1. Install Dependencies
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Build Docker Executor Images
```bash
docker build -t runtime-debugger-python ./docker/python
docker build -t runtime-debugger-java ./docker/java
```

### 3. Run FastAPI Server
```bash
uvicorn app.main:app --reload --port 8000
```

## Logging Architecture & Retention Policy

PW1 strictly enforces separation of concerns across three categories:

| Category | Destination | Purpose | Retention Policy |
| :--- | :--- | :--- | :--- |
| **Category A: Application Runtime Log** | `backend/logs/app.log` | Server lifecycle (startup/shutdown), unhandled 500 exceptions, curation summaries | Auto-rotated via `RotatingFileHandler` (5 MB max size, 3 backup rotations: `app.log.1`, `app.log.2`, `app.log.3`). Ignored by git. |
| **Category B: Experiment Telemetry** | `backend/data/m8/experiments/<eval_id>/` and `backend/data/m8/m8_events.jsonl` | Structured JSONL telemetry events capturing M7/M8 curation and debugging lifecycle steps | Permanent per-evaluation run directory containing `events.jsonl`, `summary.json`, `baseline.json`, and `dynamic.json`. Global `m8_events.jsonl` provides research event stream. |
| **Category C: Evaluation Dataset** | `backend/data/m8/m8_experiments.csv` | Canonical research evaluation dataset pairing baseline vs dynamic runs | Append-only master CSV. Single source of truth consumed by analysis scripts and UI. Backed up prior to multi-run batch executions. |

