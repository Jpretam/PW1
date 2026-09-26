import json
import logging
import os
import time
from typing import Any
from pydantic import BaseModel, Field

from app.agent.llm import get_llm
from app.agent.mcp_client import get_debugging_tools

class RetrievalDecision(BaseModel):
    tool_name: str | None = Field(description="Name of the tool to call next. Null if stopping.")
    tool_args: dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool.")
    reason: str = Field(description="Why this information is needed.")
    is_sufficient: bool = Field(description="True if enough context is gathered to diagnose the bug.")
    direction: str = Field(description="Investigation direction: 'forward', 'backward', 'stack', 'path', or 'initial'.")

class CurationResult(BaseModel):
    context: str
    telemetry: dict[str, Any]

logger = logging.getLogger("m7_curator")
logger.setLevel(logging.INFO)
# Prevent duplicate handlers if module is reloaded
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(message)s')  # Just output the JSON message
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class ContextCurator:
    def __init__(self):
        self.llm = get_llm()
        self.tools = get_debugging_tools()
        self.tools_by_name = {tool.name: tool for tool in self.tools}
        self.decision_model = self.llm.with_structured_output(RetrievalDecision)
        
        self.max_calls = int(os.getenv("MAX_CONTEXT_CALLS", "10"))
        self.max_events = int(os.getenv("MAX_CONTEXT_EVENTS", "50"))
        self.max_lines = int(os.getenv("MAX_CONTEXT_LINES", "100"))

    def _size(self, obj: Any) -> tuple[int, int]:
        s = json.dumps(obj) if not isinstance(obj, str) else obj
        return len(s), len(s.encode('utf-8'))

    async def curate(self, execution_id: str, initial_context: str | None = None) -> CurationResult:
        start_time = time.time()
        
        state = {
            "execution_id": execution_id,
            "known_context": [],
            "retrieval_history": [],
            "remaining_budget": self.max_calls,
        }
        
        telemetry = {
            "execution_id": execution_id,
            "initial_context_size": len(initial_context) if initial_context else 0,
            "mcp_calls": 0,
            "tools_used": [],
            "events_retrieved": 0,
            "source_lines_retrieved": 0,
            "variables_retrieved": 0,
            "total_curated_context_size": 0,
            "investigation_depth": 0,
            "investigation_directions": set(),
            "time_spent": 0.0
        }
        
        
        logger.info(json.dumps({
            "event": "curation_start",
            "execution_id": execution_id,
            "max_calls": self.max_calls
        }))

        if initial_context:
            state["known_context"].append({"source": "initial_context", "data": initial_context})
            logger.info(json.dumps({
                "event": "initial_context",
                "execution_id": execution_id,
                "context_size": len(initial_context)
            }))

        system_prompt = """You are the Dynamic Context Curator. 
Your goal is to gather ONLY the runtime context relevant to diagnosing a failure.
Do not retrieve everything. Start with get_error_context. 
Based on the error, investigate backwards, forwards, stack, or path.
If you have enough information to explain the root cause and line of failure, set is_sufficient to True.
"""

        while state["remaining_budget"] > 0:
            prompt = f"Current State: {json.dumps(state['known_context'])}\nRemaining Budget: {state['remaining_budget']}\nWhat context should we retrieve next?"
            
            try:
                decision: RetrievalDecision = await self.decision_model.ainvoke([
                    ("system", system_prompt),
                    ("human", prompt)
                ])
                logger.info(json.dumps({
                    "event": "curation_decision",
                    "execution_id": execution_id,
                    "step": telemetry["mcp_calls"] + 1,
                    "mcp_tool_name": decision.tool_name,
                    "reason": decision.reason,
                    "direction": decision.direction,
                    "is_sufficient": decision.is_sufficient
                }))
            except Exception as e:
                # Fallback if LLM fails
                break

            if decision.is_sufficient:
                logger.info(json.dumps({
                    "event": "root_cause_identified",
                    "execution_id": execution_id,
                    "reason": decision.reason
                }))
                break
                
            if not decision.tool_name:
                logger.info(json.dumps({
                    "event": "curation_stop",
                    "execution_id": execution_id,
                    "reason": "Agent decided to stop."
                }))
                break
                
            tool_name = decision.tool_name
            tool_args = decision.tool_args
            
            if "execution_id" not in tool_args:
                tool_args["execution_id"] = execution_id
                
            # Check for duplicate retrieval
            is_duplicate = any(
                entry["source"] == tool_name and entry.get("args") == tool_args 
                for entry in state["known_context"]
            )
            
            if is_duplicate:
                logger.info(json.dumps({
                    "event": "duplicate_retrieval_skipped",
                    "execution_id": execution_id,
                    "step": telemetry["mcp_calls"] + 1,
                    "mcp_tool_name": tool_name
                }))
                # Avoid infinite loops by reducing budget and continuing
                state["remaining_budget"] -= 1
                continue

            tool = self.tools_by_name.get(tool_name)
            if not tool:
                continue
                
            logger.info(json.dumps({
                "event": "mcp_retrieval",
                "execution_id": execution_id,
                "step": telemetry["mcp_calls"] + 1,
                "mcp_tool_name": tool_name,
                "tool_args": tool_args
            }))
            
            try:
                result = await tool.ainvoke(tool_args)
            except Exception as e:
                result = {"error": str(e)}
                
            chars, bytes_ = self._size(result)
            
            # Simple relevance check: if it's not an error, we consider it relevant for now.
            relevance = "high" if "error" not in result else "low"
            
            context_entry = {
                "source": tool_name,
                "args": tool_args,
                "reason": decision.reason,
                "relevance": relevance,
                "data": result
            }
            
            state["known_context"].append(context_entry)
            
            history_entry = {
                "step": telemetry["mcp_calls"] + 1,
                "tool": tool_name,
                "reason": decision.reason,
                "result_size": chars
            }
            state["retrieval_history"].append(history_entry)
            
            # Update telemetry
            telemetry["mcp_calls"] += 1
            if tool_name not in telemetry["tools_used"]:
                telemetry["tools_used"].append(tool_name)
            telemetry["investigation_depth"] += 1
            telemetry["investigation_directions"].add(decision.direction)
            
            events_got = 0
            lines_got = 0
            vars_got = 0
            
            if tool_name == "get_event":
                telemetry["events_retrieved"] += 1
                events_got = 1
            elif tool_name == "get_execution_path" or tool_name == "search_trace":
                events_got = len(result) if isinstance(result, list) else 0
                telemetry["events_retrieved"] += events_got
            elif tool_name == "get_source_context":
                if isinstance(result, dict) and "start_line" in result and "end_line" in result:
                    lines_got = (result["end_line"] - result["start_line"] + 1)
                    telemetry["source_lines_retrieved"] += lines_got
            elif tool_name == "get_frame_variables":
                if isinstance(result, dict):
                    vars_got = len(result)
                    telemetry["variables_retrieved"] += vars_got
                    
            logger.info(json.dumps({
                "event": "retrieval_result",
                "execution_id": execution_id,
                "step": telemetry["mcp_calls"],
                "mcp_tool_name": tool_name,
                "context_size": chars,
                "relevance": relevance,
                "events_retrieved": events_got,
                "source_lines_retrieved": lines_got,
                "variables_retrieved": vars_got
            }))
            
            state["remaining_budget"] -= 1
            
            if state["remaining_budget"] == 0:
                logger.info(json.dumps({
                    "event": "budget_limit_reached",
                    "execution_id": execution_id
                }))

        telemetry["investigation_directions"] = list(telemetry["investigation_directions"])
        telemetry["time_spent"] = time.time() - start_time
        
        final_context = json.dumps(state["known_context"], indent=2)
        chars, _ = self._size(final_context)
        telemetry["total_curated_context_size"] = chars
        
        logger.info(json.dumps({
            "event": "curation_summary",
            "execution_id": execution_id,
            "mcp_calls": telemetry["mcp_calls"],
            "events_retrieved": telemetry["events_retrieved"],
            "source_lines_retrieved": telemetry["source_lines_retrieved"],
            "variables_retrieved": telemetry["variables_retrieved"],
            "total_curated_context_size": chars,
            "investigation_depth": telemetry["investigation_depth"],
            "time_spent": telemetry["time_spent"]
        }))
        
        return CurationResult(context=final_context, telemetry=telemetry)
