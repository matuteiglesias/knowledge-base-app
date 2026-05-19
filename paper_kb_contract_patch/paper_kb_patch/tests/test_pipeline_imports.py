
def test_embed_runner_imports_kb_embedding():
    import pipeline.producer.embed_runner as er
    assert er.embed_records.__module__.startswith("kb.embedding")
