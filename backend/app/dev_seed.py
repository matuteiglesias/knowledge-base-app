# backend/app/dev_seed.py
from .schemas import PaperMeta
def dev_papers():
    return [
        {
            "paper_id": "dev-1",
            "title": "Dev Paper One",
            "authors": ["A Dev"],
            "n_chunks": 4,
            "preview": "dev preview"
        }
    ]
