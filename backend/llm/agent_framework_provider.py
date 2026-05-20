from __future__ import annotations
import json, os
from backend.llm.base import SummaryInput

class AgentFrameworkSummaryProvider:
    provider_name = "agent-framework"

    def __init__(self) -> None:
        try:
            from agent_framework import Message
            from agent_framework.openai import OpenAIChatClient
        except ImportError as exc:
            raise RuntimeError("Install optional deps: pip install agent-framework-core agent-framework-openai") from exc
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for provider=agent-framework")
        self._Message = Message
        self._client = OpenAIChatClient()
        self.model_name = os.getenv("OPENAI_CHAT_MODEL") or os.getenv("OPENAI_MODEL") or ""

    async def summarize(self, summary_input: SummaryInput) -> dict:
        response = await self._client.get_response([
            self._Message("system", ["You produce valid JSON only."]),
            self._Message("user", [summary_input.prompt]),
        ])
        text = getattr(response.messages[0], "text", None) or "{}"
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model returned non-JSON output for paper_id={summary_input.paper_id}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Model output must be a JSON object")
        payload.setdefault("paper_id", summary_input.paper_id)
        return payload
