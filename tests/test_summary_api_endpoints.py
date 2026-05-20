from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


class StubStorage:
    backend_name = "chunk-set"
    loaded_at = 123.4

    def __init__(self):
        self._papers = [{"paper_id": "p1", "title": "Paper 1", "authors": ["Ada"], "n_chunks": 1, "preview": "x"}]

    def list_papers(self):
        return self._papers

    def get_paper(self, paper_id: str):
        for p in self._papers:
            if p["paper_id"] == paper_id:
                return p
        return {}




def _write_chunk_set():
    from pipeline.corpus import resolve_corpus_paths
    paths = resolve_corpus_paths("apitest_api").ensure_dirs()
    import shutil
    shutil.rmtree(paths.root, ignore_errors=True)
    paths = resolve_corpus_paths("apitest_api").ensure_dirs()
    sets = paths.chunk_sets
    payload = {
        "artifact_kind": "chunk_set",
        "paper_meta": {"paper_id": "p1", "title": "Paper 1"},
        "chunks": [{"chunk_id": "p1_c0", "paper_id": "p1", "text": "alpha", "chunk_index": 0, "char_len": 5, "metadata": {"title": "Paper 1"}}],
    }
    (sets / "a.chunk_set.json").write_text(__import__("json").dumps(payload), encoding="utf-8")

def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_KB_CORPUS", "apitest_api")
    monkeypatch.chdir(tmp_path)
    app.state.storage = StubStorage()
    app.state.cache_ready = True
    return TestClient(app)


def test_summary_api_flow(tmp_path, monkeypatch):
    _write_chunk_set()
    c = _client(tmp_path, monkeypatch)

    missing = c.get('/api/papers/p1/summary')
    assert missing.status_code == 404

    generated = c.post('/api/papers/p1/summary:generate', json={"provider": "mock", "force": False})
    assert generated.status_code == 200
    body = generated.json()
    assert body["paper_id"] == "p1"

    fetched = c.get('/api/papers/p1/summary')
    assert fetched.status_code == 200
    assert fetched.json()["paper_id"] == "p1"

    again = c.post('/api/papers/p1/summary:generate', json={"provider": "mock", "force": False})
    assert again.status_code == 200
    assert again.json()["generated_at"] == body["generated_at"]

    force = c.post('/api/papers/p1/summary:generate', json={"provider": "mock", "force": True})
    assert force.status_code == 200
    assert force.json()["generated_at"] != body["generated_at"]


def test_summary_missing_paper_404_and_url_encoded(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    missing = c.get('/api/papers/not%20there/summary')
    assert missing.status_code == 404
    missing_post = c.post('/api/papers/not%20there/summary:generate', json={"provider": "mock", "force": False})
    assert missing_post.status_code == 404
