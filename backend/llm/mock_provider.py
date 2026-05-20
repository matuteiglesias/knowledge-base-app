from __future__ import annotations
from backend.llm.base import SummaryInput

class MockSummaryProvider:
    provider_name = "mock"
    model_name = "mock-v1"

    def __init__(self) -> None:
        self.calls = 0

    async def summarize(self, summary_input: SummaryInput) -> dict:
        self.calls += 1
        return {
            "paper_id": summary_input.paper_id,
            "one_line": f"Mock summary for {summary_input.paper_id}",
            "research_question": "",
            "data": "",
            "method": "",
            "main_contribution": "",
            "limitations": "",
            "relevance_to_thesis": "",
            "suggested_tags": {"method_tags": [], "data_tags": []},
            "confidence": "medium",
            "warnings": [],
        }
