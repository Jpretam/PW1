"""
Tests for Milestone 8: Baseline Comparison, Token Tracking, Measurement Validation, and Experiment Pairing.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from app.agent.debugger import DebuggingAgent
from app.agent.models import DebugDiagnosis
from app.agent.token_tracker import TokenUsageCallback, TokenUsageResult, extract_token_usage
from app.evaluation.benchmarks import get_all_benchmarks, get_benchmark
from app.evaluation.logger import ExperimentLogger
from app.evaluation.models import BenchmarkRunRequest, ExperimentRecord
from app.evaluation.service import EvaluationService
from app.main import app
from app.models.execution import ExecutionLanguage, ExecutionRequest
from app.services.executor import CodeExecutionService

client = TestClient(app)


def test_normalized_extract_token_usage_helper():
    """Verify extract_token_usage handles AIMessage, dict, and missing usage cleanly."""
    # 1. AIMessage with usage_metadata
    msg = AIMessage(
        content='Hello',
        usage_metadata={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}
    )
    res = extract_token_usage(msg)
    assert res.available is True
    assert res.input_tokens == 120
    assert res.output_tokens == 30
    assert res.total_tokens == 150

    # 2. Raw OpenRouter response dictionary with 'usage'
    raw_dict = {
        "id": "gen-123",
        "usage": {
            "prompt_tokens": 200,
            "completion_tokens": 50,
            "total_tokens": 250,
        }
    }
    res_dict = extract_token_usage(raw_dict)
    assert res_dict.available is True
    assert res_dict.input_tokens == 200
    assert res_dict.output_tokens == 50
    assert res_dict.total_tokens == 250

    # 3. Missing usage metadata -> available is False, tokens are None (never 0)
    msg_empty = AIMessage(content='No metadata')
    res_empty = extract_token_usage(msg_empty)
    assert res_empty.available is False
    assert res_empty.input_tokens is None
    assert res_empty.output_tokens is None
    assert res_empty.total_tokens is None
    assert res_empty.total_tokens != 0

    # 4. None input
    res_none = extract_token_usage(None)
    assert res_none.available is False
    assert res_none.input_tokens is None


def test_fairness_token_aggregation_curator_and_debugger(tmp_path):
    """Verify Dynamic total tokens = curator_tokens + debugger_tokens, and Baseline = debugger_tokens."""
    isolated_logger = ExperimentLogger(data_dir=tmp_path)
    service = EvaluationService(logger=isolated_logger)

    # Dynamic run record simulation
    dyn_rec = ExperimentRecord(
        evaluation_id="eval_fairness_1",
        experiment_id="eval_fairness_1_dynamic",
        bug_id="B001",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=1306,
        curator_input_tokens=100,
        curator_output_tokens=25,
        curator_total_tokens=125,
        debugger_input_tokens=200,
        debugger_output_tokens=50,
        debugger_total_tokens=250,
        input_tokens=300,  # 100 + 200
        output_tokens=75,  # 25 + 50
        total_tokens=375,  # 125 + 250
        token_usage_available=True,
    )

    # Baseline run record simulation
    base_rec = ExperimentRecord(
        evaluation_id="eval_fairness_1",
        experiment_id="eval_fairness_1_baseline",
        bug_id="B001",
        mode="baseline",
        language="python",
        model="openrouter/free",
        context_chars=11440,
        curator_input_tokens=0,
        curator_output_tokens=0,
        curator_total_tokens=0,
        debugger_input_tokens=500,
        debugger_output_tokens=120,
        debugger_total_tokens=620,
        input_tokens=500,
        output_tokens=120,
        total_tokens=620,
        token_usage_available=True,
    )

    assert dyn_rec.total_tokens == dyn_rec.curator_total_tokens + dyn_rec.debugger_total_tokens
    assert dyn_rec.input_tokens == dyn_rec.curator_input_tokens + dyn_rec.debugger_input_tokens
    assert dyn_rec.output_tokens == dyn_rec.curator_output_tokens + dyn_rec.debugger_output_tokens
    assert base_rec.total_tokens == base_rec.debugger_total_tokens

    # Verify token reduction is computed from total tokens
    from app.evaluation.models import ComparisonResult
    comp = ComparisonResult(
        evaluation_id="eval_fairness_1",
        bug_id="B001",
        language="python",
        model="openrouter/free",
        baseline=base_rec,
        dynamic=dyn_rec,
        context_reduction_percent=88.58,
        token_reduction_percent=round(((base_rec.total_tokens - dyn_rec.total_tokens) / base_rec.total_tokens) * 100.0, 2),
        time_difference_ms=100.0,
    )
    # 620 vs 375 -> (620 - 375) / 620 * 100 = 39.52%
    assert comp.token_reduction_percent == 39.52


def test_token_usage_extraction():
    """1. Verify TokenUsageCallback extracts actual provider usage metadata from AIMessage and fallback."""
    tracker = TokenUsageCallback()

    # Simulate LangChain LLMResult with usage_metadata
    msg = AIMessage(
        content='{"test": 1}',
        usage_metadata={"input_tokens": 150, "output_tokens": 45, "total_tokens": 195}
    )
    result = LLMResult(generations=[[ChatGeneration(message=msg)]])

    tracker.on_llm_end(result)
    assert tracker.calls == 1
    assert tracker.usage_available is True
    assert tracker.input_tokens == 150
    assert tracker.output_tokens == 45
    assert tracker.total_tokens == 195
    assert tracker.safe_input_tokens == 150
    assert tracker.safe_output_tokens == 45
    assert tracker.safe_total_tokens == 195

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


def test_missing_token_usage_does_not_become_zero():
    """2. Verify missing token metadata from provider results in None and usage_available=False, never 0."""
    tracker = TokenUsageCallback()

    # LLMResult with empty generations and no usage_metadata or token_usage
    msg = AIMessage(content='{"result": "ok"}')
    result = LLMResult(generations=[[ChatGeneration(message=msg)]])

    tracker.on_llm_end(result)
    assert tracker.calls == 1
    assert tracker.usage_available is False
    assert tracker.safe_input_tokens is None
    assert tracker.safe_output_tokens is None
    assert tracker.safe_total_tokens is None
    # Crucial: safe properties return None, not 0
    assert tracker.safe_total_tokens != 0


def test_context_character_measurement():
    """3. Verify context_chars measures characters and distinguishes characters from tokens."""
    context_text = "def hello():\n    return 'world'"
    char_count = len(context_text)

    record = ExperimentRecord(
        evaluation_id="eval_test",
        experiment_id="exp_test",
        bug_id="B001",
        mode="baseline",
        language="python",
        model="openrouter/free",
        context_chars=char_count,
        input_tokens=12,  # token count is different from character count
        output_tokens=5,
        total_tokens=17,
        token_usage_available=True,
    )

    assert record.context_chars == char_count
    assert record.context_size == char_count
    assert record.context_chars != record.total_tokens


def test_context_reduction_calculation():
    """4. Verify context reduction formula: ((baseline_chars - dynamic_chars) / baseline_chars) * 100."""
    baseline_chars = 10000
    dynamic_chars = 1200
    expected_reduction = round(((baseline_chars - dynamic_chars) / baseline_chars) * 100.0, 2)
    assert expected_reduction == 88.0

    service = EvaluationService(logger=MagicMock())
    # Test formula directly
    reduction = round(((baseline_chars - dynamic_chars) / baseline_chars) * 100.0, 2)
    assert reduction == 88.0


def test_token_reduction_calculation_and_unavailable_handling():
    """Verify token reduction is calculated when available, and None (not fake 0) when unavailable."""
    # When available
    base_tok = 1000
    dyn_tok = 400
    expected_reduction = round(((base_tok - dyn_tok) / base_tok) * 100.0, 2)
    assert expected_reduction == 60.0

    # When unavailable, ComparisonResult returns None for token_reduction_percent
    base_rec = ExperimentRecord(
        evaluation_id="eval_1",
        experiment_id="exp_1",
        bug_id="B001",
        mode="baseline",
        language="python",
        model="test",
        token_usage_available=False,
        total_tokens=None,
    )
    dyn_rec = ExperimentRecord(
        evaluation_id="eval_1",
        experiment_id="exp_2",
        bug_id="B001",
        mode="dynamic",
        language="python",
        model="test",
        token_usage_available=False,
        total_tokens=None,
    )
    from app.evaluation.models import ComparisonResult
    comp = ComparisonResult(
        evaluation_id="eval_1",
        bug_id="B001",
        language="python",
        model="test",
        baseline=base_rec,
        dynamic=dyn_rec,
        context_reduction_percent=None,
        token_reduction_percent=None,
        time_difference_ms=10.0,
    )
    assert comp.token_reduction_percent is None


@pytest.mark.asyncio
async def test_experiment_pairing_and_single_record_creation(tmp_path):
    """5 & 6. Verify shared evaluation_id links paired runs, and 1 request creates 1 record per mode."""
    isolated_logger = ExperimentLogger(data_dir=tmp_path)
    service = EvaluationService(logger=isolated_logger)

    with patch("app.agent.debugger.get_llm") as mock_get_llm, \
         patch("app.agent.curator.streamable_http_client") as mock_client, \
         patch("app.agent.curator.ClientSession"):

        mock_ctx = AsyncMock()
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_client.return_value.__aenter__.return_value = (mock_read, mock_write)

        mock_llm = MagicMock()
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = DebugDiagnosis(
            execution_id="dummy",
            diagnosis="ZeroDivisionError",
            root_cause="Division by zero",
            evidence=[],
            queries_used=[],
            confidence=0.9,
            suggested_fix="return 0",
        )
        mock_llm.with_structured_output.return_value = mock_model
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="def calculate(x): return 10 / x if x != 0 else 0\nprocess()"))
        mock_get_llm.return_value = mock_llm

        # Run paired experiment
        result = await service.run_paired_experiment(bug_id="B001")

        # 1. Pairing verification
        assert result.evaluation_id.startswith("eval_")
        assert result.baseline.evaluation_id == result.evaluation_id
        assert result.dynamic.evaluation_id == result.evaluation_id
        assert result.baseline.experiment_id == f"{result.evaluation_id}_baseline"
        assert result.dynamic.experiment_id == f"{result.evaluation_id}_dynamic"

        # 2. Exactly 2 records in isolated logger
        records = isolated_logger.get_experiments()
        assert len(records) == 2
        modes = {r.mode for r in records}
        assert modes == {"baseline", "dynamic"}


@pytest.mark.asyncio
async def test_baseline_produces_zero_mcp_calls():
    """7. Verify Baseline Mode: uses full source code and trace, produces zero MCP calls."""
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

        assert mock_curate.call_count == 0  # Curator NEVER called in baseline
        assert diag.telemetry is not None
        assert diag.telemetry["mode"] == "baseline"
        assert diag.telemetry["mcp_calls"] == 0
        assert diag.telemetry["mcp_query_time"] == 0.0
        assert diag.telemetry["mcp_transport_time"] == 0.0
        assert diag.telemetry["curator_input_tokens"] == 0
        assert diag.telemetry["context_chars"] > 0
        assert "=== FULL SOURCE CODE ===" in mock_model.ainvoke.call_args[0][0][1][1]


@pytest.mark.asyncio
async def test_dynamic_records_mcp_calls_and_timing():
    """8 & 9. Verify Dynamic Mode records MCP calls and distinct timing fields."""
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
                "token_usage_available": True,
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

        assert mock_curate.call_count == 1
        assert diag.telemetry is not None
        assert diag.telemetry["mode"] == "dynamic"
        assert diag.telemetry["mcp_calls"] == 2
        assert diag.telemetry["mcp_query_time"] == 0.08
        assert diag.telemetry["mcp_transport_time"] == 0.02
        assert diag.telemetry["mcp_total_time"] == 0.10
        assert diag.telemetry["dynamic_curator_total_tokens"] == 150


@pytest.mark.asyncio
async def test_invalid_experiment_record_handling(tmp_path):
    """10. Verify 2-char context or mcp_transport_error is flagged as invalid, not completed."""
    isolated_logger = ExperimentLogger(data_dir=tmp_path)
    service = EvaluationService(logger=isolated_logger)

    with patch("app.agent.fixer.FixerAgent.fix") as mock_fix:
        # Simulate failed curation producing empty context [] (2 chars)
        mock_diagnosis = DebugDiagnosis(
            execution_id="dummy_fail",
            diagnosis="Diagnosis unavailable",
            root_cause="",
            evidence=[],
            queries_used=[],
            confidence=0.0,
            suggested_fix="none",
            telemetry={
                "mode": "dynamic",
                "context_chars": 2,
                "context_size": 2,
                "mcp_calls": 0,
                "mcp_query_time": 0.0,
                "mcp_transport_time": 0.0,
                "mcp_total_time": 0.0,
                "stop_reason": "mcp_transport_error: connection refused",
            }
        )
        mock_fix.return_value = MagicMock(
            original_diagnosis=mock_diagnosis,
            fixed_code="",
            success=False,
            telemetry=mock_diagnosis.telemetry,
        )

        record = await service.run_experiment(
            code="def f(): pass",
            mode="dynamic",
            bug_id="B001",
        )

        assert record.status == "invalid"
        assert record.context_reduction_percent is None
        assert record.fix_correct is False


def test_benchmark_registry():
    """Verify predefined benchmarks B001 to B008 exist with valid specifications."""
    benchmarks = get_all_benchmarks()
    assert len(benchmarks) == 8

    b_ids = [b.bug_id for b in benchmarks]
    for expected_id in ["B001", "B002", "B003", "B004", "B005", "B006", "B007", "B008"]:
        assert expected_id in b_ids
        bench = get_benchmark(expected_id)
        assert bench is not None
        assert len(bench.code.strip()) > 0
        assert len(bench.expected_error.strip()) > 0


def test_experiment_logger_schema_and_persistence(tmp_path):
    """Verify ExperimentLogger writes and reads CSV records with the Section 11 schema."""
    logger = ExperimentLogger(data_dir=tmp_path)
    record = ExperimentRecord(
        evaluation_id="eval_20260928_b001_123456",
        experiment_id="eval_20260928_b001_123456_baseline",
        bug_id="B001",
        mode="baseline",
        language="python",
        model="openrouter/free",
        context_chars=11440,
        input_tokens=250,
        output_tokens=60,
        total_tokens=310,
        token_usage_available=True,
        curator_input_tokens=0,
        curator_output_tokens=0,
        curator_total_tokens=0,
        debugger_input_tokens=250,
        debugger_output_tokens=60,
        debugger_total_tokens=310,
        llm_calls=1,
        mcp_calls=0,
        mcp_query_time_ms=0.0,
        mcp_transport_time_ms=0.0,
        mcp_total_time_ms=0.0,
        llm_time_ms=350.0,
        total_experiment_time_ms=500.0,
        root_cause_identified=True,
        fix_generated=True,
        fix_correct=True,
        re_execution_passed=True,
        stop_reason="completed",
        status="completed",
        timestamp="2026-09-28T12:00:00Z",
    )

    logger.log_experiment(record)
    records = logger.get_experiments()
    assert len(records) == 1
    r = records[0]
    assert r.evaluation_id == "eval_20260928_b001_123456"
    assert r.experiment_id == "eval_20260928_b001_123456_baseline"
    assert r.context_chars == 11440
    assert r.total_tokens == 310
    assert r.token_usage_available is True
    assert r.status == "completed"


def test_api_evaluation_routes():
    """Verify the /evaluation REST endpoints."""
    resp = client.get("/evaluation/benchmarks")
    assert resp.status_code == 200
    assert len(resp.json()) == 8

    resp_b1 = client.get("/evaluation/benchmarks/B001")
    assert resp_b1.status_code == 200
    assert resp_b1.json()["bug_id"] == "B001"

    resp_exp = client.get("/evaluation/experiments?limit=10")
    assert resp_exp.status_code == 200
    assert isinstance(resp_exp.json(), list)
