"""Small data contracts shared by sources, research and the UI."""

from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from pydantic_ai import CustomEvent


class SearchHit(BaseModel):
    source_id: str
    document_id: str
    title: str
    url: str
    snippet: str


class Evidence(BaseModel):
    evidence_id: str = ""
    source_id: str
    document_id: str
    title: str
    url: str
    locator: str
    text: str
    truncated: bool = False
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResearchAnswer(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)
    insufficient: bool = False


@dataclass(kw_only=True)
class Progress(CustomEvent):
    message: str


@dataclass(kw_only=True)
class AnswerReady(CustomEvent):
    answer: dict[str, object]
    sources: list[dict[str, object]]
