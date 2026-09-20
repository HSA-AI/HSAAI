"""HSAAI Wisdom Marketplace — v0.3.0
Trade Wisdom Crystals between organizations. The Intelligence Economy."""
import os, sys, logging, time, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from common.wisdom import wisdom_engine, WisdomCrystal
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")

logger = logging.getLogger("wisdom_marketplace")
app = FastAPI(title="HSAAI Wisdom Marketplace", version="0.3.0")

class WisdomListing(BaseModel):
    statement: str
    confidence: float = 0.7
    domain: str = "general"
    evidence_base: str = ""
    applicable_when: str = ""
    price_usd: float = 0.0  # 0 = free, >0 = paid
    seller_org: str = ""

class WisdomPurchase(BaseModel):
    wisdom_id: str
    buyer_org: str = ""

_listings: dict[str, dict] = {}
_transactions: list[dict] = []

@app.get("/health")
def health(): return {"status": "ok", "service": "wisdom_marketplace",
                      "listings": len(_listings), "transactions": len(_transactions)}

@app.post("/v1/list")
async def list_wisdom(l: WisdomListing, claims: dict = Depends(_auth_dep)):
    wid = f"wisdom-listing-{uuid.uuid4().hex[:8]}"
    listing = {**l.__dict__, "wisdom_id": wid, "listed_at": time.time(), "status": "available"}
    _listings[wid] = listing
    logger.info("Wisdom listed: %s by %s ($%.2f)", wid, l.seller_org, l.price_usd)
    return {"wisdom_id": wid, "status": "listed"}

@app.get("/v1/browse")
def browse(domain: str = None, limit: int = 50, claims: dict = Depends(_auth_dep)):
    listings = list(_listings.values())
    if domain: listings = [l for l in listings if l.get("domain") == domain]
    return {"listings": listings[:limit], "total": len(listings)}

@app.post("/v1/purchase")
async def purchase(p: WisdomPurchase, claims: dict = Depends(_auth_dep)):
    listing = _listings.get(p.wisdom_id)
    if not listing: raise HTTPException(404, "Wisdom listing not found")
    if listing.get("status") != "available": raise HTTPException(409, "Already sold")
    listing["status"] = "sold"
    listing["buyer_org"] = p.buyer_org
    listing["sold_at"] = time.time()
    _transactions.append({"wisdom_id": p.wisdom_id, "seller": listing["seller_org"],
                          "buyer": p.buyer_org, "price": listing["price_usd"], "at": time.time()})
    logger.info("Wisdom purchased: %s by %s from %s ($%.2f)", p.wisdom_id, p.buyer_org, listing["seller_org"], listing["price_usd"])
    return {"status": "purchased", "wisdom": listing}

@app.get("/v1/transactions")
def transactions(limit: int = 50, claims: dict = Depends(_auth_dep)):
    return {"transactions": _transactions[-limit:], "total": len(_transactions)}
