from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.llm import smoke_agent_framework


def test_smoke_main_success(monkeypatch):
    def _fake_run(coro):
        coro.close()
        return 0

    monkeypatch.setattr(smoke_agent_framework.asyncio, "run", _fake_run)
    monkeypatch.setattr(sys, "argv", ["prog", "--prompt", "Return JSON only: {\"ok\": true}", "--agent-mode", "client"])

    rc = smoke_agent_framework.main()
    assert rc == 0


def test_smoke_main_failure(monkeypatch, capsys):
    def _raise(coro):
        coro.close()
        raise RuntimeError("boom")

    monkeypatch.setattr(smoke_agent_framework.asyncio, "run", _raise)
    monkeypatch.setattr(sys, "argv", ["prog", "--prompt", "x"])

    rc = smoke_agent_framework.main()
    err = capsys.readouterr().err
    assert rc == 1
    assert "ERROR: boom" in err
