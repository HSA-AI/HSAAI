from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func
from backend_core.db.database import Base


class SmartResponseTemplate(Base):
    __tablename__ = "smart_response_templates"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, index=True, default="default", nullable=False)
    workspace_id = Column(String, index=True, default="default", nullable=False)
    rule_name = Column(String, index=True, nullable=False)
    intent = Column(String, index=True, nullable=False)
    keywords_json = Column(Text, default="[]", nullable=False)
    match_type = Column(String, index=True, default="keyword", nullable=False)
    regex_pattern = Column(Text, default="")
    response_text = Column(Text, nullable=False)
    priority = Column(Integer, index=True, default=100)
    enabled = Column(Boolean, index=True, default=True)
    language = Column(String, index=True, default="ar")
    usage_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fallback_count = Column(Integer, default=0)
    created_by = Column(String, index=True, default="system")
    updated_by = Column(String, index=True, default="system")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SmartResponseLog(Base):
    __tablename__ = "smart_response_logs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, index=True, default="default", nullable=False)
    workspace_id = Column(String, index=True, default="default", nullable=False)
    user_id = Column(String, index=True, default="anonymous")
    message = Column(Text, default="")
    matched_rule_id = Column(Integer, index=True, nullable=True)
    intent = Column(String, index=True, default="")
    score = Column(Float, default=0.0)
    response_source = Column(String, index=True, default="llm")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
