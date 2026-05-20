from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol

@dataclass(frozen=True)
class SummaryInput:
    paper_id: str
    prompt: str
    context: dict[str, Any]

class SummaryProvider(Protocol):
    async def summarize(self, summary_input: SummaryInput) -> dict[str, Any]:
        ...
