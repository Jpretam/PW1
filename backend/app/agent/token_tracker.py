"""
Token usage tracking callback for LangChain models.
Extracts real token usage metadata directly from LLM provider responses (ChatOpenRouter / LangChain).
"""

from typing import Any
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
        self.records: list[dict[str, int]] = []

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self.calls += 1
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
                        if isinstance(um, dict):
                            call_input += int(um.get("input_tokens", 0) or 0)
                            call_output += int(um.get("output_tokens", 0) or 0)
                            call_total += int(um.get("total_tokens", 0) or 0)

        # 2. Fallback: Extract from LLMResult.llm_output['token_usage']
        if call_total == 0 and response.llm_output and "token_usage" in response.llm_output:
            tu = response.llm_output["token_usage"]
            if isinstance(tu, dict):
                call_input += int(tu.get("prompt_tokens", 0) or tu.get("input_tokens", 0) or 0)
                call_output += int(tu.get("completion_tokens", 0) or tu.get("output_tokens", 0) or 0)
                call_total += int(tu.get("total_tokens", 0) or (call_input + call_output))

        self.input_tokens += call_input
        self.output_tokens += call_output
        self.total_tokens += call_total if call_total > 0 else (call_input + call_output)

        self.records.append({
            "call_index": self.calls,
            "input_tokens": call_input,
            "output_tokens": call_output,
            "total_tokens": call_total,
        })

    def reset(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.calls = 0
        self.records = []
