from __future__ import annotations

import json
import os
from typing import Any

from backend.llm.base import SummaryInput


class AgentFrameworkSummaryProvider:
    provider_name = "agent-framework"

    def __init__(self, model: str | None = None, env_file_path: str | None = None) -> None:
        self.model_name = model or ""
        self._explicit_model = model
        self._env_file_path = env_file_path
        self._client: Any | None = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            from agent_framework import Message
            from agent_framework.openai import OpenAIChatClient
        except ImportError as exc:
            raise RuntimeError(
                "Agent Framework OpenAI provider is not installed. "
                "Install optional deps: pip install agent-framework agent-framework-openai"
            ) from exc

        has_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"))
        has_model = bool(self._explicit_model or os.getenv("OPENAI_CHAT_MODEL") or os.getenv("OPENAI_MODEL") or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"))
        if not has_key:
            raise RuntimeError(
                "provider=agent-framework requires OPENAI_API_KEY (or AZURE_OPENAI_API_KEY)."
            )
        if not has_model:
            raise RuntimeError(
                "provider=agent-framework requires a model. Set --model, OPENAI_CHAT_MODEL, OPENAI_MODEL, or AZURE_OPENAI_CHAT_DEPLOYMENT."
            )

        kwargs: dict[str, Any] = {}
        if self._explicit_model:
            kwargs["model"] = self._explicit_model
        if self._env_file_path:
            kwargs["env_file_path"] = self._env_file_path

        self._client = OpenAIChatClient(**kwargs)
        self._Message = Message
        self.model_name = self._explicit_model or os.getenv("OPENAI_CHAT_MODEL") or os.getenv("OPENAI_MODEL") or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT") or ""
        return self._client

    async def summarize(self, summary_input: SummaryInput) -> dict[str, Any]:
        client = self._get_client()
        response = await client.get_response([
            self._Message("system", ["You produce valid JSON only."]),
            self._Message("user", [summary_input.prompt]),
        ])

        text = None
        try:
            text = getattr(response.messages[0], "text", None)
        except Exception:
            text = None
        if not text:
            text = str(response)

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Provider returned non-JSON output for paper_id={summary_input.paper_id}") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Provider output must be a JSON object")

        payload.setdefault("paper_id", summary_input.paper_id)
        return payload
