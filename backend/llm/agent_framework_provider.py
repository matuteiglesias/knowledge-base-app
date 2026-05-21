from __future__ import annotations

import json
import os
from typing import Any

from backend.llm.base import SummaryInput


class AgentFrameworkSummaryProvider:
    provider_name = "agent-framework"

    def __init__(self, model: str | None = None, env_file_path: str | None = None, agent_mode: str = "client") -> None:
        self.model_name = model or ""
        self._explicit_model = model
        self._env_file_path = env_file_path
        self._agent_mode = (agent_mode or "client").strip().lower()
        if self._agent_mode not in {"client", "agent"}:
            raise ValueError("agent_mode must be one of: client, agent")
        self._client: Any | None = None
        self._Message: Any | None = None

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
        has_model = bool(
            self._explicit_model
            or os.getenv("OPENAI_CHAT_MODEL")
            or os.getenv("OPENAI_MODEL")
            or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
        )
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

        try:
            self._client = OpenAIChatClient(**kwargs)
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize agent-framework OpenAI client: {exc}") from exc
        self._Message = Message
        self.model_name = (
            self._explicit_model
            or os.getenv("OPENAI_CHAT_MODEL")
            or os.getenv("OPENAI_MODEL")
            or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
            or ""
        )
        return self._client

    async def _invoke_client_mode(self, prompt: str):
        client = self._get_client()
        return await client.get_response(
            [
                self._Message(
                    "system",
                    [
                        "Return JSON only. Use keys exactly: one_line, research_question, data, method, "
                        "main_contribution, limitations, relevance_to_thesis, suggested_tags, confidence, warnings."
                    ],
                ),
                self._Message("user", [prompt]),
            ],
            response_format={"type": "json_object"},
        )

    async def _invoke_agent_mode(self, prompt: str):
        client = self._get_client()
        instructions = (
            "Return JSON only. Use keys exactly: one_line, research_question, data, method, "
            "main_contribution, limitations, relevance_to_thesis, suggested_tags, confidence, warnings."
        )
        # Prefer as_agent convenience when available; fallback to direct Agent construction.
        agent = None
        as_agent = getattr(client, "as_agent", None)
        if callable(as_agent):
            agent = as_agent(instructions=instructions)
        if agent is None:
            try:
                from agent_framework import Agent
            except ImportError as exc:
                raise RuntimeError("Agent mode requires agent_framework Agent support.") from exc
            agent = Agent(name="paper-summary-agent", instructions=instructions, model_client=client)

        return await agent.run(input=prompt, response_format={"type": "json_object"})

    @staticmethod
    def _coerce_payload(payload: dict[str, Any], paper_id: str) -> dict[str, Any]:
        out = {
            "paper_id": paper_id,
            "one_line": str(payload.get("one_line") or payload.get("summary") or ""),
            "research_question": str(payload.get("research_question") or ""),
            "data": str(payload.get("data") or ""),
            "method": str(payload.get("method") or ""),
            "main_contribution": str(payload.get("main_contribution") or ""),
            "limitations": str(payload.get("limitations") or ""),
            "relevance_to_thesis": str(payload.get("relevance_to_thesis") or ""),
            "suggested_tags": payload.get("suggested_tags") if isinstance(payload.get("suggested_tags"), dict) else {},
            "confidence": str(payload.get("confidence") or "medium").lower(),
            "warnings": payload.get("warnings") if isinstance(payload.get("warnings"), list) else [],
        }
        out["suggested_tags"] = {
            "method_tags": [str(x) for x in (out["suggested_tags"].get("method_tags") or []) if str(x).strip()],
            "data_tags": [str(x) for x in (out["suggested_tags"].get("data_tags") or []) if str(x).strip()],
        }
        if out["confidence"] not in {"low", "medium", "high"}:
            out["confidence"] = "medium"
        return out

    async def summarize(self, summary_input: SummaryInput) -> dict[str, Any]:
        if self._agent_mode == "agent":
            response = await self._invoke_agent_mode(summary_input.prompt)
        else:
            response = await self._invoke_client_mode(summary_input.prompt)

        text = None
        try:
            text = getattr(response.messages[0], "text", None)
        except Exception:
            text = None
        if not text:
            text = getattr(response, "output_text", None)
        if not text:
            text = getattr(response, "text", None)
        if not text:
            text = str(response)

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Provider returned non-JSON output for paper_id={summary_input.paper_id}") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Provider output must be a JSON object")

        return self._coerce_payload(payload, summary_input.paper_id)
