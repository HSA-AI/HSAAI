"""
HSAAI Shared Keyword Router (v2.0)

Consolidates 3 duplicate keyword-based routing implementations:
  - services/multi_agents/agents.py::SupervisorAgent.route()
  - services/multi_agents/main.py::route_message()
  - services/backend_core/chat/router.py::route_agent()

All three now import from this single source of truth.
"""
import re
from typing import Literal

AgentKind = Literal["hr", "finance", "executive", "document", "it", "general", "supervisor"]

# Keyword map: keyword → agent kind
# Bilingual (English + Arabic)
KEYWORD_MAP = {
    "hr": ["salary", "employee", "hr", "leave", "human resources",
           "موظف", "راتب", "اجاز", "موارد بشرية", "إجازة", "الموارد البشرية"],
    "finance": ["budget", "invoice", "finance", "cost", "payment", "expense",
                "ميزانية", "فاتورة", "مالي", "تكلفة", "مدفوعات", "مصاريف"],
    "executive": ["strategy", "kpi", "board", "executive", "ceo", "cto", "cfo",
                  "استراتيجية", "مؤشر", "تنفيذي", "مجلس", "إدارة تنفيذية"],
    "document": ["document", "pdf", "file", "word", "excel", "powerpoint",
                 "ملف", "وثيقة", "مستند"],
    "it": ["it", "tech", "computer", "network", "server", "software", "hardware",
           "تقنية", "حاسوب", "شبكة", "خادم", "برمجيات"],
}


def route_message(message: str, preferred: str | None = None) -> AgentKind:
    """Route a user message to the appropriate department agent.

    Args:
        message: The user's message text.
        preferred: Optional explicit override (skip keyword detection).

    Returns:
        Agent kind: "hr" | "finance" | "executive" | "document" | "it" | "general"
    """
    if preferred:
        # Validate preferred is a known kind
        if preferred in KEYWORD_MAP or preferred in ("general", "supervisor"):
            return preferred  # type: ignore
        return "general"

    if not message:
        return "general"

    m = message.lower()

    # Check each agent's keywords
    for kind, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in m:
                return kind  # type: ignore

    return "general"


def get_agent_confidence(message: str, route: AgentKind) -> float:
    """Return a confidence score for the routing decision."""
    if route == "general":
        return 0.65
    m = message.lower()
    keywords = KEYWORD_MAP.get(route, [])
    matches = sum(1 for kw in keywords if kw in m)
    if matches == 0:
        return 0.65
    if matches == 1:
        return 0.85
    return 0.95


__all__ = ["route_message", "get_agent_confidence", "AgentKind", "KEYWORD_MAP"]
