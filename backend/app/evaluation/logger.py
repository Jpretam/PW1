"""
Experiment logging module for M8.
Saves experiment-level records to CSV (m8_experiments.csv) and detailed event telemetry to JSONL (m8_events.jsonl).
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Optional

from app.evaluation.models import ExperimentRecord

# Default data directory relative to backend root
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CSV_FILENAME = "m8_experiments.csv"
JSONL_FILENAME = "m8_events.jsonl"

_log_lock = Lock()

CSV_FIELDNAMES = [
    "evaluation_id",
    "experiment_id",
    "bug_id",
    "mode",
    "language",
    "model",
    "context_chars",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "token_usage_available",
    "curator_input_tokens",
    "curator_output_tokens",
    "curator_total_tokens",
    "debugger_input_tokens",
    "debugger_output_tokens",
    "debugger_total_tokens",
    "llm_calls",
    "mcp_calls",
    "mcp_query_time_ms",
    "mcp_transport_time_ms",
    "mcp_total_time_ms",
    "llm_time_ms",
    "total_experiment_time_ms",
    "root_cause_identified",
    "fix_generated",
    "fix_correct",
    "re_execution_passed",
    "stop_reason",
    "status",
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
            # 1. Format row for CSV
            raw_dict = record.model_dump()
            csv_row: dict[str, Any] = {}
            for field in CSV_FIELDNAMES:
                val = raw_dict.get(field)
                if val is None:
                    csv_row[field] = ""
                elif isinstance(val, bool):
                    csv_row[field] = "True" if val else "False"
                else:
                    csv_row[field] = str(val)

            with open(self.csv_path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                writer.writerow(csv_row)

            # 2. Append detailed events to JSONL
            event_entry = {
                "evaluation_id": record.evaluation_id,
                "experiment_id": record.experiment_id,
                "timestamp": record.timestamp or datetime.now(timezone.utc).isoformat(),
                "summary": raw_dict,
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
                        def parse_opt_int(val: Any) -> Optional[int]:
                            if val is not None and str(val).strip() != "":
                                try:
                                    return int(val)
                                except ValueError:
                                    return None
                            return None

                        def parse_opt_float(val: Any, default: float = 0.0) -> float:
                            if val is not None and str(val).strip() != "":
                                try:
                                    return float(val)
                                except ValueError:
                                    return default
                            return default

                        ctx_chars = int(row.get("context_chars") or row.get("context_size") or 0)
                        usage_avail = str(row.get("token_usage_available", "")).lower() == "true"
                        mcp_tot_time = parse_opt_float(row.get("mcp_total_time_ms") or row.get("mcp_time_ms"))
                        exp_tot_time = parse_opt_float(row.get("total_experiment_time_ms") or row.get("total_time_ms"))

                        converted = {
                            "evaluation_id": row.get("evaluation_id", ""),
                            "experiment_id": row.get("experiment_id", ""),
                            "bug_id": row.get("bug_id", ""),
                            "mode": row.get("mode", ""),
                            "language": row.get("language", ""),
                            "model": row.get("model", ""),
                            "context_chars": ctx_chars,
                            "context_size": ctx_chars,
                            "input_tokens": parse_opt_int(row.get("input_tokens")),
                            "output_tokens": parse_opt_int(row.get("output_tokens")),
                            "total_tokens": parse_opt_int(row.get("total_tokens")),
                            "token_usage_available": usage_avail,
                            "curator_input_tokens": parse_opt_int(row.get("curator_input_tokens")),
                            "curator_output_tokens": parse_opt_int(row.get("curator_output_tokens")),
                            "curator_total_tokens": parse_opt_int(row.get("curator_total_tokens")),
                            "debugger_input_tokens": parse_opt_int(row.get("debugger_input_tokens")),
                            "debugger_output_tokens": parse_opt_int(row.get("debugger_output_tokens")),
                            "debugger_total_tokens": parse_opt_int(row.get("debugger_total_tokens")),
                            "llm_calls": int(row.get("llm_calls") or 0),
                            "mcp_calls": int(row.get("mcp_calls") or 0),
                            "context_reduction_percent": None,
                            "llm_time_ms": parse_opt_float(row.get("llm_time_ms")),
                            "mcp_query_time_ms": parse_opt_float(row.get("mcp_query_time_ms")),
                            "mcp_transport_time_ms": parse_opt_float(row.get("mcp_transport_time_ms")),
                            "mcp_total_time_ms": mcp_tot_time,
                            "mcp_time_ms": mcp_tot_time,
                            "total_curation_time_ms": parse_opt_float(row.get("total_curation_time_ms")),
                            "total_debugging_time_ms": parse_opt_float(row.get("total_debugging_time_ms")),
                            "total_experiment_time_ms": exp_tot_time,
                            "total_time_ms": exp_tot_time,
                            "root_cause_identified": str(row.get("root_cause_identified", "")).lower() == "true",
                            "fix_generated": str(row.get("fix_generated", "")).lower() == "true",
                            "fix_correct": str(row.get("fix_correct", "")).lower() == "true",
                            "re_execution_passed": str(row.get("re_execution_passed", "")).lower() == "true",
                            "stop_reason": row.get("stop_reason", ""),
                            "status": row.get("status", "completed"),
                            "timestamp": row.get("timestamp", ""),
                        }
                        records.append(ExperimentRecord(**converted))
            except Exception:
                return []

        return list(reversed(records))[:limit]

    def get_latest_baseline(self, bug_id: str) -> Optional[ExperimentRecord]:
        """
        Find the most recent valid baseline run for a specific bug_id.
        """
        for record in self.get_experiments(limit=100):
            if (
                record.bug_id.upper() == bug_id.upper()
                and record.mode == "baseline"
                and record.status == "completed"
                and record.context_chars > 0
            ):
                return record
        return None


# Default shared logger instance
logger = ExperimentLogger()
