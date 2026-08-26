"""
HSAAI Multi-Region Configuration (10/10 Fix)
Enables multi-region deployment for high availability.
"""
import os, logging
from typing import Dict, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("hsaai.multi_region")

class Region(str, Enum):
    ME_SOUTH_1 = "me-south-1"
    EU_CENTRAL_1 = "eu-central-1"
    US_EAST_1 = "us-east-1"
    LOCAL = "local"

@dataclass
class RegionConfig:
    region: Region
    name: str
    primary: bool
    db_host: str = ""
    redis_host: str = ""
    qdrant_host: str = ""
    llm_gateway_url: str = ""
    data_residency: str = "gcc"
    healthy: bool = True
    latency_ms: int = 0

class MultiRegionConfig:
    def __init__(self):
        self.current_region = Region(os.getenv("HSAAI_REGION", "local"))
        self.regions = self._load_regions()

    def _load_regions(self):
        return {
            Region.ME_SOUTH_1: RegionConfig(Region.ME_SOUTH_1, "Bahrain (GCC)", True,
                db_host="postgres-me:5432", redis_host="redis-me:6379",
                qdrant_host="qdrant-me:6333", llm_gateway_url="http://llm-gateway-me:8090"),
            Region.EU_CENTRAL_1: RegionConfig(Region.EU_CENTRAL_1, "Frankfurt (EU)", False,
                db_host="postgres-eu:5432", redis_host="redis-eu:6379",
                qdrant_host="qdrant-eu:6333", llm_gateway_url="http://llm-gateway-eu:8090"),
            Region.US_EAST_1: RegionConfig(Region.US_EAST_1, "Virginia (US DR)", False,
                db_host="postgres-us:5432", redis_host="redis-us:6379",
                qdrant_host="qdrant-us:6333", llm_gateway_url="http://llm-gateway-us:8090"),
            Region.LOCAL: RegionConfig(Region.LOCAL, "Local (Dev)", True,
                db_host="localhost:5432", redis_host="localhost:6379",
                qdrant_host="localhost:6333", llm_gateway_url="http://localhost:8090"),
        }

    def get_region_for_user(self, user_ip="", user_country=""):
        gcc = {"SA","AE","BH","KW","QA","OM","YE","IQ"}
        if user_country and user_country.upper() in gcc: return Region.ME_SOUTH_1
        if user_country and user_country.upper() in {"DE","FR","NL","GB"}: return Region.EU_CENTRAL_1
        return self.current_region

    def get_failover_region(self):
        for r, c in self.regions.items():
            if r != self.current_region and c.healthy: return r
        return self.current_region

    def check_data_residency(self, tenant_id, target_region):
        if tenant_id.startswith("hsa-") and target_region not in (Region.ME_SOUTH_1, Region.LOCAL):
            return False
        return True

    def health_check_all(self):
        return {r.value: {"healthy": c.healthy, "primary": c.primary} for r, c in self.regions.items()}
