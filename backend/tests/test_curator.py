import pytest
import os
import json
from unittest.mock import AsyncMock, patch, MagicMock

from app.agent.curator import ContextCurator, RetrievalDecision, ToolCall
from app.agent.models import DebugDiagnosis


@pytest.fixture
def mock_llm_chain():
    with patch("app.agent.curator.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_model = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_model
        mock_get_llm.return_value = mock_llm
        yield mock_model


@pytest.fixture
def mock_mcp_session():
    with patch("app.agent.curator.streamable_http_client") as mock_client:
        mock_ctx = AsyncMock()
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_client.return_value.__aenter__.return_value = (mock_read, mock_write)
        
        with patch("app.agent.curator.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session
            
            async def call_tool(name, arguments):
                mock_result = MagicMock()
                if name == "get_error_context":
                    mock_result.structured_content = {"error_type": "ZeroDivisionError", "line": 5, "file": "script.py"}
                elif name == "get_stack_trace":
                    mock_result.structured_content = [{"frame_id": 1, "function": "process", "line": 5, "file": "script.py"}]
                elif name == "get_frame_variables":
                    mock_result.structured_content = {"a": 10, "b": 0}
                elif name == "get_source_context":
                    mock_result.structured_content = {"start_line": 3, "end_line": 6}
                else:
                    mock_result.structured_content = {}
                return mock_result
            
            mock_session.call_tool.side_effect = call_tool
            yield mock_session


@pytest.mark.asyncio
async def test_curator_basic_flow(mock_llm_chain, mock_mcp_session):
    # LLM will decide to call get_error_context, then get_stack_trace, then stop.
    mock_llm_chain.ainvoke.side_effect = [
        RetrievalDecision(tool_calls=[ToolCall(tool_name="get_error_context", tool_args={})], reason="Get error", is_sufficient=False, direction="initial"),
        RetrievalDecision(tool_calls=[ToolCall(tool_name="get_stack_trace", tool_args={})], reason="Get stack", is_sufficient=False, direction="stack"),
        RetrievalDecision(tool_calls=[], reason="Done", is_sufficient=True, direction="initial"),
    ]

    curator = ContextCurator()
    result = await curator.curate("exec_123")
    
    assert "telemetry" in result.model_dump()
    assert result.telemetry["mcp_calls"] == 4 # 4 deterministic, duplicates skipped
    assert result.telemetry["llm_calls"] == 3
    assert result.telemetry["llm_successes"] == 3
    assert result.telemetry["llm_failures"] == 0
    assert "mcp_query_time" in result.telemetry
    assert "mcp_transport_time" in result.telemetry
    assert "mcp_total_time" in result.telemetry
    assert "get_error_context" in result.telemetry["tools_used"]
    assert "get_stack_trace" in result.telemetry["tools_used"]
    assert "stack" in result.telemetry["investigation_directions"]
    assert result.telemetry["investigation_depth"] == 6
    assert result.telemetry["stop_reason"] == "root_cause_identified"


@pytest.mark.asyncio
async def test_curator_context_budget(mock_llm_chain, mock_mcp_session):
    # Simulate LLM wanting to call tools forever but with unique args
    call_count = 0
    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return RetrievalDecision(tool_calls=[ToolCall(tool_name="get_error_context", tool_args={"count": call_count})], reason="Loop", is_sufficient=False, direction="initial")
    
    mock_llm_chain.ainvoke.side_effect = side_effect

    curator = ContextCurator()
    # Force max budget to 3
    curator.max_calls = 3
    result = await curator.curate("exec_123")
    
    assert result.telemetry["mcp_calls"] == 3
    assert result.telemetry["stop_reason"] == "budget_limit_reached"


@pytest.mark.asyncio
async def test_curator_stops_when_sufficient(mock_llm_chain, mock_mcp_session):
    mock_llm_chain.ainvoke.side_effect = [
        RetrievalDecision(tool_calls=[], reason="Check error", is_sufficient=True, direction="initial"),
    ]

    curator = ContextCurator()
    result = await curator.curate("exec_123")
    
    assert result.telemetry["mcp_calls"] == 4 # 4 deterministic calls
    assert result.telemetry["stop_reason"] == "root_cause_identified"


@pytest.mark.asyncio
async def test_curator_handles_llm_error(mock_llm_chain, mock_mcp_session):
    mock_llm_chain.ainvoke.side_effect = Exception("OpenRouter 429")

    curator = ContextCurator()
    result = await curator.curate("exec_123")
    
    assert result.telemetry["llm_calls"] == 1
    assert result.telemetry["llm_successes"] == 0
    assert result.telemetry["llm_failures"] == 1
    assert result.telemetry["stop_reason"] == "curator_error"


@pytest.mark.asyncio
async def test_debugging_agent_uses_curator(mock_llm_chain, mock_mcp_session):
    # Ensure M5 functionality works through the new architecture
    with patch("app.agent.debugger.ContextCurator.curate") as mock_curate:
        from app.agent.curator import CurationResult
        mock_curate.return_value = CurationResult(
            context='[{"source": "get_error_context", "data": "ZeroDivisionError"}]',
            telemetry={"tools_used": ["get_error_context"], "mcp_calls": 1}
        )

        with patch("app.agent.debugger.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_model = AsyncMock()
            mock_model.ainvoke.return_value = DebugDiagnosis(
                execution_id="exec_123",
                diagnosis="ZeroDivisionError",
                root_cause="b was 0",
                evidence=["get_error_context returned ZeroDivisionError"],
                queries_used=[],
                confidence=0.9,
                suggested_fix="if b == 0: return 0"
            )
            mock_llm.with_structured_output.return_value = mock_model
            mock_get_llm.return_value = mock_llm
            
            from app.agent.debugger import DebuggingAgent
            agent = DebuggingAgent()
            diagnosis = await agent.diagnose("exec_123")
            
            assert diagnosis.execution_id == "exec_123"
            assert "get_error_context" in diagnosis.queries_used
            assert hasattr(diagnosis, "telemetry")
