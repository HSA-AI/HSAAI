"""
HSAAI Enterprise Model Training Service (v2.0)
- Env-driven CORS allowlist (was allow_origins=['*'])
- Modern lifespan context manager (was deprecated @app.on_event)
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.model_training.db.database import Base, engine
from services.model_training.api.training_routes import router as training_router
from services.model_training.api.dataset_routes import router as dataset_router
from services.model_training.api.model_routes import router as model_router
from services.model_training.api.monitoring_routes import router as monitoring_router

logger = logging.getLogger("model_training")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _resolve_cors_origins() -> list[str]:
    raw = os.getenv("MODEL_TRAINING_CORS_ORIGINS", "").strip()
    if not raw:
        return ["http://localhost:3000"]
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Model Training service starting up...")
    if os.getenv("MODEL_TRAINING_USE_ALEMBIC", "false").lower() == "true":
        logger.info("MODEL_TRAINING_USE_ALEMBIC=true — skipping create_all; Alembic expected to run separately.")
    else:
        logger.warning(
            "Running Base.metadata.create_all() on startup. For production, set MODEL_TRAINING_USE_ALEMBIC=true "
            "and run `alembic upgrade head` before starting the service."
        )
        Base.metadata.create_all(bind=engine)
    yield
    logger.info("Model Training service shutting down.")


app = FastAPI(
    title="HSAAI Enterprise Model Training Service",
    version="4.0.0",
    description="Enterprise-grade LoRA / QLoRA / SFT training service with Redis + RQ job queue.",
    lifespan=lifespan,
)

_cors_origins = _resolve_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Request-Id"],
)
logger.info(f"CORS allow_origins = {_cors_origins}")


@app.get("/health")
def health():
    return {"status": "ok", "service": "model_training", "mode": "real-training", "version": "2.0.0"}


@app.get("/ready")
def ready():
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}


app.include_router(training_router)
app.include_router(dataset_router)
app.include_router(model_router)
app.include_router(monitoring_router)
