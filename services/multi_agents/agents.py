"""
HSAAI Multi-Agent System — Production Implementation (v4.0 — AI-IMPROVEMENTS)

AI FIX: Replaced fake agents that returned static template strings with
real LLM-backed agents that perform actual AI inference via the LLM gateway.
Tool execution is now routed to actual backend services.

v4.0 (AI-IMPROVEMENTS):
  - SupervisorAgent enhanced with intent classification + confidence
    scoring + clarification threshold + planning + multi-agent
    orchestration + reflection + self-correction.
  - The original v3.0 `route()` is preserved for backward compatibility
    (it now delegates to `route_with_confidence()` and returns an
    `AgentDecision` augmented with the v4.0 fields).
"""
import os
import re
import httpx
from dataclasses import dataclass, field
from typing import Literal, Optional
from datetime import datetime, timezone

import logging

logger = logging.getLogger("hsaai.multi_agents")

AgentKind = Literal["hr", "finance", "executive", "document", "general"]

LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm_gateway:8090")
# FIX v5.0 (P0): Updated default to use Docker service name (hyphen, not underscore).
RAG_ENGINE_URL = os.getenv("RAG_ENGINE_URL", "http://rag-service:8030")
BACKEND_CORE_URL = os.getenv("BACKEND_CORE_URL", "http://backend:8000")

# v4.0: Reflection / self-correction thresholds.
DEFAULT_ROUTE_CONFIDENCE_THRESHOLD = 0.6  # below → ask for clarification
DEFAULT_REFLECTION_QUALITY_THRESHOLD = 0.6  # below → regenerate
DEFAULT_MAX_REGENERATIONS = 1  # cap self-correction loops


# ─────────────────────────────────────────────────────────────────────
# v4.0 — Intent classification keyword dictionaries (Arabic + English)
# ─────────────────────────────────────────────────────────────────────

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "hr": [
        "salary", "employee", "hr", "leave", "payroll", "vacation",
        "benefits", "onboarding", "performance", "training",
        # Arabic:
        "موظف", "رواتب", "إجازة", "اجازة", "موارد بشرية", "الراتب",
        "استحقاقات", "تعيين", "أداء", "تدريب",
    ],
    "finance": [
        "budget", "invoice", "finance", "cost", "expense", "revenue",
        "p&l", "forecast", "tax", "audit",
        # Arabic:
        "ميزانية", "فاتورة", "مالي", "تكلفة", "المالية", "إيرادات",
        "أرباح وخسائر", "توقعات", "ضريبة", "تدقيق",
    ],
    "executive": [
        "strategy", "kpi", "okr", "board", "executive", "ceo", "cfo",
        "cto", "performance", "risk", "summary", "report",
        # Arabic:
        "استراتيجية", "مؤشر", "تنفيذي", "مجلس الإدارة", "أداء",
        "مخاطر", "ملخص", "تقرير",
    ],
    "document": [
        "document", "pdf", "file", "contract", "agreement", "policy",
        "memo", "directive", "upload",
        # Arabic:
        "ملف", "وثيقة", "مستند", "عقد", "اتفاقية", "سياسة",
        "تعميم", "رفع",
    ],
    "general": [
        "help", "hello", "hi", "thanks", "what", "how", "why",
        # Arabic:
        "مساعدة", "مرحبا", "أهلا", "ماذا", "كيف", "لماذا",
    ],
}

# v4.0 — Signals that a query is *complex* (multi-step) and warrants
# planning + multi-agent orchestration.
_COMPLEX_QUERY_SIGNALS = [
    r"\band\b", r"\bthen\b", r"\bafter that\b", r"\bcompare\b",
    r"\bversus\b", r"\bvs\.?\b", r"\banalyze\b", r"\bsummarize\b",
    r"\bبعد ذلك\b", r"\bمقارنة\b", r"\bحلل\b", r"\bاختصر\b",
    r"\bثم\b", r"\bوأيضاً?\b",
]


@dataclass
class AgentDecision:
    agent: AgentKind
    reason: str
    confidence: float = 0.75
    # v4.0 additions:
    needs_clarification: bool = False
    clarification_question: str = ""
    secondary_agent: Optional[AgentKind] = None  # for multi-agent chaining
    plan: list[str] = field(default_factory=list)


@dataclass
class ToolResult:
    tool: str
    output: dict


