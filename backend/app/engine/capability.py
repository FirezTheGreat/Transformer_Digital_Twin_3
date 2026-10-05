"""Dynamic Capability Tier Evaluator.

Evaluates operational capability tiers (C0-C4) and analytical sub-capabilities
dynamically based on TwinState observation quality, signal availability,
asset profile verification, and model promotion status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

from app.models.capability import CapabilityItem, CapabilityManifest, CapabilityTier
from app.models.profile import AssetProfile, InsulationClass, ProfileVerificationStatus
from app.models.scenario import ThermalTrustState
from app.models.telemetry import Measurement, QualitySeverity
from app.models.thermal_artifact import QualificationStatus, ThermalModelQualification
from app.models.twin_state import TwinState


# Normalized temperature signal names (continuous top-oil)
TOP_OIL_SIGNAL_IDS = {
    "top_oil_temperature",
    "oil_temperature",
    "top_oil_temp",
    "oti",
}

# Ambient temperature signal names
AMBIENT_SIGNAL_IDS = {
    "ambient_temperature",
    "ambient_temp",
    "ati",
}

# Discrete WTI alarm/trip contacts - strictly rejected as continuous temperature
DISCRETE_WTI_SIGNAL_IDS = {
    "winding_temp_alarm_contact",
    "winding_temperature",
    "wti",
    "wti_alarm",
    "wti_trip",
}

# Electrical Power signals
ACTIVE_POWER_SIGNAL_IDS = {
    "active_power",
    "active_power_total",
    "active_power_kw",
    "p_total",
    "active_power_l1",
    "active_power_l2",
    "active_power_l3",
    "active_power_a",
    "active_power_b",
    "active_power_c",
}

REACTIVE_POWER_SIGNAL_IDS = {
    "reactive_power",
    "reactive_power_total",
    "reactive_power_kvar",
    "q_total",
    "reactive_power_l1",
    "reactive_power_l2",
    "reactive_power_l3",
    "reactive_power_a",
    "reactive_power_b",
    "reactive_power_c",
}

APPARENT_POWER_SIGNAL_IDS = {
    "apparent_power",
    "apparent_power_total",
    "apparent_power_kva",
    "s_total",
    "apparent_power_l1",
    "apparent_power_l2",
    "apparent_power_l3",
    "apparent_power_a",
    "apparent_power_b",
    "apparent_power_c",
}

PHASE_CURRENT_KEYS_L1 = {"current_l1", "current_a", "current_phase_a", "i_l1", "current_i1"}
PHASE_CURRENT_KEYS_L2 = {"current_l2", "current_b", "current_phase_b", "i_l2", "current_i2"}
PHASE_CURRENT_KEYS_L3 = {"current_l3", "current_c", "current_phase_c", "i_l3", "current_i3"}

PHASE_VOLTAGE_KEYS_L1 = {"voltage_l1", "voltage_a", "voltage_phase_a", "v_l1", "voltage_v1"}
PHASE_VOLTAGE_KEYS_L2 = {"voltage_l2", "voltage_b", "voltage_phase_b", "v_l2", "voltage_v2"}
PHASE_VOLTAGE_KEYS_L3 = {"voltage_l3", "voltage_c", "voltage_phase_c", "v_l3", "voltage_v3"}

NEUTRAL_CURRENT_KEYS = {"neutral_current", "current_n", "current_neutral", "i_n", "inut"}
POWER_FACTOR_KEYS = {"power_factor", "pf", "power_factor_total"}


def _is_measurement_valid(m: Measurement | None) -> bool:
    """Check if measurement exists, is non-null, and not marked with BAD quality."""
    if m is None:
        return False
    if m.value is None:
        return False
    if m.quality.severity == QualitySeverity.BAD:
        return False
    return True


def _find_measurement(
    observations: Mapping[str, Measurement],
    candidate_keys: set[str],
) -> Measurement | None:
    """Find first matching valid measurement matching candidate keys (case-insensitive)."""
    for obs_key, m in observations.items():
        clean_key = obs_key.lower().strip()
        clean_signal_id = m.signal_id.lower().strip() if m.signal_id else ""
        if (clean_key in candidate_keys or clean_signal_id in candidate_keys) and _is_measurement_valid(m):
            return m
    return None


def _has_any_bad_measurement(
    observations: Mapping[str, Measurement],
    candidate_keys: set[str],
) -> bool:
    """Check if any matching measurement has BAD quality severity."""
    for obs_key, m in observations.items():
        clean_key = obs_key.lower().strip()
        clean_signal_id = m.signal_id.lower().strip() if m.signal_id else ""
        if (clean_key in candidate_keys or clean_signal_id in candidate_keys) and m.quality.severity == QualitySeverity.BAD:
            return True
    return False


class CapabilityEvaluator:
    """Evaluates dynamic capability tiers and analytical manifest for TwinState."""

    def __init__(
        self,
        profile: AssetProfile | None = None,
        model_version: str = "uncalibrated",
        is_model_promoted: bool = False,
        qualification: ThermalModelQualification | None = None,
        hotspot_supported: bool = False,
        expected_cadence_s: int = 900,
        evaluation_window_s: int = 86400,
    ) -> None:
        """Initialize CapabilityEvaluator.

        Args:
            profile: Optional AssetProfile for nameplate verification.
            model_version: Thermal model version string.
            is_model_promoted: Whether the thermal model has passed promotion tests.
            qualification: Optional capability-specific qualification breakdown.
            hotspot_supported: Whether credible hot-spot estimation is supported.
            expected_cadence_s: Configured telemetry interval in seconds.
            evaluation_window_s: Rolling evaluation window duration in seconds.
        """
        self.profile = profile
        self.model_version = model_version
        self.is_model_promoted = is_model_promoted
        self.qualification = qualification
        self.hotspot_supported = hotspot_supported
        self.expected_cadence_s = expected_cadence_s
        self.evaluation_window_s = evaluation_window_s

    def evaluate(
        self,
        state: TwinState,
        evaluated_at_utc: datetime | None = None,
    ) -> CapabilityManifest:
        """Evaluate active capability tiers and build dynamic CapabilityManifest.

        Args:
            state: Current TwinState snapshot.
            evaluated_at_utc: Optional evaluation timestamp (defaults to state.state_time_utc).

        Returns:
            CapabilityManifest: Complete explainable capability manifest.
        """
        eval_time = evaluated_at_utc or state.state_time_utc
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        obs = state.current_observations

        # 1. Available and valid signal IDs
        available_signals = sorted(
            {
                m.signal_id
                for m in obs.values()
                if _is_measurement_valid(m)
            }
        )

        # 2. Verified profile metadata fields
        verified_metadata_ids = []
        if self.profile is not None:
            if self.profile.profile_status == ProfileVerificationStatus.VERIFIED:
                verified_metadata_ids.append("asset_profile")
            for field_name, p_field in self.profile.fields.items():
                if p_field.status == ProfileVerificationStatus.VERIFIED:
                    verified_metadata_ids.append(field_name)
        verified_metadata_ids = sorted(set(verified_metadata_ids))

        # 3. Calculate freshness from state_time_utc
        if len(available_signals) > 0:
            state_time = state.state_time_utc
            if state_time.tzinfo is None:
                state_time = state_time.replace(tzinfo=timezone.utc)
            freshness_s = max(0.0, (eval_time - state_time).total_seconds())
        else:
            freshness_s = 0.0

        # Helper lookups for specific telemetry inputs
        m_top_oil = _find_measurement(obs, TOP_OIL_SIGNAL_IDS)
        has_bad_top_oil = _has_any_bad_measurement(obs, TOP_OIL_SIGNAL_IDS)
        m_ambient = _find_measurement(obs, AMBIENT_SIGNAL_IDS)
        has_bad_ambient = _has_any_bad_measurement(obs, AMBIENT_SIGNAL_IDS)
        m_wti = _find_measurement(obs, DISCRETE_WTI_SIGNAL_IDS)

        m_p = _find_measurement(obs, ACTIVE_POWER_SIGNAL_IDS)
        m_q = _find_measurement(obs, REACTIVE_POWER_SIGNAL_IDS)
        m_s = _find_measurement(obs, APPARENT_POWER_SIGNAL_IDS)
        m_pf = _find_measurement(obs, POWER_FACTOR_KEYS)

        m_i1 = _find_measurement(obs, PHASE_CURRENT_KEYS_L1)
        m_i2 = _find_measurement(obs, PHASE_CURRENT_KEYS_L2)
        m_i3 = _find_measurement(obs, PHASE_CURRENT_KEYS_L3)

        m_v1 = _find_measurement(obs, PHASE_VOLTAGE_KEYS_L1)
        m_v2 = _find_measurement(obs, PHASE_VOLTAGE_KEYS_L2)
        m_v3 = _find_measurement(obs, PHASE_VOLTAGE_KEYS_L3)

        m_in = _find_measurement(obs, NEUTRAL_CURRENT_KEYS)

        # Check for presence of discrete WTI without continuous top oil
        only_discrete_wti = (m_top_oil is None) and (m_wti is not None)

        capabilities: dict[str, CapabilityItem] = {}

        # ------------------------------------------------------------------
        # Tier C0: Data Integrity & Ingestion
        # ------------------------------------------------------------------
        c0_required = ["asset_id", "timestamp", "recognized_signals"]
        c0_missing: list[str] = []
        c0_reasons: list[str] = []

        if not state.asset_id:
            c0_missing.append("asset_id")
            c0_reasons.append("MISSING_ASSET_ID")
        if len(available_signals) == 0:
            c0_missing.append("recognized_signals")
            c0_reasons.append("NO_VALID_TELEMETRY")

        c0_enabled = len(c0_reasons) == 0
        c0_grade = "A" if c0_enabled and not any(m.quality.severity == QualitySeverity.UNCERTAIN for m in obs.values()) else ("B" if c0_enabled else "U")

        capabilities["C0"] = CapabilityItem(
            enabled=c0_enabled,
            evidence_grade=c0_grade,
            required_inputs=c0_required,
            missing_inputs=c0_missing,
            disabled_reason_codes=c0_reasons,
            coverage_pct=100.0 if c0_enabled else 0.0,
            model_status="NOT_APPLICABLE",
        )

        # ------------------------------------------------------------------
        # Sub-capabilities under C1: Electrical
        # ------------------------------------------------------------------
        # Loading proxy
        has_load_driver = (m_s is not None) or (m_p is not None and m_q is not None) or (m_p is not None) or (m_i1 is not None and m_i2 is not None and m_i3 is not None) or (m_i1 is not None or m_i2 is not None or m_i3 is not None)
        loading_required = ["apparent_power_or_power_or_currents"]
        loading_missing = [] if has_load_driver else ["load_driver_inputs"]
        loading_reasons = [] if has_load_driver else ["MISSING_LOAD_INPUTS"]

        capabilities["loading_proxy"] = CapabilityItem(
            enabled=c0_enabled and has_load_driver,
            evidence_grade="A" if has_load_driver else "U",
            required_inputs=loading_required,
            missing_inputs=loading_missing,
            disabled_reason_codes=loading_reasons,
            model_status="NOT_APPLICABLE",
        )

        # Power factor
        has_pf = (m_pf is not None) or (m_p is not None and m_s is not None) or (m_p is not None and m_q is not None)
        pf_required = ["power_factor_or_p_and_s"]
        pf_missing = [] if has_pf else ["power_factor_inputs"]
        pf_reasons = [] if has_pf else ["MISSING_PF_INPUTS"]

        capabilities["power_factor"] = CapabilityItem(
            enabled=c0_enabled and has_pf,
            evidence_grade="A" if has_pf else "U",
            required_inputs=pf_required,
            missing_inputs=pf_missing,
            disabled_reason_codes=pf_reasons,
            model_status="NOT_APPLICABLE",
        )

        # Current imbalance (strictly requires all 3 phase currents)
        has_3p_current = (m_i1 is not None) and (m_i2 is not None) and (m_i3 is not None)
        curr_imb_missing: list[str] = []
        if m_i1 is None:
            curr_imb_missing.append("current_L1")
        if m_i2 is None:
            curr_imb_missing.append("current_L2")
        if m_i3 is None:
            curr_imb_missing.append("current_L3")

        curr_imb_reasons = [] if has_3p_current else ["MISSING_THREE_PHASE_CURRENT"]

        capabilities["current_imbalance"] = CapabilityItem(
            enabled=c0_enabled and has_3p_current,
            evidence_grade="A" if has_3p_current else "U",
            required_inputs=["current_L1", "current_L2", "current_L3"],
            missing_inputs=curr_imb_missing,
            disabled_reason_codes=curr_imb_reasons,
            model_status="NOT_APPLICABLE",
        )

        # Voltage imbalance (strictly requires all 3 phase voltages)
        has_3p_voltage = (m_v1 is not None) and (m_v2 is not None) and (m_v3 is not None)
        volt_imb_missing: list[str] = []
        if m_v1 is None:
            volt_imb_missing.append("voltage_L1")
        if m_v2 is None:
            volt_imb_missing.append("voltage_L2")
        if m_v3 is None:
            volt_imb_missing.append("voltage_L3")

        volt_imb_reasons = [] if has_3p_voltage else ["MISSING_THREE_PHASE_VOLTAGE"]

        capabilities["voltage_imbalance"] = CapabilityItem(
            enabled=c0_enabled and has_3p_voltage,
            evidence_grade="A" if has_3p_voltage else "U",
            required_inputs=["voltage_L1", "voltage_L2", "voltage_L3"],
            missing_inputs=volt_imb_missing,
            disabled_reason_codes=volt_imb_reasons,
            model_status="NOT_APPLICABLE",
        )

        # Neutral current ratio
        has_neutral_inputs = (m_in is not None) and (has_3p_current or m_i1 is not None or m_i2 is not None or m_i3 is not None)
        neutral_missing = [] if has_neutral_inputs else (["neutral_current"] if m_in is None else ["phase_currents"])
        neutral_reasons = [] if has_neutral_inputs else ["MISSING_NEUTRAL_OR_PHASE_CURRENT"]

        capabilities["neutral_current_ratio"] = CapabilityItem(
            enabled=c0_enabled and has_neutral_inputs,
            evidence_grade="A" if has_neutral_inputs else "U",
            required_inputs=["neutral_current", "phase_currents"],
            missing_inputs=neutral_missing,
            disabled_reason_codes=neutral_reasons,
            model_status="NOT_APPLICABLE",
        )

        # PQS consistency
        has_pqs = (m_p is not None) and (m_q is not None) and (m_s is not None)
        pqs_missing: list[str] = []
        if m_p is None:
            pqs_missing.append("active_power")
        if m_q is None:
            pqs_missing.append("reactive_power")
        if m_s is None:
            pqs_missing.append("apparent_power")
        pqs_reasons = [] if has_pqs else ["MISSING_PQS_SIGNALS"]

        capabilities["pqs_consistency"] = CapabilityItem(
            enabled=c0_enabled and has_pqs,
            evidence_grade="A" if has_pqs else "U",
            required_inputs=["active_power", "reactive_power", "apparent_power"],
            missing_inputs=pqs_missing,
            disabled_reason_codes=pqs_reasons,
            model_status="NOT_APPLICABLE",
        )

        # ------------------------------------------------------------------
        # Tier C1: Electrical Monitoring (General Tier)
        # ------------------------------------------------------------------
        c1_required = ["usable_electrical_power_or_current"]
        c1_missing: list[str] = []
        c1_reasons: list[str] = []

        if not c0_enabled:
            c1_reasons.append("C0_UNAVAILABLE")
        if not has_load_driver and not has_pf and not has_3p_current and not has_3p_voltage:
            c1_missing.append("electrical_inputs")
            c1_reasons.append("MISSING_ELECTRICAL_INPUTS")

        c1_enabled = c0_enabled and (len(c1_reasons) == 0)
        c1_grade = "A" if c1_enabled else "U"

        capabilities["C1"] = CapabilityItem(
            enabled=c1_enabled,
            evidence_grade=c1_grade,
            required_inputs=c1_required,
            missing_inputs=c1_missing,
            disabled_reason_codes=c1_reasons,
            coverage_pct=100.0 if c1_enabled else 0.0,
            model_status="NOT_APPLICABLE",
        )

        # ------------------------------------------------------------------
        # Tier C2: Thermal Descriptive Monitoring
        # ------------------------------------------------------------------
        c2_required = ["top_oil_temperature"]
        c2_missing: list[str] = []
        c2_reasons: list[str] = []

        if not c0_enabled:
            c2_reasons.append("C0_UNAVAILABLE")

        if m_top_oil is None:
            c2_missing.append("top_oil_temperature")
            if has_bad_top_oil:
                c2_reasons.append("BAD_QUALITY_TOP_OIL_TEMPERATURE")
            elif only_discrete_wti:
                c2_reasons.append("DISCRETE_WTI_NOT_SUBSTITUTE_FOR_TOP_OIL")
                c2_reasons.append("MISSING_CONTINUOUS_TOP_OIL_TEMPERATURE")
            else:
                c2_reasons.append("MISSING_CONTINUOUS_TOP_OIL_TEMPERATURE")

        c2_enabled = c0_enabled and (m_top_oil is not None) and (len(c2_reasons) == 0)
        c2_grade = "A" if (c2_enabled and m_top_oil.quality.severity == QualitySeverity.GOOD) else ("B" if c2_enabled else "U")

        capabilities["C2"] = CapabilityItem(
            enabled=c2_enabled,
            evidence_grade=c2_grade,
            required_inputs=c2_required,
            missing_inputs=c2_missing,
            disabled_reason_codes=c2_reasons,
            coverage_pct=100.0 if c2_enabled else 0.0,
            model_status="NOT_APPLICABLE",
        )
        capabilities["top_oil_monitoring"] = capabilities["C2"]

        # ------------------------------------------------------------------
        # ------------------------------------------------------------------
        # Ambient Monitoring Sub-capability
        # ------------------------------------------------------------------
        amb_missing = [] if m_ambient is not None else ["ambient_temperature"]
        amb_reasons: list[str] = []
        if m_ambient is None:
            if has_bad_ambient:
                amb_reasons.append("BAD_QUALITY_AMBIENT_TEMPERATURE")
            else:
                amb_reasons.append("MISSING_AMBIENT_TEMPERATURE")

        capabilities["ambient_monitoring"] = CapabilityItem(
            enabled=c0_enabled and (m_ambient is not None),
            evidence_grade="A" if (m_ambient is not None and m_ambient.quality.severity == QualitySeverity.GOOD) else ("B" if m_ambient is not None else "U"),
            required_inputs=["ambient_temperature"],
            missing_inputs=amb_missing,
            disabled_reason_codes=amb_reasons,
            model_status="NOT_APPLICABLE",
        )

        # ------------------------------------------------------------------
        # Thermal Residual Shadow Sub-capability (Under C2)
        # ------------------------------------------------------------------
        shadow_has_inputs = c2_enabled and (m_ambient is not None) and has_load_driver
        if self.qualification is not None:
            shadow_is_permitted = self.qualification.residual_display_qualification in (
                QualificationStatus.DESCRIPTIVE_ONLY,
                QualificationStatus.QUALIFIED,
            )
        else:
            shadow_is_permitted = (
                self.is_model_promoted
                or state.thermal_latent.model_status in ("PROMOTED", "SHADOW_DESCRIPTIVE")
                or state.thermal_latent.last_free_running_top_oil_degc is not None
            )
        shadow_enabled = shadow_has_inputs and shadow_is_permitted
        shadow_missing: list[str] = []
        shadow_reasons: list[str] = []
        if not c2_enabled:
            shadow_missing.append("top_oil_temperature")
            shadow_reasons.append("C2_UNAVAILABLE")
        if m_ambient is None:
            shadow_missing.append("ambient_temperature")
            shadow_reasons.append("MISSING_AMBIENT_TEMPERATURE")
        if not has_load_driver:
            shadow_missing.append("load_driver")
            shadow_reasons.append("MISSING_LOAD_DRIVER")
        if not shadow_is_permitted:
            shadow_reasons.append("RESIDUAL_DISPLAY_NOT_QUALIFIED")

        capabilities["thermal_residual_shadow"] = CapabilityItem(
            enabled=shadow_enabled,
            evidence_grade="B" if shadow_enabled else "U",
            required_inputs=["top_oil_temperature", "ambient_temperature", "load_driver"],
            missing_inputs=shadow_missing,
            disabled_reason_codes=shadow_reasons,
            model_status="DESCRIPTIVE_ONLY" if shadow_enabled else "DISABLED",
        )

        # ------------------------------------------------------------------
        # Tier C3: Thermal Predictive Modeling
        # ------------------------------------------------------------------
        c3_required = ["top_oil_temperature", "ambient_temperature", "load_driver", "promoted_thermal_model"]
        c3_missing: list[str] = []
        c3_reasons: list[str] = []

        if not c2_enabled:
            c3_missing.append("top_oil_temperature")
            c3_reasons.append("C2_UNAVAILABLE")

        if m_ambient is None:
            c3_missing.append("ambient_temperature")
            if has_bad_ambient:
                c3_reasons.append("BAD_QUALITY_AMBIENT_TEMPERATURE")
            else:
                c3_reasons.append("MISSING_AMBIENT_TEMPERATURE")

        if not has_load_driver:
            c3_missing.append("load_driver")
            c3_reasons.append("MISSING_LOAD_DRIVER")

        # Thermal model promotion / forecast qualification check
        forecast_is_qualified = (
            (self.qualification.forecast_qualification == QualificationStatus.QUALIFIED)
            if self.qualification is not None
            else (
                self.is_model_promoted
                or (state.thermal_latent.model_status == "PROMOTED" and self.model_version != "uncalibrated")
            )
        )

        model_status_str = "PROMOTED" if forecast_is_qualified else (
            state.thermal_latent.model_status if state.thermal_latent.model_status != "PROMOTED" else "UNCALIBRATED"
        )

        if not forecast_is_qualified:
            c3_missing.append("promoted_thermal_model")
            c3_reasons.append("MODEL_NOT_PROMOTED")

        c3_enabled = c2_enabled and (m_ambient is not None) and has_load_driver and forecast_is_qualified
        c3_grade = "A" if c3_enabled else "U"

        capabilities["C3"] = CapabilityItem(
            enabled=c3_enabled,
            evidence_grade=c3_grade,
            required_inputs=c3_required,
            missing_inputs=c3_missing,
            disabled_reason_codes=c3_reasons,
            coverage_pct=100.0 if c3_enabled else 0.0,
            model_status=model_status_str,
        )
        capabilities["thermal_prediction"] = capabilities["C3"]

        # ------------------------------------------------------------------
        # Tier C4: Thermal Exposure & Equivalent Ageing
        # ------------------------------------------------------------------
        c4_required = ["C3_thermal_predictive", "verified_insulation_class", "hotspot_estimate"]
        c4_missing: list[str] = []
        c4_reasons: list[str] = []

        if not c3_enabled:
            c4_missing.append("C3_thermal_predictive")
            c4_reasons.append("C3_UNAVAILABLE")

        # Verified insulation class check
        has_verified_insulation = False
        if self.profile is not None:
            if self.profile.insulation_paper_class in (
                InsulationClass.THERMALLY_UPGRADED,
                InsulationClass.NON_THERMALLY_UPGRADED,
            ):
                if self.profile.profile_status == ProfileVerificationStatus.VERIFIED:
                    has_verified_insulation = True
                elif "insulation_paper_class" in self.profile.fields and self.profile.fields["insulation_paper_class"].status == ProfileVerificationStatus.VERIFIED:
                    has_verified_insulation = True

        if not has_verified_insulation:
            c4_missing.append("verified_insulation_class")
            c4_reasons.append("MISSING_VERIFIED_INSULATION_CLASS")

        # Hot-spot estimate check
        hotspot_ok = self.hotspot_supported or state.exposure_state.is_ageing_enabled
        if not hotspot_ok:
            c4_missing.append("hotspot_estimate")
            c4_reasons.append("HOTSPOT_ESTIMATE_UNSUPPORTED")

        c4_enabled = c3_enabled and has_verified_insulation and hotspot_ok
        c4_grade = "A" if c4_enabled else "U"

        capabilities["C4"] = CapabilityItem(
            enabled=c4_enabled,
            evidence_grade=c4_grade,
            required_inputs=c4_required,
            missing_inputs=c4_missing,
            disabled_reason_codes=c4_reasons,
            coverage_pct=100.0 if c4_enabled else 0.0,
            model_status=model_status_str,
        )
        capabilities["thermal_ageing"] = capabilities["C4"]

        # ------------------------------------------------------------------
        # Determine highest enabled tier
        # ------------------------------------------------------------------
        if c4_enabled:
            highest_tier = CapabilityTier.C4_THERMAL_EXPOSURE
        elif c3_enabled:
            highest_tier = CapabilityTier.C3_THERMAL_PREDICTIVE
        elif c2_enabled:
            highest_tier = CapabilityTier.C2_THERMAL_DESCRIPTIVE
        elif c1_enabled:
            highest_tier = CapabilityTier.C1_ELECTRICAL
        else:
            highest_tier = CapabilityTier.C0_INTEGRITY

        profile_version = self.profile.profile_version if self.profile else "1.0.0"

        return CapabilityManifest(
            asset_id=state.asset_id,
            evaluated_at_utc=eval_time,
            evaluation_window_s=self.evaluation_window_s,
            highest_tier=highest_tier,
            available_signal_ids=available_signals,
            verified_metadata_ids=verified_metadata_ids,
            expected_cadence_s=self.expected_cadence_s,
            current_freshness_s=freshness_s,
            capabilities=capabilities,
            schema_version="1.0.0",
            profile_version=profile_version,
            model_version=self.model_version,
        )


def evaluate_capabilities(
    state: TwinState,
    profile: AssetProfile | None = None,
    model_version: str = "uncalibrated",
    is_model_promoted: bool = False,
    qualification: ThermalModelQualification | None = None,
    hotspot_supported: bool = False,
    expected_cadence_s: int = 900,
    evaluated_at_utc: datetime | None = None,
) -> CapabilityManifest:
    """Convenience functional interface to evaluate capabilities."""
    evaluator = CapabilityEvaluator(
        profile=profile,
        model_version=model_version,
        is_model_promoted=is_model_promoted,
        qualification=qualification,
        hotspot_supported=hotspot_supported,
        expected_cadence_s=expected_cadence_s,
    )
    return evaluator.evaluate(state, evaluated_at_utc=evaluated_at_utc)
