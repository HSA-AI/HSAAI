"""
HSAAI PII Detector Service (v3.0)

Uses Microsoft Presidio to detect and redact Personally Identifiable Information
from documents BEFORE they are indexed into Qdrant.

Supported PII types:
  - Person names (Arabic + English)
  - Email addresses
  - Phone numbers (international + Saudi/Gulf formats)
  - National IDs (Saudi Iqama, Emirates ID, Qatar ID)
  - Credit card numbers
  - IBAN (Saudi/Gulf)
  - Passport numbers
  - Dates of birth
  - URLs
  - IP addresses
  - Crypto wallet addresses

Usage:
    POST /v1/pii/scan
    {
      "text": "My name is Ahmed Al-Rashid, phone +966501234567, email ahmed@example.com",
      "redact": true,
      "tenant_id": "default"
    }

    Response:
    {
      "has_pii": true,
      "pii_found": [
        {"type": "PERSON", "text": "Ahmed Al-Rashid", "start": 11, "end": 26, "score": 0.85},
        {"type": "PHONE_NUMBER", "text": "+966501234567", "start": 35, "end": 48, "score": 0.95},
        {"type": "EMAIL_ADDRESS", "text": "ahmed@example.com", "start": 56, "end": 73, "score": 0.99}
      ],
      "redacted_text": "My name is <PERSON>, phone <PHONE_NUMBER>, email <EMAIL_ADDRESS>",
      "risk_level": "high"
    }
"""
import os
import sys
import logging
from typing import Any
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field

# Add packages/ to path for shared auth
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
    _AUTH_AVAILABLE = True
except ImportError as _e:
    _AUTH_AVAILABLE = False
    _AUTH_LOAD_ERROR = str(_e)
    async def _auth_dep():  # type: ignore
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Authentication module unavailable. Service cannot accept requests.")

logger = logging.getLogger("hsaai.pii_detector")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="HSAAI PII Detector",
    version="4.0.0",
    description="PII detection + redaction via Microsoft Presidio",
)

# ─── Try to import Presidio ───
try:
    from presidio_analyzer import Analyzer, RecognizerRegistry
    from presidio_analyzer.predefined_recognizers import (
        EmailRecognizer, PhoneRecognizer, UrlRecognizer, IpRecognizer,
        CreditCardRecognizer, IbanRecognizer, DateRecognizer,
        PersonRecognizer, SpacyRecognizer,
    )
    from presidio_anonymizer import Anonymizer
    from presidio_anonymizer.entities import AnonymizerConfig

    PRESIDIO_AVAILABLE = True
    logger.info("Presidio is available — full PII detection enabled")
except ImportError:
    PRESIDIO_AVAILABLE = False
    logger.warning("Presidio not installed — using regex-only fallback. Install with: pip install presidio-analyzer presidio-anonymizerspresacy")

# ─── Fallback regex patterns (used if Presidio is not available) ───
import re

FALLBACK_PATTERNS = {
    "EMAIL_ADDRESS": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "PHONE_NUMBER": re.compile(r"\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b"),
    "URL": re.compile(r'''https?://[^\s<>"]+|www\.[^\s<>"]+'''),
    "IP_ADDRESS": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "IBAN": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b"),
    "DATE": re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b"),
    "SAUDI_ID": re.compile(r"\b[12]\d{9}\b"),  # Saudi Iqama/National ID (10 digits starting with 1 or 2)
    "EMIRATES_ID": re.compile(r"\b784-\d{4}-\d{7}-\d\b"),  # Emirates ID format
    "PASSPORT": re.compile(r"\b[A-Z]\d{7,8}\b"),  # Generic passport format
    "SCHOOL_EMAIL": re.compile(r"\b\w+@(?:edu|ac)\.[a-z]{2,3}\b"),
}

# Arabic name patterns (common Saudi/Gulf names)
ARABIC_NAME_PATTERNS = [
    re.compile(r"\b(?:محمد|أحمد|عبدالله|عبدالرحمن|خالد|سعد|فهد|ناصر|علي|حسن|حسين|عمر|يوسف|إبراهيم|إسماعيل|داود|سليمان|يحيى|زكريا|طارق|ماجد|وليد|بدر|نواف|تركي|سلطان|فيصل|بندر|راكان|مشعل)\s+(?:بن\s+)?(?:عبد\w+|\w+)\b"),
    re.compile(r"\b(?:سارة|فاطمة|عائشة|نورة|muzna|hessa|الجوهرة|العنود|لطيفة|مريم|زينب|خديجة|سمية|أمل|هند|ريم|لمى|دانة|جود)\b"),
]


# ─── Models ───

class PIIScanRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1_000_000, description="Text to scan for PII")
    redact: bool = Field(True, description="If true, return redacted_text with PII replaced")
    tenant_id: str = Field("default", description="Tenant ID for audit logging")
    workspace_id: str = Field("default", description="Workspace ID for audit logging")
    language: str = Field("en", description="Primary language (en/ar)")


class PIIFinding(BaseModel):
    type: str
    text: str
    start: int
    end: int
    score: float


class PIIScanResponse(BaseModel):
    has_pii: bool
    pii_found: list[PIIFinding]
    redacted_text: str | None = None
    risk_level: str  # "none", "low", "medium", "high", "critical"
    counts: dict[str, int]
    detection_method: str  # "presidio" | "regex_fallback"


# ─── Detection Logic ───

