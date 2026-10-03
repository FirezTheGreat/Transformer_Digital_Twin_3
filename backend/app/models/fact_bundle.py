"""Immutable FactBundle Aggregator Contract."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.models.twin_state import TwinState
from app.models.capability import CapabilityManifest
from app.models.health import OTHIBundle
from app.models.anomaly import AnomalyEpisode
from app.models.maintenance import MaintenanceRecommendation


class FactBundle(BaseModel):
    """Unified immutable payload guaranteeing agreement across Dashboard, 3D, and Reports."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_bundle_id: str = Field(..., description="Unique deterministic FactBundle UUID")
    asset_id: str = Field(..., description="Transformer asset identifier")
    timestamp_utc: datetime = Field(..., description="Timestamp of the snapshot in UTC")
    twin_state: TwinState = Field(..., description="Complete snapshot of the stateful digital twin")
    capabilities: CapabilityManifest = Field(..., description="Active capability tiers and prerequisite status")
    health: OTHIBundle = Field(..., description="Domain health breakdown, evidence grades, and gated OTHI")
    open_episodes: list[AnomalyEpisode] = Field(default_factory=list, description="All currently active/open anomaly episodes")
    active_recommendations: list[MaintenanceRecommendation] = Field(default_factory=list, description="Active prioritized maintenance actions")
    provenance_hash: str = Field(..., description="SHA-256 state and data provenance hash")
    bundle_version: str = Field(default="1.0.0", description="FactBundle schema version")
