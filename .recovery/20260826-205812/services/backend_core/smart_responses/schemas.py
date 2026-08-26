from datetime import datetime
from pydantic import BaseModel, Field, field_validator

ALLOWED_MATCH_TYPES = {"exact", "partial", "keyword", "regex"}


class SmartResponseBase(BaseModel):
    rule_name: str = Field(..., min_length=2, max_length=200)
    intent: str = Field(..., min_length=2, max_length=100)
    keywords: list[str] = Field(default_factory=list)
    match_type: str = "keyword"
    regex_pattern: str | None = ""
    response_text: str = Field(..., min_length=1)
    priority: int = 100
    enabled: bool = True
    language: str = "ar"
    workspace_id: str = "default"

    @field_validator("match_type")
    @classmethod
    def validate_match_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ALLOWED_MATCH_TYPES:
            raise ValueError(f"match_type must be one of {sorted(ALLOWED_MATCH_TYPES)}")
        return value


class SmartResponseCreate(SmartResponseBase):
    pass


class SmartResponseUpdate(BaseModel):
    rule_name: str | None = None
    intent: str | None = None
    keywords: list[str] | None = None
    match_type: str | None = None
    regex_pattern: str | None = None
    response_text: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    language: str | None = None
    workspace_id: str | None = None

    @field_validator("match_type")
    @classmethod
    def validate_match_type(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().lower()
        if value not in ALLOWED_MATCH_TYPES:
            raise ValueError(f"match_type must be one of {sorted(ALLOWED_MATCH_TYPES)}")
        return value


class SmartResponseOut(SmartResponseBase):
    id: int
    tenant_id: str
    usage_count: int = 0
    success_count: int = 0
    fallback_count: int = 0
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class MatchResult(BaseModel):
    matched: bool
    agent: str = "HSAAI Enterprise Assistant"
    source: str = "llm"
    intent: str | None = None
    score: float = 0.0
    rule_id: int | None = None
    message: str | None = None


class PriorityUpdate(BaseModel):
    priority: int


class ImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
