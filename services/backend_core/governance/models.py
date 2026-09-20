from pydantic import BaseModel
from typing import List, Dict

class GovernanceKPI(BaseModel):
    name: str
    target: str
    owner: str
    status: str

class UseCase(BaseModel):
    code: str
    name: str
    owner: str
    risk_level: str
    pilot_ready: bool
