"""HSAAI Knowledge Genome Service — v0.6.0"""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
from pydantic import BaseModel
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")
from common.knowledge_genome import genome_engine
engine = genome_engine
logger = logging.getLogger("knowledge_genome_engine")
app = FastAPI(title="HSAAI Knowledge Genome", version="0.6.0")

@app.get("/health")
def health():
    stats = engine.stats() if hasattr(engine, 'stats') else {}
    return {"status": "ok", "service": "knowledge_genome_engine", **stats}
class GeneInput(BaseModel):
    name: str
    chromosome: str
    sequence: str
    expressed_as: list[str] = []

class MutationInput(BaseModel):
    gene_id: str
    new_sequence: str
    mutation_type: str = "refinement"

@app.post("/v1/discover")
def discover_gene(req: GeneInput, claims: dict = Depends(_auth_dep)):
    gene = genome_engine.discover_gene(req.name, req.chromosome, req.sequence, req.expressed_as)
    return gene.__dict__

@app.post("/v1/mutate")
def mutate_gene(req: MutationInput, claims: dict = Depends(_auth_dep)):
    mutation = genome_engine.mutate(req.gene_id, req.new_sequence, req.mutation_type)
    return mutation.__dict__

@app.get("/v1/genome")
def get_genome(chromosome: str = None, claims: dict = Depends(_auth_dep)):
    return genome_engine.get_genome(chromosome)

@app.get("/v1/fittest")
def fittest(limit: int = 10, claims: dict = Depends(_auth_dep)):
    return {"genes": genome_engine.fittest_genes(limit)}