@dataclass
class AgentMemory:
    turns: list[dict] = field(default_factory=list)

    def remember(self, tenant_id: str, workspace_id: str, agent: str, message: str):
        self.turns.append({
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "agent": agent,
            "message": message,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        self.turns = self.turns[-200:]

    def recent(self, tenant_id: str, workspace_id: str, limit: int = 5):
        return [
            t for t in self.turns
            if t["tenant_id"] == tenant_id and t["workspace_id"] == workspace_id
        ][-limit:]


class SupervisorAgent:
    """Routes messages to appropriate domain agents using intent classification.

    v4.0 enhancements:
      - Multi-signal intent classification (keyword + script-aware).
      - Confidence scoring — if confidence < threshold, request
        clarification instead of guessing.
      - Multi-agent orchestration — complex queries (compare/analyze/
        multi-step) can chain multiple agents.
      - Planning — decompose complex queries into steps.
      - Reflection — after a response is generated, self-evaluate its
        quality (via `_reflect()`).
      - Self-correction — if quality < threshold, regenerate (up to
        `max_regenerations` times).
    """

    def __init__(
        self,
        *,
        confidence_threshold: float = DEFAULT_ROUTE_CONFIDENCE_THRESHOLD,
        reflection_quality_threshold: float = DEFAULT_REFLECTION_QUALITY_THRESHOLD,
        max_regenerations: int = DEFAULT_MAX_REGENERATIONS,
    ):
        self.confidence_threshold = float(confidence_threshold)
        self.reflection_quality_threshold = float(reflection_quality_threshold)
        self.max_regenerations = int(max_regenerations)

    # ── Backward-compatible route() ─────────────────────────────────

    def route(self, message: str) -> AgentDecision:
        """Route a message to the best agent.

        v4.0: This is a thin facade over `route_with_confidence()` that
        preserves the v3.0 signature. The returned `AgentDecision`
        includes the new v4.0 fields (`needs_clarification`,
        `clarification_question`, `secondary_agent`, `plan`).
        """
        return self.route_with_confidence(message)

    # ── v4.0 — Intent classification + confidence ──────────────────

    def route_with_confidence(self, message: str) -> AgentDecision:
        """Classify the message intent and return a routing decision.

        Confidence is computed as:
            top_dept_hits / total_dept_hits
        where only the department pools (hr/finance/executive/document)
        are counted. The `general` pool is excluded from the
        denominator because its keywords ("what", "how", "hello") are
        generic and would otherwise dilute the department signal.

        Multi-agent chaining: if the runner-up is within 1 hit of the
        leader AND the leader's confidence is < 0.75, we set
        `secondary_agent` to the runner-up so the caller can fan-out.
        """
        if not message or not message.strip():
            return AgentDecision(
                agent="general",
                reason="empty_message",
                confidence=0.0,
                needs_clarification=True,
                clarification_question="Could you please rephrase or provide more detail?",
            )

        m = (message or "").lower()
        # Compute department-only scores (exclude "general" pool).
        dept_scores: dict[str, int] = {}
        general_hits = 0
        for dept, keywords in _INTENT_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in m)
            if dept == "general":
                general_hits = hits
                continue
            if hits > 0:
                dept_scores[dept] = hits

        if not dept_scores:
            # Only general keywords matched (or nothing matched).
            return AgentDecision(
                agent="general",
                reason="no_dept_keywords_matched",
                confidence=0.0 if general_hits == 0 else 0.3,
                needs_clarification=True,
                clarification_question=(
                    "I'm not sure which department can help with that. Could you "
                    "specify whether your question is about HR, finance, documents, "
                    "or executive topics?\n\n"
                    "غير متأكد من القسم المختص. هل يمكنك تحديد ما إذا كان سؤالك "
                    "متعلقاً بالموارد البشرية أو المالية أو الوثائق أو الشؤون التنفيذية؟"
                ),
            )

        # Sort departments by hit count descending.
        ranked = sorted(dept_scores.items(), key=lambda x: x[1], reverse=True)
        top_dept, top_hits = ranked[0]
        total_hits = sum(dept_scores.values())
        confidence = top_hits / total_hits  # 0.0 - 1.0

        # Multi-agent chaining: if the runner-up is within 1 hit of the
        # leader AND the leader's confidence is < 0.75, set secondary.
        secondary: Optional[AgentKind] = None
        if len(ranked) >= 2:
            runner_dept, runner_hits = ranked[1]
            if runner_hits >= top_hits - 1 and confidence < 0.75:
                secondary = runner_dept  # type: ignore[assignment]

        # Planning: if the query looks complex, decompose.
        plan = self.plan(message, top_dept, secondary)

        # Clarification gate.
        needs_clarification = confidence < self.confidence_threshold
        clarification = ""
        if needs_clarification:
            clarification = (
                f"I see your question might relate to {top_dept}. Could you "
                f"confirm or clarify what specific {top_dept} information you need?"
            )

        return AgentDecision(
            agent=top_dept,  # type: ignore[arg-type]
            reason=f"intent_classification_hits={top_hits}/{total_hits}",
            confidence=round(confidence, 4),
            needs_clarification=needs_clarification,
            clarification_question=clarification,
            secondary_agent=secondary,
            plan=plan,
        )

    # ── v4.0 — Planning ────────────────────────────────────────────

    def plan(self, message: str, primary: str, secondary: Optional[str] = None) -> list[str]:
        """Decompose a complex query into a step-by-step plan.

        Returns an empty list for simple queries. For complex queries
        (containing compare/analyze/then/multi-step signals), returns
        a list of step descriptions.
        """
        m_lower = (message or "").lower()
        is_complex = any(re.search(p, m_lower) for p in _COMPLEX_QUERY_SIGNALS)
        if not is_complex and not secondary:
            return []

        steps: list[str] = []
        # Step 1: retrieve primary-agent context.
        steps.append(f"Retrieve {primary} context via RAG search")
        if secondary:
            steps.append(f"Retrieve {secondary} context via RAG search (multi-agent fan-out)")
        # Step 2: if "compare", add comparison step.
        if "compare" in m_lower or "versus" in m_lower or "vs" in m_lower or "مقارنة" in m_lower:
            steps.append("Compare the retrieved contexts and identify differences/similarities")
        # Step 3: if "summarize"/"analyze", add synthesis step.
        if "summarize" in m_lower or "analyze" in m_lower or "ملخص" in m_lower or "حلل" in m_lower:
            steps.append("Synthesize a concise summary from the retrieved contexts")
        # Step 4: always add citation step.
        steps.append("Generate response with inline citations and verify groundedness")
        # Step 5: reflection.
        steps.append("Self-evaluate response quality; regenerate if below threshold")
        return steps

    # ── v4.0 — Reflection ──────────────────────────────────────────

    def reflect(self, message: str, response: str, context: str = "") -> dict:
        """Self-evaluate the quality of a generated response.

        Returns a dict with:
          - quality: float in [0, 1] (composite score)
          - grounded: bool — response has at least one citation
          - relevant: bool — response shares tokens with the context
          - complete: bool — response length is reasonable
          - regenerate: bool — quality < reflection_quality_threshold
        """
        if not response or not response.strip():
            return {
                "quality": 0.0,
                "grounded": False,
                "relevant": False,
                "complete": False,
                "regenerate": True,
                "reason": "empty_response",
            }

        # Grounded: at least one [n] citation.
        has_citation = bool(re.search(r"\[\d+\]", response))
        # Relevant: token overlap between response and context.
        resp_tokens = set(re.findall(r"\w+", response.lower()))
        ctx_tokens = set(re.findall(r"\w+", (context or "").lower()))
        overlap = len(resp_tokens & ctx_tokens) / max(1, len(resp_tokens))
        relevant = overlap >= 0.2
        # Complete: at least 30 chars and ends with a sentence terminator.
        complete = len(response) >= 30 and response.rstrip()[-1:] in ".!?؟"

        # Composite quality score.
        quality = 0.0
        quality += 0.35 if has_citation else 0.0
        quality += 0.35 * overlap  # 0..0.35
        quality += 0.20 if complete else 0.0
        quality += 0.10  # base score (response exists)

        regenerate = quality < self.reflection_quality_threshold

        return {
            "quality": round(quality, 4),
            "grounded": has_citation,
            "relevant": relevant,
            "complete": complete,
            "regenerate": regenerate,
            "overlap": round(overlap, 4),
            "reason": "below_threshold" if regenerate else "ok",
        }

    # ── v4.0 — Self-correction orchestrator ────────────────────────

    async def run_with_self_correction(
        self,
        agent: "BaseAgent",
        message: str,
        context: str = "",
        memory: list[dict] | None = None,
        tenant_id: str = "default",
        workspace_id: str = "default",
    ) -> dict:
        """Run an agent, reflect on its output, and regenerate if needed.

        Up to `max_regenerations` retries. Each regeneration appends a
        "be more grounded / cite your sources" hint to the prompt.
        """
        last_result: dict = {}
        last_quality = 0.0
        hint = ""
        for attempt in range(self.max_regenerations + 1):
            effective_message = message
            if hint:
                effective_message = f"{message}\n\n[Self-correction hint: {hint}]"
            result = await agent.run(
                effective_message, context=context, memory=memory,
                tenant_id=tenant_id, workspace_id=workspace_id,
            )
            reflection = self.reflect(message, result.get("answer", ""), context)
            result["reflection"] = reflection
            result["attempt"] = attempt
            if not reflection["regenerate"]:
                return result
            last_result = result
            last_quality = reflection["quality"]
            # Hint for next attempt.
            if not reflection["grounded"]:
                hint = "Your previous answer had no inline citations. Cite sources with [1], [2]."
            elif not reflection["relevant"]:
                hint = "Your previous answer was not well-grounded in the retrieved context."
            elif not reflection["complete"]:
                hint = "Your previous answer was incomplete. Provide a complete response."
            else:
                hint = "Improve the quality and grounding of your answer."
            logger.info(
                "Supervisor self-correction: agent=%s attempt=%d quality=%.2f — regenerating",
                getattr(agent, "name", "unknown"), attempt, last_quality,
            )
        return last_result


class BaseAgent:
    """Base agent with REAL LLM inference via the LLM gateway."""
    name = "base"
    domain = "general"
    tools = ["rag_search", "policy_lookup", "summarizer"]  # declared capabilities
    executed_tools = ["rag_search"]  # actually wired to runtime
    system_prompt = "You are HSAAI, a private enterprise AI assistant. Respond in Arabic. Be helpful, accurate, and cite internal sources when available."

    async def run(self, message: str, context: str = "", memory: list[dict] | None = None, tenant_id: str = "default", workspace_id: str = "default") -> dict:
        # FIX B-03: Method is now async and awaits all internal async calls.
        # Was sync → called async _get_rag_context/_call_llm without await → returned coroutines.
        # Also removed asyncio.run() inside what is now an async context (was raising RuntimeError).
        import asyncio
        tools_executed_list = []
        tool_results = {}

        # Try to import the tool registry and execute declared tools
        try:
            import sys as _sys
            import os as _os
            _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), '..', '..', 'packages'))
            from common.tool_registry import dispatch_tool

            # Execute each declared tool that's actually registered
            for tool_name in self.tools:
                try:
                    # Build args based on tool type
                    if tool_name == "rag_search":
                        args = {"query": message, "top_k": 5}
                    elif tool_name == "policy_lookup":
                        args = {"policy_name": message}
                    elif tool_name == "summarizer":
                        args = {"text": message}
                    elif tool_name == "invoice_lookup":
                        # Extract invoice ID from message (simple heuristic)
                        import re
                        match = re.search(r'\b[A-Z]{2,4}-?\d{3,6}\b', message)
                        args = {"invoice_id": match.group() if match else "unknown"}
                    elif tool_name == "budget_summary":
                        args = {"department": self.domain}
                    elif tool_name == "kpi_summary":
                        args = {"department": self.domain}
                    elif tool_name == "risk_analysis":
                        args = {"department": self.domain}
                    elif tool_name == "document_extract":
                        args = {"doc_id": message}
                    elif tool_name == "citation_builder":
                        args = {"results": []}  # populated after RAG search
                    elif tool_name == "employee_lookup":
                        import re
                        match = re.search(r'\bEMP-\d+\b', message)
                        args = {"employee_id": match.group() if match else "unknown"}
                    else:
                        # Skip unknown tools (e.g., "employee_knowledge_base" was renamed)
                        continue

                    # FIX B-03: await directly — we are already inside an async function.
                    result = await dispatch_tool(
                        tool_name,
                        args,
                        {"tenant_id": tenant_id, "workspace_id": workspace_id, "user_id": "agent"},
                    )
                    if result.get("success"):
                        tools_executed_list.append(tool_name)
                        tool_results[tool_name] = result
                except (ValueError, Exception) as exc:
                    logger.debug("Tool %s skipped: %s", tool_name, exc)
        except ImportError:
            logger.warning("tool_registry not available — running without tool dispatch")

        # Step 1: Get RAG context — await the async method
        rag_context, rag_results_count = await self._get_rag_context(message, tenant_id, workspace_id)

        # Step 2: Build the full prompt with context + tool results
        full_prompt = message
        context_parts = []
        if rag_context:
            context_parts.append(f"Internal Context:\n{rag_context}")
        if tool_results:
            for tool_name, result in tool_results.items():
                if result.get("success"):
                    context_parts.append(f"Tool '{tool_name}' result: {str(result)[:500]}")
        if context_parts:
            full_prompt = "\n\n".join(context_parts) + f"\n\nUser Question: {message}"

        # Step 3: Call LLM for real inference — await the async method
        answer = await self._call_llm(full_prompt)

        # Step 4: If LLM fails, try RAG-only fallback
        if not answer and rag_context:
            answer = f"Based on available internal sources:\n\n{rag_context}"
        elif not answer:
            answer = "Unable to generate a response. The AI service is currently unavailable. Please try again later."

        return {
            "agent": self.name,
            "domain": self.domain,
            "answer": answer,
            "context_used": bool(rag_context),
            "memory_turns_used": len(memory or []),
            "tools_available": self.tools,
            "tools_executed": tools_executed_list,  # v3.0: real execution list
            "tool_results": tool_results,  # v3.0: actual tool outputs
            "rag_results_count": rag_results_count,
        }

    async def _get_rag_context(self, query: str, tenant_id: str, workspace_id: str) -> tuple[str, int]:
        """Retrieve RAG context for the query. Returns (formatted, count)."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{RAG_ENGINE_URL}/v1/search",
                    json={"query": query, "tenant_id": tenant_id, "workspace_id": workspace_id, "top_k": 5},
                )
                if response.status_code < 400:
                    results = response.json().get("results", [])
                    formatted = "\n".join([f"[{i+1}] {r.get('text', '')[:500]}" for i, r in enumerate(results[:5])])
                    return formatted, len(results)
        except Exception as exc:
            logger.warning("RAG context retrieval failed for %s: %s", self.name, exc)
        return "", 0

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM gateway for real AI inference."""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{LLM_GATEWAY_URL}/v1/generate",
                    json={"prompt": prompt, "system": self.system_prompt, "temperature": 0.2, "max_tokens": 1024},
                )
                if response.status_code < 400:
                    return response.json().get("text", "").strip()
        except Exception as exc:
            logger.error("LLM inference failed for %s: %s", self.name, exc)
        return ""


