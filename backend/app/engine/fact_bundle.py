"""Immutable FactBundle Aggregator and Assembler (Phase 7.1).

Assembles unified, immutable FactBundle instances ensuring cross-view data consistency
between Dashboard, 3D visualization, API clients, and deterministic audit reports.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.engine.capability import CapabilityEvaluator
from app.models.capability import CapabilityManifest, CapabilityTier
from app.models.fact_bundle import FactBundle
from app.models.health import (
    DomainFreshness,
    DomainHealth,
    EvidenceGrade,
    HealthStatus,
    OTHIBundle,
)
from app.models.twin_state import TwinState


def _compute_sha256(content: str) -> str:
    """Compute SHA-256 hex digest for given text."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_fact_bundle_hash(
    state_hash: str,
    manifest: CapabilityManifest,
    health: OTHIBundle,
    open_episode_ids: list[str],
    recommendation_ids: list[str],
    bundle_version: str = "1.0.0",
) -> str:
    """Compute deterministic SHA-256 provenance hash for FactBundle."""
    payload = {
        "state_hash": state_hash,
        "highest_tier": manifest.highest_tier.value,
        "othi_score": health.othi_score,
        "is_gated": health.is_gated,
        "evidence_grade": health.evidence_grade.value,
        "open_episode_ids": sorted(open_episode_ids),
        "recommendation_ids": sorted(recommendation_ids),
        "bundle_version": bundle_version,
    }
    serialized = json.dumps(payload, sort_keys=True)
    return _compute_sha256(serialized)


def build_default_health_bundle(
    asset_id: str,
    timestamp_utc: datetime,
) -> OTHIBundle:
    """Construct baseline default OTHIBundle when state does not have an active assessment."""
    domains: dict[str, DomainHealth] = {
        "thermal": DomainHealth(
            domain_name="thermal",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Baseline normal (uninitialized)",
            freshness=DomainFreshness.CURRENT,
        ),
        "loading": DomainHealth(
            domain_name="loading",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Baseline normal (uninitialized)",
            freshness=DomainFreshness.CURRENT,
        ),
        "phase_neutral": DomainHealth(
            domain_name="phase_neutral",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Baseline normal (uninitialized)",
            freshness=DomainFreshness.CURRENT,
        ),
        "voltage_pf_freq": DomainHealth(
            domain_name="voltage_pf_freq",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Baseline normal (uninitialized)",
            freshness=DomainFreshness.CURRENT,
        ),
        "oil_protection": DomainHealth(
            domain_name="oil_protection",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Baseline normal (uninitialized)",
            freshness=DomainFreshness.CURRENT,
        ),
    }

    return OTHIBundle(
        asset_id=asset_id,
        timestamp_utc=timestamp_utc,
        othi_score=100,
        raw_othi=100,
        status=HealthStatus.NORMAL,
        raw_status=HealthStatus.NORMAL,
        operational_status=HealthStatus.NORMAL,
        evidence_grade=EvidenceGrade.U,
        driving_domain=None,
        driving_condition_family=None,
        base_penalty=0.0,
        secondary_penalty=0.0,
        total_penalty=0.0,
        is_gated=False,
        gate_reason=None,
        available_domains=["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"],
        current_domains=["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"],
        stale_domains=[],
        domains=domains,
    )


class FactBundleAssembler:
    """Assembler class for constructing immutable, verifiable FactBundles."""

    def __init__(
        self,
        capability_evaluator: CapabilityEvaluator | None = None,
        bundle_version: str = "1.0.0",
    ) -> None:
        """Initialize FactBundleAssembler."""
        self.capability_evaluator = capability_evaluator or CapabilityEvaluator()
        self.bundle_version = bundle_version

    def assemble(
        self,
        state: TwinState,
        capabilities: CapabilityManifest | None = None,
        bundle_id: str | None = None,
    ) -> FactBundle:
        """Assemble complete immutable FactBundle from TwinState."""
        eval_time = state.state_time_utc
        manifest = capabilities or self.capability_evaluator.evaluate(state, evaluated_at_utc=eval_time)
        health = state.health_bundle or build_default_health_bundle(state.asset_id, eval_time)

        open_episode_ids = [ep.episode_id for ep in state.open_episodes]
        recommendation_ids = [rec.recommendation_id for rec in state.active_recommendations]

        prov_hash = compute_fact_bundle_hash(
            state_hash=state.state_hash,
            manifest=manifest,
            health=health,
            open_episode_ids=open_episode_ids,
            recommendation_ids=recommendation_ids,
            bundle_version=self.bundle_version,
        )

        fb_id = bundle_id or f"fb-{state.asset_id}-{state.state_sequence:06d}"

        return FactBundle(
            fact_bundle_id=fb_id,
            asset_id=state.asset_id,
            timestamp_utc=eval_time,
            twin_state=state,
            capabilities=manifest,
            health=health,
            open_episodes=list(state.open_episodes),
            active_recommendations=list(state.active_recommendations),
            provenance_hash=prov_hash,
            bundle_version=self.bundle_version,
        )


def assemble_fact_bundle(
    state: TwinState,
    capability_evaluator: CapabilityEvaluator | None = None,
    capabilities: CapabilityManifest | None = None,
    bundle_version: str = "1.0.0",
    bundle_id: str | None = None,
) -> FactBundle:
    """Functional convenience wrapper for FactBundleAssembler.assemble."""
    assembler = FactBundleAssembler(
        capability_evaluator=capability_evaluator,
        bundle_version=bundle_version,
    )
    return assembler.assemble(state=state, capabilities=capabilities, bundle_id=bundle_id)