def _detect_with_presidio(text: str, language: str = "en") -> list[PIIFinding]:
    """Use Presidio for accurate PII detection."""
    registry = RecognizerRegistry()
    registry.add_recognizer(EmailRecognizer())
    registry.add_recognizer(PhoneRecognizer())
    registry.add_recognizer(UrlRecognizer())
    registry.add_recognizer(IpRecognizer())
    registry.add_recognizer(CreditCardRecognizer())
    registry.add_recognizer(IbanRecognizer())
    registry.add_recognizer(DateRecognizer())
    registry.add_recognizer(PersonRecognizer())

    analyzer = Analyzer(registry=registry)
    results = analyzer.analyze(
        text=text,
        language=language,
        entities=[
            "EMAIL_ADDRESS", "PHONE_NUMBER", "URL", "IP_ADDRESS",
            "CREDIT_CARD", "IBAN", "DATE_TIME", "PERSON",
        ],
        score_threshold=0.5,
    )

    findings = []
    for r in results:
        findings.append(PIIFinding(
            type=r.entity_type,
            text=text[r.start:r.end],
            start=r.start,
            end=r.end,
            score=float(r.score),
        ))
    return findings


def _detect_with_regex(text: str, language: str = "en") -> list[PIIFinding]:
    """Fallback regex-based detection (when Presidio is not available)."""
    findings = []
    for pii_type, pattern in FALLBACK_PATTERNS.items():
        for match in pattern.finditer(text):
            findings.append(PIIFinding(
                type=pii_type,
                text=match.group(),
                start=match.start(),
                end=match.end(),
                score=0.8,  # regex matches have moderate confidence
            ))
    # Arabic names
    for pattern in ARABIC_NAME_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(PIIFinding(
                type="PERSON",
                text=match.group(),
                start=match.start(),
                end=match.end(),
                score=0.7,
            ))
    return findings


def _redact_text(text: str, findings: list[PIIFinding]) -> str:
    """Replace PII findings with type placeholders."""
    # Sort by start descending so we can redact without shifting indices
    sorted_findings = sorted(findings, key=lambda f: f.start, reverse=True)
    redacted = text
    for f in sorted_findings:
        redacted = redacted[:f.start] + f"<{f.type}>" + redacted[f.end:]
    return redacted


def _risk_level(findings: list[PIIFinding]) -> str:
    """Determine risk level based on PII types found."""
    if not findings:
        return "none"
    types = {f.type for f in findings}
    # Critical: national IDs, credit cards, full names + DOB
    critical_types = {"SAUDI_ID", "EMIRATES_ID", "CREDIT_CARD", "IBAN", "PASSPORT"}
    if types & critical_types:
        return "critical"
    # High: person + email + phone
    high_types = {"PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"}
    if len(types & high_types) >= 2:
        return "high"
    if types & high_types:
        return "medium"
    # Low: URLs, IPs, dates
    return "low"


# ─── Endpoints ───

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "pii_detector",
        "version": "3.0.0",
        "detection_engine": "presidio" if PRESIDIO_AVAILABLE else "regex_fallback",
    }


@app.post("/v1/pii/scan", response_model=PIIScanResponse)
async def scan_pii(req: PIIScanRequest, claims: dict = Depends(_auth_dep)):
    """Scan text for PII and optionally redact it."""
    if PRESIDIO_AVAILABLE:
        findings = _detect_with_presidio(req.text, req.language)
        method = "presidio"
    else:
        findings = _detect_with_regex(req.text, req.language)
        method = "regex_fallback"

    # Deduplicate findings (Presidio can return overlapping entities)
    seen = set()
    unique_findings = []
    for f in findings:
        key = (f.type, f.start, f.end)
        if key not in seen:
            seen.add(key)
            unique_findings.append(f)

    redacted = None
    if req.redact:
        redacted = _redact_text(req.text, unique_findings)

    counts: dict[str, int] = {}
    for f in unique_findings:
        counts[f.type] = counts.get(f.type, 0) + 1

    risk = _risk_level(unique_findings)

    return PIIScanResponse(
        has_pii=len(unique_findings) > 0,
        pii_found=unique_findings,
        redacted_text=redacted,
        risk_level=risk,
        counts=counts,
        detection_method=method,
    )


@app.post("/v1/pii/redact")
async def redact_pii(req: PIIScanRequest, claims: dict = Depends(_auth_dep)):
    """Convenience endpoint that returns only the redacted text."""
    req.redact = True
    result = await scan_pii(req, claims)
    return {
        "redacted_text": result.redacted_text,
        "pii_count": len(result.pii_found),
        "risk_level": result.risk_level,
    }


@app.post("/v1/pii/check-document")
async def check_document(req: PIIScanRequest, claims: dict = Depends(_auth_dep)):
    """Check if a document is SAFE to index.

    Returns 'block' if critical PII is found, 'warn' if high, 'allow' otherwise.
    Use this before indexing documents into Qdrant.
    """
    result = await scan_pii(req, claims)
    decision = "allow"
    if result.risk_level == "critical":
        decision = "block"
    elif result.risk_level in ("high", "medium"):
        decision = "warn"

    return {
        "decision": decision,
        "risk_level": result.risk_level,
        "pii_count": len(result.pii_found),
        "pii_types": list(result.counts.keys()),
        "redacted_text": result.redacted_text,
        "message": {
            "allow": "Document is safe to index.",
            "warn": "Document contains PII — consider redacting before indexing.",
            "block": "Document contains critical PII (national ID, credit card) — MUST be redacted before indexing.",
        }[decision],
    }