class HRAgent(BaseAgent):
    name = "HR Agent"
    domain = "human_resources"
    tools = ["policy_lookup", "employee_knowledge_base", "rag_search"]
    system_prompt = "You are HSAAI HR Assistant. Help with HR policies, employee services, leave, and benefits. Respond in Arabic. Maintain confidentiality."


class FinanceAgent(BaseAgent):
    name = "Finance Agent"
    domain = "finance"
    tools = ["invoice_lookup", "budget_summary", "rag_search"]
    system_prompt = "You are HSAAI Finance Assistant. Help with budgets, invoices, costs, and financial reports. Respond in Arabic. Follow financial compliance rules."


class ExecutiveAgent(BaseAgent):
    name = "Executive Agent"
    domain = "executive"
    tools = ["kpi_summary", "risk_analysis", "rag_search"]
    system_prompt = "You are HSAAI Executive Assistant. Provide KPI summaries, risk analysis, and strategic insights. Respond in Arabic. Be concise and data-driven."


class DocumentAgent(BaseAgent):
    name = "Document Agent"
    domain = "documents"
    tools = ["document_extract", "rag_search", "citation_builder"]
    system_prompt = "You are HSAAI Document Assistant. Help analyze documents, extract key information, and cite sources. Respond in Arabic. Always provide citations."


class GeneralAgent(BaseAgent):
    name = "General Agent"
    domain = "general"
    tools = ["rag_search", "summarizer"]


AGENTS = {
    "hr": HRAgent(),
    "finance": FinanceAgent(),
    "executive": ExecutiveAgent(),
    "document": DocumentAgent(),
    "general": GeneralAgent(),
}
MEMORY = AgentMemory()
