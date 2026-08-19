"""
HSAAI PII Detector — Standalone runner (v3.0)

Usage:
    cd services/pii_detector
    pip install -r requirements.txt
    python -m spacy download en_core_web_sm
    uvicorn main:app --host 0.0.0.0 --port 8092 --reload
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8092,
        reload=True,
        log_level="info",
    )
