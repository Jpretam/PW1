"""
Tests for Milestone 8: Baseline Comparison and Evaluation.
Validates:
1. Baseline execution works without MCP (mcp_calls == 0, no curator).
2. Dynamic execution uses M7 / MCP.
3. Same bug can run in both modes (paired experiment).
4. Same LLM/model is used.
5. Token usage is captured correctly without estimation.
6. LLM calls are counted correctly.
7. MCP calls are counted correctly.
8. Timing metrics are recorded accurately.
9. Experiment CSV records and JSONL events are saved properly.
10. Benchmark registry B001-B008 functions properly.
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult, LLMResult

from app.agent.debugger import DebuggingAgent
from app.agent.models import DebugDiagnosis
from app.agent.token_tracker import TokenUsageCallback
from app.evaluation.benchmarks import get_all_benchmarks, get_benchmark
from app.evaluation.logger import ExperimentLogger
from app.evaluation.models import BenchmarkRunRequest, ExperimentRecord
from app.evaluation.service import EvaluationService
from app.main import app
from app.models.execution import ExecutionLanguage, ExecutionRequest
from app.services.executor import CodeExecutionService
from app.services.trace_store.store import store

client = TestClient(app)


def test_token_tracker_callback():
    """Verify TokenUsageCallback captures exact tokens from AIMessage and fallback."""
    tracker = TokenUsageCallback()

    # Simulate LangChain LLMResult with usage_metadata
    msg = AIMessage(
        content='{"test": 1}',
        usage_metadata={"input_tokens": 150, "output_tokens": 45, "total_tokens": 195}
    )
    result = LLMResult(generations=[[ChatGeneration(message=msg)]])

    tracker.on_llm_end(result)
    assert tracker.calls == 1
    assert tracker.input_tokens == 150
    assert tracker.output_tokens == 45
    assert tracker.total_tokens == 195

    # Simulate second call with llm_output fallback
    result_fallback = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="second"))]],
        llm_output={"token_usage": {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100}}
    )
    tracker.on_llm_end(result_fallback)
    assert tracker.calls == 2
    assert tracker.input_tokens == 230
    assert tracker.output_tokens == 65
    assert tracker.total_tokens == 295


def test_benchmark_registry():
    """Verify predefined benchmarks B001 to B008 exist with code and expected error."""
    benchmarks = get_all_benchmarks()
    assert len(benchmarks) == 8

    b_ids = [b.bug_id for b in benchmarks]
    for expected_id in ["B001", "B002", "B003", "B004", "B005", "B006", "B007", "B008"]:
        assert expected_id in b_ids
        bench = get_benchmark(expected_id)
        assert bench is not None
        assert len(bench.code.strip()) > 0
        assert len(bench.expected_error.strip()) > 0


def test_experiment_logger(tmp_path):
    """Verify ExperimentLogger writes CSV and JSONL records correctly."""
    logger = ExperimentLogger(data_dir=tmp_path)
    record = ExperimentRecord(
        experiment_id="exp_test_001",
        bug_id="B001",
        mode="baseline",
        language="python",
        model="openrouter/free",
        llm_calls=1,
        input_tokens=200,
        output_tokens=50,
        total_tokens=250,
        curator_input_tokens=0,
        curator_output_tokens=0,
        curator_total_tokens=0,
        debugger_input_tokens=200,
        debugger_output_tokens=50,
        debugger_total_tokens=250,
        mcp_calls=0,
        context_size=1200,
        context_reduction_percent=0.0,
        llm_time_ms=300.0,
        mcp_query_time_ms=0.0,
        mcp_transport_time_ms=0.0,
        mcp_time_ms=0.0,
        total_curation_time_ms=0.0,
        total_debugging_time_ms=450.0,
        total_time_ms=500.0,
        root_cause_identified=True,
        fix_generated=True,
        fix_correct=True,
        re_execution_passed=True,
        stop_reason="completed",
        timestamp="2026-09-28T12:00:00Z",
    )

    logger.log_experiment(record)

    # Verify CSV file
    assert logger.csv_path.exists()
    records = logger.get_experiments()
    assert len(records) == 1
    assert records[0].experiment_id == "exp_test_001"
    assert records[0].bug_id == "B001"
    assert records[0].mode == "baseline"
    assert records[0].mcp_calls == 0
    assert records[0].total_tokens == 250

    # Verify JSONL file
    assert logger.jsonl_path.exists()
    content = logger.jsonl_path.read_text(encoding="utf-8")
    assert "exp_test_001" in content


@pytest.mark.asyncio
async def test_baseline_diagnosis_mode_does_not_use_mcp():
    """Verify Baseline Mode: uses full source code and trace, never invokes MCP or curator."""
    executor = CodeExecutionService()
    exec_resp = executor.execute_code(ExecutionRequest(
        language=ExecutionLanguage.PYTHON,
        code="def compute(a, b):\n    return a / b\n\ncompute(10, 0)",
    ))
    assert exec_resp.execution_id is not None

    with patch("app.agent.debugger.get_llm") as mock_get_llm, \
         patch("app.agent.debugger.ContextCurator.curate") as mock_curate:

        mock_llm = MagicMock()
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = DebugDiagnosis(
            execution_id=exec_resp.execution_id,
            diagnosis="ZeroDivisionError occurred in compute",
            root_cause="b was evaluated to 0 without guard",
            evidence=["compute(10, 0) caused ZeroDivisionError"],
            queries_used=[],
            confidence=0.95,
            suggested_fix="if b != 0: return a / b else: return 0",
        )
        mock_llm.with_structured_output.return_value = mock_model
        mock_get_llm.return_value = mock_llm

        agent = DebuggingAgent()
        diag = await agent.diagnose(execution_id=exec_resp.execution_id, mode="baseline")

        # Crucial assertions for Baseline
        assert mock_curate.call_count == 0  # Curator NEVER called in baseline
        assert diag.telemetry is not None
        assert diag.telemetry["mode"] == "baseline"
        assert diag.telemetry["mcp_calls"] == 0
        assert diag.telemetry["mcp_query_time"] == 0.0
        assert diag.telemetry["mcp_transport_time"] == 0.0
        assert diag.telemetry["curator_input_tokens"] == 0
        assert diag.telemetry["curator_total_tokens"] == 0
        assert diag.telemetry["context_size"] > 0
        assert "=== FULL SOURCE CODE ===" in mock_model.ainvoke.call_args[0][0][1][1]


@pytest.mark.asyncio
async def test_dynamic_diagnosis_mode_uses_m7_and_mcp():
    """Verify Dynamic Mode: uses M7 ContextCurator and records curator + debugger tokens."""
    executor = CodeExecutionService()
    exec_resp = executor.execute_code(ExecutionRequest(
        language=ExecutionLanguage.PYTHON,
        code="def compute(a, b):\n    return a / b\n\ncompute(10, 0)",
    ))
    assert exec_resp.execution_id is not None

    with patch("app.agent.debugger.get_llm") as mock_get_llm, \
         patch("app.agent.debugger.ContextCurator.curate") as mock_curate:

        from app.agent.curator import CurationResult
        mock_curate.return_value = CurationResult(
            context='[{"source": "get_error_context", "data": "ZeroDivisionError"}]',
            telemetry={
                "tools_used": ["get_error_context", "get_stack_trace"],
                "mcp_calls": 2,
                "curator_input_tokens": 120,
                "curator_output_tokens": 30,
                "curator_total_tokens": 150,
                "llm_calls": 1,
                "llm_time": 0.5,
                "mcp_query_time": 0.08,
                "mcp_transport_time": 0.02,
                "mcp_total_time": 0.10,
                "time_spent": 0.65,
                "stop_reason": "root_cause_identified"
            }
        )

        mock_llm = MagicMock()
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = DebugDiagnosis(
            execution_id=exec_resp.execution_id,
            diagnosis="ZeroDivisionError occurred",
            root_cause="b was 0",
            evidence=["get_error_context returned ZeroDivisionError"],
            queries_used=["get_error_context", "get_stack_trace"],
            confidence=0.9,
            suggested_fix="if b == 0: return 0"
        )
        mock_llm.with_structured_output.return_value = mock_model
        mock_get_llm.return_value = mock_llm

        agent = DebuggingAgent()
        diag = await agent.diagnose(execution_id=exec_resp.execution_id, mode="dynamic")

        assert mock_curate.call_count == 1  # Curator WAS called
        assert diag.telemetry is not None
        assert diag.telemetry["mode"] == "dynamic"
        assert diag.telemetry["mcp_calls"] == 2
        assert diag.telemetry["dynamic_curator_total_tokens"] == 150
        assert "get_error_context" in diag.telemetry["tools_used"]


@pytest.mark.asyncio
async def test_paired_benchmark_execution():
    """Verify running both Baseline and Dynamic on the same bug produces valid comparison."""
    service = EvaluationService()
    bench = get_benchmark("B001")
    assert bench is not None

    with patch("app.agent.debugger.get_llm") as mock_get_llm, \
         patch("app.agent.curator.streamable_http_client"), \
         patch("app.agent.curator.ClientSession"):

        mock_llm = MagicMock()
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = DebugDiagnosis(
            execution_id="dummy",
            diagnosis="ZeroDivisionError",
            root_cause="value is 0",
            evidence=["calculate(0) called"],
            queries_used=[],
            confidence=0.95,
            suggested_fix="if x == 0: return 0\nreturn 10 / x"
        )
        mock_llm.with_structured_output.return_value = mock_model
        # For fixer's ainvoke: return working code
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
            content="def calculate(x):\n    if x == 0: return 0\n    return 10 / x\ndef process():\n    value = 0\n    return calculate(value)\nprocess()"
        ))
        mock_get_llm.return_value = mock_llm

        result = await service.run_paired_experiment(bug_id="B001")

        assert result.bug_id == "B001"
        assert result.baseline.mode == "baseline"
        assert result.dynamic.mode == "dynamic"
        assert result.baseline.mcp_calls == 0
        assert result.baseline.context_size > 0
        assert result.dynamic.context_size > 0
        assert result.baseline.model == result.dynamic.model
        assert result.baseline.language == "python"
        assert result.dynamic.language == "python"


def test_api_evaluation_routes():
    """Verify the /evaluation REST endpoints."""
    # 1. GET /evaluation/benchmarks
    resp = client.get("/evaluation/benchmarks")
    assert resp.status_code == 200
    benchmarks = resp.json()
    assert len(benchmarks) == 8

    # 2. GET /evaluation/benchmarks/B001
    resp_b1 = client.get("/evaluation/benchmarks/B001")
    assert resp_b1.status_code == 200
    assert resp_b1.json()["bug_id"] == "B001"

    # 3. GET /evaluation/experiments
    resp_exp = client.get("/evaluation/experiments?limit=10")
    assert resp_exp.status_code == 200
    assert isinstance(resp_exp.json(), list)
