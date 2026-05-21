from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.llm.agent_framework_provider import AgentFrameworkSummaryProvider
from backend.exports.generate_summaries import _validate_summary_payload


def test_agent_framework_provider_import_is_lazy():
    provider = AgentFrameworkSummaryProvider()
    assert provider.provider_name == "agent-framework"


def test_agent_framework_provider_missing_package_error(monkeypatch):
    provider = AgentFrameworkSummaryProvider(model="gpt-4o-mini")

    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("agent_framework"):
            raise ImportError("missing agent framework")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError, match="not installed"):
        provider._get_client()


def test_summary_output_schema_rejects_missing_required_fields():
    with pytest.raises(ValueError, match="Invalid LLM summary output"):
        _validate_summary_payload({"one_line": "only"}, "paper_1234abcde0")


def test_summary_output_schema_ignores_extra_fields():
    payload = _validate_summary_payload(
        {
            "one_line": "x",
            "research_question": "",
            "data": "",
            "method": "",
            "main_contribution": "",
            "limitations": "",
            "relevance_to_thesis": "",
            "suggested_tags": {"method_tags": [], "data_tags": []},
            "confidence": "medium",
            "warnings": [],
            "extra_debug": "ignore me",
        },
        "paper_1234abcde0",
    )
    assert "extra_debug" not in payload


def test_agent_framework_provider_non_json_rejected():
    provider = AgentFrameworkSummaryProvider(model="gpt-4o-mini")

    class _RespMsg:
        text = "not json"

    class _Resp:
        messages = [_RespMsg()]

    class _Client:
        async def get_response(self, *args, **kwargs):
            return _Resp()

    provider._Message = lambda role, parts: (role, parts)
    provider._get_client = lambda: _Client()  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="non-JSON"):
        asyncio.run(provider.summarize(type("SI", (), {"paper_id": "paper_1234abcde0", "prompt": "x", "context": {}})()))


def test_agent_framework_provider_agent_mode_uses_agent_run():
    provider = AgentFrameworkSummaryProvider(model="gpt-4o-mini", agent_mode="agent")

    class _Resp:
        output_text = '{"one_line":"x","research_question":"","data":"","method":"","main_contribution":"","limitations":"","relevance_to_thesis":"","suggested_tags":{"method_tags":[],"data_tags":[]},"confidence":"medium","warnings":[]}'

    class _Agent:
        async def run(self, **kwargs):
            return _Resp()

    class _Client:
        def as_agent(self, **kwargs):
            return _Agent()

    provider._get_client = lambda: _Client()  # type: ignore[method-assign]
    out = asyncio.run(provider.summarize(type("SI", (), {"paper_id": "paper_1234abcde0", "prompt": "x", "context": {}})()))
    assert out["one_line"] == "x"
