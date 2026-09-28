"""
Service module for executing evaluation experiments, capturing metrics,
and comparing Baseline vs Dynamic context curation.
"""

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.agent.fixer import FixerAgent
from app.evaluation.benchmarks import get_benchmark
from app.evaluation.logger import logger
from app.evaluation.models import ComparisonResult, ExperimentRecord
from app.models.execution import ExecutionLanguage, ExecutionRequest
from app.services.executor import CodeExecutionService
from app.services.trace_store.store import store


class EvaluationService:
    def __init__(self) -> None:
        self.executor = CodeExecutionService()
        self.fixer = FixerAgent()
        self.store = store
        self.logger = logger

    async def run_experiment(
        self,
        code: str,
        language: str = "python",
        stdin: str = "",
        mode: str = "dynamic",
        bug_id: str = "CUSTOM",
        baseline_context_size: int | None = None,
    ) -> ExperimentRecord:
        """
        Execute a single evaluation experiment (either 'baseline' or 'dynamic').
        """
        clean_mode = mode.strip().lower()
        if clean_mode not in ("baseline", "dynamic"):
            clean_mode = "dynamic"

        try:
            lang_enum = ExecutionLanguage(language.lower())
        except ValueError:
            lang_enum = ExecutionLanguage.PYTHON

        model_name = os.getenv("LLM_MODEL", "openrouter/free")
        now_utc = datetime.now(timezone.utc)
        timestamp = now_utc.isoformat()
        exp_id = f"exp_{now_utc.strftime('%Y%m%d_%H%M%S')}_{bug_id.lower()}_{clean_mode}_{uuid.uuid4().hex[:6]}"

        overall_start = time.time()

        # Step 1: Initial execution to create execution trace
        exec_request = ExecutionRequest(
            language=lang_enum,
            code=code,
            stdin=stdin or "",
        )
        exec_response = self.executor.execute_code(exec_request)
        execution_id = exec_response.execution_id

        # Step 2: Run diagnosis & repair workflow in the chosen mode
        fix_result = await self.fixer.fix(
            execution_id=execution_id,
            max_attempts=1,
            mode=clean_mode,
        )

        overall_time_ms = (time.time() - overall_start) * 1000.0

        # Step 3: Extract diagnosis, repair, and telemetry data
        diagnosis = fix_result.original_diagnosis
        telemetry = fix_result.telemetry or diagnosis.telemetry or {}

        # Effectiveness Metrics
        diag_text = (diagnosis.diagnosis or "").lower()
        root_cause_identified = bool(
            diagnosis.root_cause
            and "failed to produce structured output" not in diag_text
            and "unavailable" not in diag_text
        )
        fix_generated = bool(fix_result.fixed_code and len(fix_result.fixed_code.strip()) > 0)
        fix_correct = bool(fix_result.success)
        re_execution_passed = bool(fix_result.success)

        # Context Size & Reduction
        context_size = int(telemetry.get("context_size", 0) or 0)

        # Look up baseline context size if not provided directly
        effective_baseline_size = baseline_context_size
        if effective_baseline_size is None and clean_mode == "dynamic":
            recent_baseline = self.logger.get_latest_baseline(bug_id)
            if recent_baseline and recent_baseline.context_size > 0:
                effective_baseline_size = recent_baseline.context_size

        if effective_baseline_size and effective_baseline_size > 0 and clean_mode == "dynamic":
            reduction_percent = round(
                ((effective_baseline_size - context_size) / effective_baseline_size) * 100.0, 2
            )
        else:
            reduction_percent = 0.0

        # Timing Metrics
        llm_time_ms = round(float(telemetry.get("llm_time", 0.0) or 0.0) * 1000.0, 2)
        mcp_q_ms = round(float(telemetry.get("mcp_query_time", 0.0) or 0.0) * 1000.0, 2)
        mcp_t_ms = round(float(telemetry.get("mcp_transport_time", 0.0) or 0.0) * 1000.0, 2)
        mcp_time_ms = round(float(telemetry.get("mcp_total_time", 0.0) or 0.0) * 1000.0, 2)
        curation_time_ms = round(float(telemetry.get("curation_time", 0.0) or 0.0) * 1000.0, 2)
        total_debugging_time_ms = round(overall_time_ms - curation_time_ms, 2) if clean_mode == "dynamic" else round(overall_time_ms, 2)

        # Token Measurements
        if clean_mode == "baseline":
            in_tokens = int(telemetry.get("baseline_input_tokens", 0) or 0)
            out_tokens = int(telemetry.get("baseline_output_tokens", 0) or 0)
            tot_tokens = int(telemetry.get("baseline_total_tokens", 0) or (in_tokens + out_tokens))
            cur_in = 0
            cur_out = 0
            cur_tot = 0
            deb_in = in_tokens
            deb_out = out_tokens
            deb_tot = tot_tokens
            mcp_calls_count = 0
        else:
            cur_in = int(telemetry.get("dynamic_curator_input_tokens", 0) or 0)
            cur_out = int(telemetry.get("dynamic_curator_output_tokens", 0) or 0)
            cur_tot = int(telemetry.get("dynamic_curator_total_tokens", 0) or (cur_in + cur_out))
            deb_in = int(telemetry.get("dynamic_debugger_input_tokens", 0) or 0)
            deb_out = int(telemetry.get("dynamic_debugger_output_tokens", 0) or 0)
            deb_tot = int(telemetry.get("dynamic_debugger_total_tokens", 0) or (deb_in + deb_out))
            tot_tokens = cur_tot + deb_tot
            in_tokens = cur_in + deb_in
            out_tokens = cur_out + deb_out
            mcp_calls_count = int(telemetry.get("mcp_calls", 0) or 0)

        llm_calls_count = int(telemetry.get("llm_calls", 1) or 1)
        stop_reason = str(telemetry.get("stop_reason", "completed"))

        record = ExperimentRecord(
            experiment_id=exp_id,
            bug_id=bug_id,
            mode=clean_mode,
            language=language.lower(),
            model=model_name,
            llm_calls=llm_calls_count,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            total_tokens=tot_tokens,
            curator_input_tokens=cur_in,
            curator_output_tokens=cur_out,
            curator_total_tokens=cur_tot,
            debugger_input_tokens=deb_in,
            debugger_output_tokens=deb_out,
            debugger_total_tokens=deb_tot,
            mcp_calls=mcp_calls_count,
            context_size=context_size,
            context_reduction_percent=reduction_percent,
            llm_time_ms=llm_time_ms,
            mcp_query_time_ms=mcp_q_ms,
            mcp_transport_time_ms=mcp_t_ms,
            mcp_time_ms=mcp_time_ms,
            total_curation_time_ms=curation_time_ms,
            total_debugging_time_ms=total_debugging_time_ms,
            total_time_ms=round(overall_time_ms, 2),
            root_cause_identified=root_cause_identified,
            fix_generated=fix_generated,
            fix_correct=fix_correct,
            re_execution_passed=re_execution_passed,
            stop_reason=stop_reason,
            timestamp=timestamp,
        )

        # Log record to CSV and JSONL
        self.logger.log_experiment(record)
        return record

    async def run_paired_experiment(
        self,
        bug_id: str | None = None,
        code: str | None = None,
        language: str = "python",
        stdin: str = "",
    ) -> ComparisonResult:
        """
        Run both Baseline (Full Context) and Dynamic (Curated Context) on the exact same task.
        Returns a side-by-side comparison.
        """
        effective_bug_id = bug_id.upper() if bug_id else "CUSTOM"
        effective_code = code

        if bug_id:
            bench = get_benchmark(bug_id)
            if bench:
                effective_code = bench.code
                language = bench.language
                stdin = bench.stdin

        if not effective_code:
            raise ValueError("No valid code or benchmark found to evaluate.")

        # 1. Run Baseline Mode
        baseline_record = await self.run_experiment(
            code=effective_code,
            language=language,
            stdin=stdin,
            mode="baseline",
            bug_id=effective_bug_id,
        )

        # 2. Run Dynamic Mode (supplying baseline context size for exact reduction calculation)
        dynamic_record = await self.run_experiment(
            code=effective_code,
            language=language,
            stdin=stdin,
            mode="dynamic",
            bug_id=effective_bug_id,
            baseline_context_size=baseline_record.context_size,
        )

        # 3. Compute relative comparison metrics
        base_ctx = baseline_record.context_size
        dyn_ctx = dynamic_record.context_size
        ctx_reduct = round(((base_ctx - dyn_ctx) / base_ctx) * 100.0, 2) if base_ctx > 0 else 0.0

        base_tokens = baseline_record.total_tokens
        dyn_tokens = dynamic_record.total_tokens
        tok_reduct = round(((base_tokens - dyn_tokens) / base_tokens) * 100.0, 2) if base_tokens > 0 else 0.0

        time_diff = round(dynamic_record.total_time_ms - baseline_record.total_time_ms, 2)

        return ComparisonResult(
            bug_id=effective_bug_id,
            language=language.lower(),
            model=baseline_record.model,
            baseline=baseline_record,
            dynamic=dynamic_record,
            context_reduction_percent=ctx_reduct,
            token_reduction_percent=tok_reduct,
            time_difference_ms=time_diff,
        )
