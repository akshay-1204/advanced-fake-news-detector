"""Pydantic v2 schemas for chat requests, responses, and LLM structured outputs."""
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class IntentType(str, Enum):
    TODAY_NEWS = "TODAY_NEWS"
    WEATHER = "WEATHER"
    CLAIM_CHECK = "CLAIM_CHECK"
    SMALL_TALK = "SMALL_TALK"


class VerdictType(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED = "UNVERIFIED"


class ConfidenceType(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IntentClassificationResult(BaseModel):
    """Schema expected from prompts/intent_classifier.md"""
    intent: IntentType = Field(default=IntentType.CLAIM_CHECK)
    topic: str = Field(default="general")
    city: Optional[str] = None
    language: str = Field(default="en")
    claim: Optional[str] = None

    @field_validator("intent", mode="before")
    @classmethod
    def normalize_intent(cls, v):
        if isinstance(v, str):
            v_upper = v.strip().upper()
            if v_upper in IntentType.__members__:
                return IntentType(v_upper)
        return IntentType.CLAIM_CHECK


class ClaimJudgeResult(BaseModel):
    """Schema expected from prompts/claim_judge.md"""
    verdict: VerdictType = Field(default=VerdictType.UNVERIFIED)
    reason: str = Field(default="")
    confidence: ConfidenceType = Field(default=ConfidenceType.LOW)
    supporting_chunk_ids: List[int] = Field(default_factory=list)
    reply_language: str = Field(default="en")

    @field_validator("verdict", mode="before")
    @classmethod
    def normalize_verdict(cls, v):
        if isinstance(v, str):
            v_upper = v.strip().upper()
            if v_upper in VerdictType.__members__:
                return VerdictType(v_upper)
        return VerdictType.UNVERIFIED

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v):
        if isinstance(v, str):
            v_lower = v.strip().lower()
            if v_lower in [c.value for c in ConfidenceType]:
                return ConfidenceType(v_lower)
        return ConfidenceType.LOW


class NewsSummaryItem(BaseModel):
    headline: str
    summary: str
    sources: List[str] = Field(default_factory=list)
    article_ids: List[int] = Field(default_factory=list)


class NewsSummarizerResult(BaseModel):
    """Schema expected from prompts/news_summarizer.md"""
    items: List[NewsSummaryItem] = Field(default_factory=list)


class SourceItem(BaseModel):
    outlet: str
    title: str
    link: str
    published_time: Optional[str] = None


class ChatRequest(BaseModel):
    query: str = Field(..., max_length=500, min_length=1, description="User query or news claim (max 500 characters)")
    session_id: Optional[str] = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    intent: str
    verdict: Optional[str] = None
    confidence: Optional[str] = None
    reason: Optional[str] = None
    reply: str
    sources: List[SourceItem] = Field(default_factory=list)
    language: str = "en"


class FAQItem(BaseModel):
    label: str
    query: str
    topic: str
