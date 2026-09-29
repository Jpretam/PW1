"""
Logging infrastructure configuration for PW1.
Enforces strict separation of concerns across three categories:

Category A: Application / Runtime log (backend/logs/app.log)
    - Server startup/shutdown
    - Critical errors, API failures, unexpected exceptions
    - Automatically rotated (5MB max size, 3 backups)

Category B: Experiment telemetry (backend/data/m8/m8_events.jsonl & experiments/<eval_id>/)
    - Structured M7/M8 execution telemetry and retrieval lifecycle events
    - Managed by app.evaluation.logger.ExperimentLogger

Category C: Evaluation dataset (backend/data/m8/m8_experiments.csv)
    - Tabular dataset of completed evaluation experiments
    - Maintained by app.evaluation.logger.ExperimentLogger
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOGS_DIR = BACKEND_ROOT / "logs"
APP_LOG_FILE = DEFAULT_LOGS_DIR / "app.log"

_initialized = False


def setup_logging(logs_dir: Optional[Path] = None) -> None:
    """Initialize application logging with rotating file handler and clean console handler."""
    global _initialized
    if _initialized:
        return

    target_dir = logs_dir or DEFAULT_LOGS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "app.log"

    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False

    if not app_logger.handlers:
        # 1. Rotating File Handler for Application/Runtime Log (5MB per file, 3 backups)
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.INFO)
        app_logger.addHandler(file_handler)

        # 2. Console handler: Warnings and errors only to avoid terminal noise
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            "[%(levelname)s] [%(name)s]: %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.WARNING)
        app_logger.addHandler(console_handler)

    # Silence verbose / duplicate third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.WARNING)

    # Configure mcp.telemetry boundary logger to DEBUG
    mcp_logger = logging.getLogger("app.mcp.telemetry")
    mcp_logger.setLevel(logging.DEBUG)
    mcp_logger.propagate = False

    _initialized = True


def get_app_logger(subname: Optional[str] = None) -> logging.Logger:
    """Get an application logger with the specified hierarchy."""
    if not _initialized:
        setup_logging()
    name = f"app.{subname}" if subname else "app"
    return logging.getLogger(name)
