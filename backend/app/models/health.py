"""Domain Health and Operational Transformer Health Index (OTHI) Contracts."""

from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class EvidenceGrade(str, Enum):
    """Deterministic evidence quality grade."""
    A = "A"
    B = "B"
    C = "C"
    U = "U"


class HealthStatus(str, Enum):
    """Health classification bands."""
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class DomainFreshness(str, Enum):
    """Telemetry freshness state for an individual health domain."""
    CURRENT = "CURRENT"
    WARNING_STALE = "WARNING_STALE"
    HARD_STALE = "HARD_STALE"
    UNAVAILABLE = "UNAVAILABLE"


class DomainHealth(BaseModel):
    """Health assessment for one of the 5 canonical health domains."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    domain_name: Literal["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"] = Field(
        ..., description="Exact canonical domain name"
    )
    severity: float = Field(..., ge=0.0, le=1.0, description="Domain penalty severity in [0.0, 1.0]")
    status: HealthStatus = Field(..., description="Operational status band")
    driving_evidence_id: str | None = Field(default=None, description="Evidence ID setting the domain severity")
    driving_condition_family: str | None = Field(default=None, description="Condition family setting the domain severity")
    evidence_count: int = Field(default=0, ge=0, description="Count of active evidence items contributing to this domain")
    details: str = Field(..., description="Human-readable explanation of domain condition")
    freshness: DomainFreshness = Field(default=DomainFreshness.CURRENT, description="Domain freshness status")
    last_valid_time_utc: datetime | None = Field(default=None, description="Timestamp of most recent valid observation")
    is_stale: bool = Field(default=False, description="True if domain telemetry is currently stale")
    contributing_families: list[str] = Field(default_factory=list, description="All contributing condition families")


class OTHIBundle(BaseModel):
    """Gated composite Operational Transformer Health Index bundle."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(..., description="Transformer asset identifier")
    timestamp_utc: datetime = Field(..., description="Calculation timestamp in UTC")
    othi_score: int | None = Field(
        default=None, ge=0, le=100, description="Composite score in [0, 100], or null if gated off"
    )
    raw_othi: int | None = Field(
        default=None, ge=0, le=100, description="Raw instantaneous calculated OTHI score"
    )
    status: HealthStatus | None = Field(default=None, description="Overall status band if OTHI is computed")
    raw_status: HealthStatus | None = Field(default=None, description="Raw instantaneous health status band")
    operational_status: HealthStatus | None = Field(default=None, description="Persisted operational status band reflecting active episodes")
    evidence_grade: EvidenceGrade = Field(..., description="Independent data quality and sensor coverage grade (A, B, C, U)")
    driving_domain: str | None = Field(default=None, description="Domain that set the base penalty")
    driving_condition_family: str | None = Field(default=None, description="Condition family setting the base penalty")
    base_penalty: float = Field(..., ge=0.0, le=1.0, description="Base penalty max(s_d)")
    secondary_penalty: float = Field(..., ge=0.0, le=1.0, description="Secondary penalty 0.20 * sum(other s_d)")
    total_penalty: float = Field(..., ge=0.0, le=1.0, description="Total penalty min(1.0, base + secondary)")
    is_gated: bool = Field(..., description="True if numeric OTHI is withheld due to insufficient multi-domain evidence or anti-uplift")
    gate_reason: str | None = Field(default=None, description="Deterministic reason for withholding numeric score")
    available_domains: list[str] = Field(..., min_length=1, description="List of currently available independent domains")
    current_domains: list[str] = Field(default_factory=list, description="List of currently fresh valid domains")
    stale_domains: list[str] = Field(default_factory=list, description="List of currently stale domains")
    domains: dict[str, DomainHealth] = Field(..., description="Detailed breakdown across all 5 canonical domains")
    last_valid_othi: int | None = Field(default=None, ge=0, le=100, description="Last valid numeric OTHI before staleness")
    last_valid_status: HealthStatus | None = Field(default=None, description="Status band of last valid OTHI")
    last_valid_timestamp_utc: datetime | None = Field(default=None, description="Timestamp of last valid OTHI calculation")
    algorithm_version: str = Field(default="MAX_PLUS_SECONDARY_V1", description="Locked OTHI aggregation algorithm version")
    secondary_coefficient: float = Field(default=0.20, description="Locked secondary domain penalty coefficient")
