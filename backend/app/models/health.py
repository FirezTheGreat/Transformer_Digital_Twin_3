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


class DomainHealth(BaseModel):
    """Health assessment for one of the 5 canonical health domains."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    domain_name: Literal["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"] = Field(
        ..., description="Exact canonical domain name"
    )
    severity: float = Field(..., ge=0.0, le=1.0, description="Domain penalty severity in [0.0, 1.0]")
    status: HealthStatus = Field(..., description="Operational status band")
    driving_evidence_id: str | None = Field(default=None, description="Evidence ID setting the domain severity")
    evidence_count: int = Field(default=0, ge=0, description="Count of active evidence items contributing to this domain")
    details: str = Field(..., description="Human-readable explanation of domain condition")


class OTHIBundle(BaseModel):
    """Gated composite Operational Transformer Health Index bundle."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(..., description="Transformer asset identifier")
    timestamp_utc: datetime = Field(..., description="Calculation timestamp in UTC")
    othi_score: int | None = Field(
        default=None, ge=0, le=100, description="Composite score in [0, 100], or null if gated off"
    )
    status: HealthStatus | None = Field(default=None, description="Overall status band if OTHI is computed")
    evidence_grade: EvidenceGrade = Field(..., description="Independent data quality and sensor coverage grade (A, B, C, U)")
    driving_domain: str | None = Field(default=None, description="Domain that set the base penalty")
    base_penalty: float = Field(..., ge=0.0, le=1.0, description="Base penalty max(s_d)")
    secondary_penalty: float = Field(..., ge=0.0, le=1.0, description="Secondary penalty 0.2 * sum(other s_d)")
    total_penalty: float = Field(..., ge=0.0, le=1.0, description="Total penalty min(1.0, base + secondary)")
    is_gated: bool = Field(..., description="True if numeric OTHI is withheld due to insufficient multi-domain evidence")
    gate_reason: str | None = Field(default=None, description="Deterministic reason for withholding numeric score")
    available_domains: list[str] = Field(..., min_length=1, description="List of currently available independent domains")
    domains: dict[str, DomainHealth] = Field(..., description="Detailed breakdown across all 5 canonical domains")
