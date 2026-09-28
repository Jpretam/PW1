"""
Experiment logging module for M8.
Saves experiment-level records to CSV (m8_experiments.csv) and detailed event telemetry to JSONL (m8_events.jsonl).
"""

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.evaluation.models import ExperimentRecord

# Default data directory relative to backend root
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CSV_FILENAME = "m8_experiments.csv"
JSONL_FILENAME = "m8_events.jsonl"

_log_lock = Lock()

CSV_FIELDNAMES = [
    "experiment_id",
    "bug_id",
    "mode",
    "language",
    "model",
    "llm_calls",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "curator_input_tokens",
    "curator_output_tokens",
    "curator_total_tokens",
    "debugger_input_tokens",
    "debugger_output_tokens",
    "debugger_total_tokens",
    "mcp_calls",
    "context_size",
    "context_reduction_percent",
    "llm_time_ms",
    "mcp_query_time_ms",
    "mcp_transport_time_ms",
    "mcp_time_ms",
    "total_curation_time_ms",
    "total_debugging_time_ms",
    "total_time_ms",
    "root_cause_identified",
    "fix_generated",
    "fix_correct",
    "re_execution_passed",
    "stop_reason",
    "timestamp",
]


class ExperimentLogger:
    def __init__(self, data_dir: Path | str | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.csv_path = self.data_dir / CSV_FILENAME
        self.jsonl_path = self.data_dir / JSONL_FILENAME
        self._ensure_files()

    def _ensure_files(self) -> None:
        """Create directory and CSV header if not already present."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            with open(self.csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                writer.writeheader()

    def log_experiment(self, record: ExperimentRecord, detailed_events: list[dict[str, Any]] | None = None) -> None:
        """
        Record a completed experiment run to CSV and JSONL.
        """
        with _log_lock:
            # 1. Append row to CSV
            row = record.model_dump()
            with open(self.csv_path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                writer.writerow(row)

            # 2. Append detailed events to JSONL
            event_entry = {
                "experiment_id": record.experiment_id,
                "timestamp": record.timestamp or datetime.now(timezone.utc).isoformat(),
                "summary": row,
                "events": detailed_events or [],
            }
            with open(self.jsonl_path, mode="a", encoding="utf-8") as f:
                f.write(json.dumps(event_entry) + "\n")

    def get_experiments(self, limit: int = 50) -> list[ExperimentRecord]:
        """
        Read recent experiment records from CSV.
        """
        if not self.csv_path.exists():
            return []

        records: list[ExperimentRecord] = []
        with _log_lock:
            try:
                with open(self.csv_path, mode="r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Cast types appropriately
                        converted = {
                            "experiment_id": row.get("experiment_id", ""),
                            "bug_id": row.get("bug_id", ""),
                            "mode": row.get("mode", ""),
                            "language": row.get("language", ""),
                            "model": row.get("model", ""),
                            "llm_calls": int(row.get("llm_calls") or 0),
                            "input_tokens": int(row.get("input_tokens") or 0),
                            "output_tokens": int(row.get("output_tokens") or 0),
                            "total_tokens": int(row.get("total_tokens") or 0),
                            "curator_input_tokens": int(row.get("curator_input_tokens") or 0),
                            "curator_output_tokens": int(row.get("curator_output_tokens") or 0),
                            "curator_total_tokens": int(row.get("curator_total_tokens") or 0),
                            "debugger_input_tokens": int(row.get("debugger_input_tokens") or 0),
                            "debugger_output_tokens": int(row.get("debugger_output_tokens") or 0),
                            "debugger_total_tokens": int(row.get("debugger_total_tokens") or 0),
                            "mcp_calls": int(row.get("mcp_calls") or 0),
                            "context_size": int(row.get("context_size") or 0),
                            "context_reduction_percent": float(row.get("context_reduction_percent") or 0.0),
                            "llm_time_ms": float(row.get("llm_time_ms") or 0.0),
                            "mcp_query_time_ms": float(row.get("mcp_query_time_ms") or 0.0),
                            "mcp_transport_time_ms": float(row.get("mcp_transport_time_ms") or 0.0),
                            "mcp_time_ms": float(row.get("mcp_time_ms") or 0.0),
                            "total_curation_time_ms": float(row.get("total_curation_time_ms") or 0.0),
                            "total_debugging_time_ms": float(row.get("total_debugging_time_ms") or 0.0),
                            "total_time_ms": float(row.get("total_time_ms") or 0.0),
                            "root_cause_identified": str(row.get("root_cause_identified", "")).lower() == "true",
                            "fix_generated": str(row.get("fix_generated", "")).lower() == "true",
                            "fix_correct": str(row.get("fix_correct", "")).lower() == "true",
                            "re_execution_passed": str(row.get("re_execution_passed", "")).lower() == "true",
                            "stop_reason": row.get("stop_reason", ""),
                            "timestamp": row.get("timestamp", ""),
                        }
                        records.append(ExperimentRecord(**converted))
            except Exception:
                return []

        return list(reversed(records))[:limit]

    def get_latest_baseline(self, bug_id: str) -> ExperimentRecord | None:
        """
        Find the most recent baseline run for a specific bug_id.
        """
        experiments = self.get_experiments(limit=100)
        for exp in experiments:
            if exp.bug_id.upper() == bug_id.upper() and exp.mode == "baseline":
                return exp
        return None


# Global singleton instance
logger = ExperimentLogger()
