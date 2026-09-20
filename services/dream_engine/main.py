"""HSAAI Dream Engine Service — v0.4.0
The cognitive organism dreams during quiet periods."""
import os, sys, logging, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends, BackgroundTasks
from pydantic import BaseModel
from common.dream_engine import dream_engine
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")

logger = logging.getLogger("dream_engine_service")
app = FastAPI(title="HSAAI Dream Engine", version="0.4.0")

class MemoryFeed(BaseModel):
    memory: dict

@app.get("/health")
def health(): return {"status": "ok", "service": "dream_engine", **dream_engine.stats()}

@app.post("/v1/feed")
def feed_memory(feed: MemoryFeed, claims: dict = Depends(_auth_dep)):
    dream_engine.feed_memory(feed.memory)
    return {"fed": True, "buffered": dream_engine.stats()["memories_buffered"]}

@app.post("/v1/dream")
async def dream(bg: BackgroundTasks, claims: dict = Depends(_auth_dep)):
    cycle = await dream_engine.dream()
    return {"cycle": cycle.__dict__}

@app.get("/v1/insights")
def get_insights(actionable_only: bool = False, limit: int = 50, claims: dict = Depends(_auth_dep)):
    return {"insights": dream_engine.get_insights(actionable_only, limit)}

@app.get("/v1/stats")
def stats(claims: dict = Depends(_auth_dep)):
    return dream_engine.stats()
