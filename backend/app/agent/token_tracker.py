"""
Token usage tracking callback for LangChain models.
Extracts real token usage metadata directly from LLM provider responses (ChatOpenRouter / LangChain).
Distinguishes between actual token usage (including 0) and missing/unavailable metadata.
"""

from typing import Any, Optional
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class TokenUsageCallback(BaseCallbackHandler):
    """
    Thread-safe callback handler to capture exact input, output,
    and total token usage metadata directly from the LLM provider.
    """

    def __init__(self) -> None:
        super().__init__()
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.total_tokens: int = 0
        self.calls: int = 0
        self.usage_available: bool = False
        self.records: list[dict[str, Any]] = []

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self.calls += 1
        found_usage = False
        call_input = 0
        call_output = 0
        call_total = 0

        # 1. Primary: Extract from AIMessage.usage_metadata
        if response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    msg = getattr(gen, "message", None)
                    if msg and getattr(msg, "usage_metadata", None):
                        um = msg.usage_metadata
                        if isinstance(um, dict) and any(k in um for k in ("input_tokens", "output_tokens", "total_tokens")):
                            call_input += int(um.get("input_tokens") or 0)
                            call_output += int(um.get("output_tokens") or 0)
                            call_total += int(um.get("total_tokens") or (call_input + call_output))
                            found_usage = True

        # 2. Fallback: Extract from LLMResult.llm_output['token_usage']
        if not found_usage and response.llm_output and "token_usage" in response.llm_output:
            tu = response.llm_output["token_usage"]
            if isinstance(tu, dict) and any(k in tu for k in ("prompt_tokens", "completion_tokens", "total_tokens")):
                call_input += int(tu.get("prompt_tokens") or tu.get("input_tokens") or 0)
                call_output += int(tu.get("completion_tokens") or tu.get("output_tokens") or 0)
                call_total += int(tu.get("total_tokens") or (call_input + call_output))
                found_usage = True

        if found_usage:
            self.usage_available = True
            self.input_tokens += call_input
            self.output_tokens += call_output
            self.total_tokens += call_total if call_total > 0 else (call_input + call_output)

        self.records.append({
            "call_index": self.calls,
            "input_tokens": call_input if found_usage else None,
            "output_tokens": call_output if found_usage else None,
            "total_tokens": call_total if found_usage else None,
            "available": found_usage,
        })

    @property
    def safe_input_tokens(self) -> Optional[int]:
        return self.input_tokens if self.usage_available else None

    @property
    def safe_output_tokens(self) -> Optional[int]:
        return self.output_tokens if self.usage_available else None

    @property
    def safe_total_tokens(self) -> Optional[int]:
        return self.total_tokens if self.usage_available else None

    def reset(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.calls = 0
        self.usage_available = False
        self.records = []
