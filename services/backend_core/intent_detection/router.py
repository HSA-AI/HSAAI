from fastapi import APIRouter
from pydantic import BaseModel
from backend_core.intent_detection.service import detect_intent

router = APIRouter(prefix="/v1/intent", tags=["Arabic Intent Detection"])

class IntentRequest(BaseModel):
    message: str

@router.post("/detect")
def detect(payload: IntentRequest):
    result = detect_intent(payload.message)
    return {
        "intent": result.intent,
        "score": result.score,
        "matched_terms": result.matched_terms,
        "language": result.language,
    }
