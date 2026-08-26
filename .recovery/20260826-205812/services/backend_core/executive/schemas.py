from pydantic import BaseModel
from typing import Literal

class ExecutiveAlertCreate(BaseModel):
    severity: Literal["info", "warning", "critical"] = "info"
    category: str = "platform"
    title: str
    description: str = ""
    owner: str = "AI Operations"
