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

    def list_chunks(self, paper_id: str, offset: int = 0, limit: int = 200, q=None):
        if paper_id != "p1":
            return {"n": 0, "chunks": []}
        return {"n": 1, "chunks": [{"chunk_id": "c1", "paper_id": "p1", "text": "alpha beta", "chunk_index": 0, "char_len": 10, "meta": {}}]}

    def get_chunk(self, paper_id: str, chunk_id: str):
        if paper_id == "p1" and chunk_id == "c1":
            return {"chunk_id": "c1", "paper_id": "p1", "text": "alpha beta", "chunk_index": 0, "char_len": 10, "meta": {}}
        return None

    def semantic_search(self, q: str, k: int = 6, paper_id=None):
        return [{"id": "c1", "text": "alpha beta", "score": 0.5, "meta": {}, "paper_id": "p1"}]

    def counts(self):
        return {"n_papers": 1, "n_chunks": 1, "n_artifacts": 2, "n_invalid_artifacts": 1, "n_skipped_chunks": 0, "dedupe_collisions": 0}

    def diagnostics(self):
        return {"warnings": ["invalid artifact: x.chunk_set.json"]}


def _client():
    app.state.storage = StubStorage()
    app.state.cache_ready = True
    return TestClient(app)


def test_corpus_and_health_endpoints():
    c = _client()
    r = c.get('/api/corpus')
    assert r.status_code == 200
    assert r.json()['storage_backend'] == 'chunk-set'

    h = c.get('/api/corpus/health')
    assert h.status_code == 200
    body = h.json()
    assert body['n_papers'] == 1
    assert body['n_invalid_artifacts'] == 1
    assert body['status'] == 'warning'


def test_paper_detail_and_missing_404():
    c = _client()
    ok = c.get('/api/papers/p1')
    assert ok.status_code == 200
    assert ok.json()['paper_id'] == 'p1'

    miss = c.get('/api/papers/missing')
    assert miss.status_code == 404


def test_paper_chunks_route_still_lists_chunks():
    c = _client()
    r = c.get('/api/papers/p1/chunks')
    assert r.status_code == 200
    assert r.json()['total'] == 1
    assert r.json()['chunks'][0]['chunk_id'] == 'c1'
