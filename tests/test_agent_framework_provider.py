from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.llm.agent_framework_provider import AgentFrameworkSummaryProvider


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
