from typing import Any

from app.agent.llm import get_llm
from app.agent.mcp_client import get_debugging_tools
from app.agent.models import DebugDiagnosis
from app.agent.curator import ContextCurator


SYSTEM_PROMPT = """
You are an AI debugging agent.

Your job is to diagnose a runtime failure using the provided
curated runtime context.

IMPORTANT RULES:

1. Base your diagnosis on evidence provided in the context.
2. Do not invent runtime values.
3. The diagnosis must clearly explain the actual cause of the
   runtime failure.

Return a structured diagnosis containing:
- diagnosis
- root_cause
- evidence
- suggested_fix
- confidence
"""


class DebuggingAgent:

    def __init__(self):
        self.llm = get_llm()
        self.curator = ContextCurator()
        
        self.structured_model = self.llm.with_structured_output(
            DebugDiagnosis
        )

    async def diagnose(
        self,
        execution_id: str,
        initial_context: str | None = None,
    ) -> DebugDiagnosis:

        # 1. Use the Context Curator to dynamically retrieve relevant runtime context
        curation_result = await self.curator.curate(
            execution_id=execution_id,
            initial_context=initial_context
        )
        
        curated_context = curation_result.context
        telemetry = curation_result.telemetry

        user_prompt = f"""
Diagnose the runtime failure for execution:
execution_id = {execution_id}

Curated Runtime Context:
{curated_context}
"""

        messages = [
            ("system", SYSTEM_PROMPT),
            ("human", user_prompt),
        ]

        # 2. Produce the structured diagnosis using the curated context
        try:
            result = await self.structured_model.ainvoke(messages)
            
            result.execution_id = execution_id
            
            # Extract error from the curated context if possible
            # (Just for backwards compatibility with the schema)
            error_ctx = None
            if "get_error_context" in curated_context:
                # We won't parse it fully here, we'll just leave it None 
                # or we could parse the JSON string.
                pass
                
            result.error = None
            result.queries_used = telemetry.get("tools_used", [])
            
            # Attach telemetry so it can be logged/used
            if not hasattr(result, "telemetry"):
                result.telemetry = telemetry
            
            return result
            
        except Exception as exc:
            return DebugDiagnosis(
                execution_id=execution_id,
                error=None,
                diagnosis=(
                    "The agent received curated context "
                    "but failed to produce structured output: "
                    f"{str(exc)}"
                ),
                root_cause="",
                evidence=[],
                queries_used=telemetry.get("tools_used", []),
                confidence=0.0,
                suggested_fix="No reliable code fix could be generated because structured diagnosis failed.",
            )

    @staticmethod
    def _serialize(value: Any) -> str:
        if isinstance(value, str):
            return value
        return str(value)