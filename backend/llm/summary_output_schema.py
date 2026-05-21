from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SuggestedTags(BaseModel):
    method_tags: list[str] = Field(default_factory=list)
    data_tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class SummaryLLMOutput(BaseModel):
    one_line: str
    research_question: str
    data: str
    method: str
    main_contribution: str
    limitations: str
    relevance_to_thesis: str
    suggested_tags: SuggestedTags = Field(default_factory=SuggestedTags)
    confidence: str
    warnings: list[str] = Field(default_factory=list)

    # Ignore extra LLM keys but require all contract keys above.
    model_config = ConfigDict(extra="ignore")
