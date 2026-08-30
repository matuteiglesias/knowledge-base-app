from __future__ import annotations

import requests
import pytest

from pipeline.adapter import grobid_preflight


class _Response:
    def __init__(self, status_code: int):
        self.status_code = status_code


def test_probe_accepts_method_response_as_reachable(monkeypatch):
    monkeypatch.setattr(grobid_preflight.requests, "get", lambda url, timeout: _Response(405))

    result = grobid_preflight.probe_grobid(url="http://localhost:8070/api/processFulltextDocument")

    assert result["reachable"] is True
    assert result["http_status"] == 405


def test_probe_rejects_server_failure(monkeypatch):
    monkeypatch.setattr(grobid_preflight.requests, "get", lambda url, timeout: _Response(503))

    result = grobid_preflight.probe_grobid(url="http://localhost:8070/api/processFulltextDocument")

    assert result["reachable"] is False
    assert result["error"] == "HTTP 503"


def test_require_grobid_turns_connection_refusal_into_actionable_error(monkeypatch):
    def _refused(url, timeout):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(grobid_preflight.requests, "get", _refused)

    with pytest.raises(RuntimeError) as excinfo:
        grobid_preflight.require_grobid(url="http://localhost:8070/api/processFulltextDocument")

    message = str(excinfo.value)
    assert "GROBID is not reachable" in message
    assert "GROBID_URL" in message
    assert "make corpus-check-grobid" in message
    assert "connection refused" in message
