"""
HSAAI Voice AI Service (v1.0)
==============================
Speech-to-text (ASR) using OpenAI Whisper + Text-to-speech (TTS) using Piper.
Supports Arabic and English.
"""
import os
import io
import logging
import tempfile
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="HSAAI Voice AI",
    version="1.0.0",
    description="Speech-to-text (Whisper) + Text-to-speech (Piper) for HSAAI",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get(
        "CORS_ALLOW_ORIGINS",
        "https://hsaai.internal,https://*.hsaai.internal"
    ).split(",") if o.strip() and o.strip() != "*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
    allow_credentials=True,
)

START_TIME = datetime.now()
WHISPER_MODEL_NAME = os.environ.get("WHISPER_MODEL", "base")
PIPER_VOICE = os.environ.get("PIPER_VOICE", "ar_JO-kareem-medium")

# Lazy-load Whisper (heavy import)
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            _whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
            logger.info(f"Whisper model '{WHISPER_MODEL_NAME}' loaded")
        except ImportError:
            logger.warning("Whisper not installed — ASR will return error")
            _whisper_model = False  # mark as unavailable
    return _whisper_model


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "voice_ai",
        "version": "1.0.0",
        "uptime_seconds": int((datetime.now() - START_TIME).total_seconds()),
        "whisper_model": WHISPER_MODEL_NAME,
        "piper_voice": PIPER_VOICE,
        "whisper_available": get_whisper_model() is not False,
    }


@app.get("/")
async def root():
    return {
        "service": "HSAAI Voice AI",
        "version": "1.0.0",
        "endpoints": ["/health", "/v1/asr", "/v1/tts", "/docs"],
    }


@app.post("/v1/asr")
async def speech_to_text(
    audio: UploadFile = File(...),
    language: Optional[str] = None,
):
    """Transcribe audio file to text using Whisper."""
    model = get_whisper_model()
    if model is False:
        raise HTTPException(status_code=503, detail="Whisper not available")

    # Save uploaded audio to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = model.transcribe(tmp_path, language=language)
        return {
            "text": result["text"],
            "language": result.get("language", language or "unknown"),
            "segments": len(result.get("segments", [])),
        }
    finally:
        os.unlink(tmp_path)


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    speed: float = 1.0


@app.post("/v1/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech audio using Piper."""
    try:
        from piper import PiperVoice
        import wave

        voice_name = request.voice or PIPER_VOICE
        # Try to load voice model
        voice = PiperVoice.load(voice_name)

        # Generate audio
        audio_buffer = io.BytesIO()
        with wave.open(audio_buffer, "wb") as wav_file:
            voice.synthesize_wav(request.text, wav_file, length_scale=1.0 / request.speed)

        audio_buffer.seek(0)
        return StreamingResponse(
            audio_buffer,
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=tts.wav"}
        )
    except ImportError:
        raise HTTPException(status_code=503, detail="Piper TTS not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8096, log_level="info")
