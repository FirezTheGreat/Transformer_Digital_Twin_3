"""Three-Phase Electrical Physics and Feature Derivation Engine.

Pure deterministic physical calculations:
- Apparent power derivation (S = sqrt(P^2 + Q^2))
- Power factor derivation (PF = |P| / S)
- Three-phase current magnitude imbalance (% IUB per NEMA)
- Three-phase voltage magnitude imbalance (% VUB per NEMA)
- Neutral current ratio (I_n / max(I_eq, floor))
- P-Q-S inconsistency metric (|S_obs^2 - P^2 - Q^2| / max(S_obs^2, floor))
- Relative load index (u = S / S_rated or u = S / S_ref)
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from app.core.units import convert_quantity
from app.models.features import DerivedFeatures
from app.models.profile import AssetProfile, ProfileVerificationStatus
from app.models.telemetry import CanonicalEvent, Measurement, QualitySeverity


def calculate_apparent_power(
    p_kw: float | None,
    q_kvar: float | None,
) -> float | None:
    """Derive apparent power in kVA from active power (kW) and reactive power (kvar).

    Returns:
        float | None: S = sqrt(P^2 + Q^2) >= 0.0 in kVA, or None if inputs are missing.
    """
    if p_kw is None or q_kvar is None:
        return None
    return round(math.sqrt(p_kw * p_kw + q_kvar * q_kvar), 4)


def calculate_reactive_power_magnitude(
    p_kw: float | None,
    s_kva: float | None,
) -> float | None:
    """Derive magnitude of reactive power |Q| = sqrt(max(0, S^2 - P^2)) in kvar from P and S.

    Adheres strictly to electrical physics: returns magnitude only and never fabricates reactive sign.
    """
    if p_kw is None or s_kva is None:
        return None
    diff = max(0.0, s_kva * s_kva - p_kw * p_kw)
    return round(math.sqrt(diff), 4)


def calculate_power_factor(
    p_kw: float | None,
    s_kva: float | None,
    floor_kva: float = 1e-3,
    signed: bool = False,
) -> float | None:
    """Derive power factor from active power (kW) and apparent power (kVA).

    Args:
        p_kw: Total active power in kW.
        s_kva: Total apparent power in kVA.
        floor_kva: Floor below which apparent power is treated as de-energized/insignificant.
        signed: If True, preserves active power sign for import/export flow (+ import, - export).
                If False (default), returns magnitude |P| / S in [0.0, 1.0].

    Returns:
        float | None: PF in range [-1.0, 1.0] (if signed) or [0.0, 1.0] (if unsigned),
                      or None if inputs missing or S <= floor.
    """
    if p_kw is None or s_kva is None:
        return None
    if s_kva <= floor_kva:
        return None
    pf = (p_kw / s_kva) if signed else (abs(p_kw) / s_kva)
    if signed:
        return round(min(1.0, max(-1.0, pf)), 4)
    return round(min(1.0, max(0.0, pf)), 4)


def calculate_current_imbalance(
    i_l1: float | None,
    i_l2: float | None,
    i_l3: float | None,
    floor_a: float = 0.1,
) -> tuple[float | None, float | None]:
    """Calculate three-phase mean current and NEMA current magnitude imbalance percentage.

    Returns:
        tuple[float | None, float | None]: (current_mean_a, current_magnitude_imbalance_pct).
        Both are None if any phase is missing.
    """
    if i_l1 is None or i_l2 is None or i_l3 is None:
        return None, None

    i1, i2, i3 = abs(i_l1), abs(i_l2), abs(i_l3)
    mean_i = (i1 + i2 + i3) / 3.0

    if mean_i < floor_a:
        return round(mean_i, 4), 0.0

    max_dev = max(abs(i1 - mean_i), abs(i2 - mean_i), abs(i3 - mean_i))
    imbalance_pct = 100.0 * max_dev / mean_i
    return round(mean_i, 4), round(imbalance_pct, 4)


def calculate_voltage_imbalance(
    v1: float | None,
    v2: float | None,
    v3: float | None,
    floor_v: float = 1.0,
) -> float | None:
    """Calculate NEMA voltage magnitude imbalance percentage across 3 voltages with identical basis.

    Returns:
        float | None: NEMA % VUB, or None if any phase is missing.
    """
    if v1 is None or v2 is None or v3 is None:
        return None

    val1, val2, val3 = abs(v1), abs(v2), abs(v3)
    mean_v = (val1 + val2 + val3) / 3.0

    if mean_v < floor_v:
        return 0.0

    max_dev = max(abs(val1 - mean_v), abs(val2 - mean_v), abs(val3 - mean_v))
    imbalance_pct = 100.0 * max_dev / mean_v
    return round(imbalance_pct, 4)


def calculate_equivalent_current(
    i_l1: float | None,
    i_l2: float | None,
    i_l3: float | None,
) -> float | None:
    """Calculate equivalent RMS phase current I_eq = sqrt((I1^2 + I2^2 + I3^2) / 3)."""
    if i_l1 is None or i_l2 is None or i_l3 is None:
        return None
    return math.sqrt((i_l1**2 + i_l2**2 + i_l3**2) / 3.0)


def calculate_neutral_current_ratio(
    i_n: float | None,
    i_l1: float | None,
    i_l2: float | None,
    i_l3: float | None,
    floor_a: float = 0.1,
) -> float | None:
    """Calculate neutral current ratio = |I_n| / max(I_eq, floor).

    Returns:
        float | None: Dimensionless ratio >= 0.0, or None if I_n or phase currents missing.
    """
    if i_n is None or i_l1 is None or i_l2 is None or i_l3 is None:
        return None

    i_eq = calculate_equivalent_current(i_l1, i_l2, i_l3)
    if i_eq is None:
        return None

    denominator = max(i_eq, floor_a)
    return round(abs(i_n) / denominator, 4)


def calculate_pqs_inconsistency(
    s_obs_kva: float | None,
    p_kw: float | None,
    q_kvar: float | None,
    floor_sq: float = 1e-4,
) -> float | None:
    """Calculate P-Q-S inconsistency metric = |S_obs^2 - P^2 - Q^2| / max(S_obs^2, floor).

    Returns:
        float | None: Dimensionless relative error metric >= 0.0, or None if inputs missing.
    """
    if s_obs_kva is None or p_kw is None or q_kvar is None:
        return None

    s_sq = s_obs_kva * s_obs_kva
    pq_sq = p_kw * p_kw + q_kvar * q_kvar
    numerator = abs(s_sq - pq_sq)
    denominator = max(s_sq, floor_sq)
    return round(numerator / denominator, 6)


def calculate_relative_load_index(
    s_kva: float | None,
    rated_kva: float | None = None,
    reference_kva: float = 142.898,
) -> float | None:
    """Calculate relative load index u = S / S_base.

    If verified rated_kva is provided (> 0), uses rated_kva.
    Otherwise uses frozen training reference_kva (e.g. 142.898 kVA for Tripura).

    Returns:
        float | None: Dimensionless relative load index >= 0.0, or None if S is missing.
    """
    if s_kva is None:
        return None

    basis = rated_kva if (rated_kva is not None and rated_kva > 0) else reference_kva
    if basis <= 0:
        return None

    return round(max(0.0, s_kva / basis), 4)


def calculate_prospective_short_circuit_ka(
    rated_kva: float | None,
    rated_lv_v_ll: float | None,
    impedance_pct: float | None,
) -> float | None:
    """Calculate prospective symmetrical short-circuit current reference in kA.

    Formula (symmetrical fault at transformer terminals):
        I_rated_lv_a = (S_rated_kva * 1000) / (sqrt(3) * V_ll_v)
        I_sc_sym_ka  = (I_rated_lv_a / (impedance_pct / 100)) / 1000.0

    Assumptions & Scope:
        - Stated as prospective steady-state reference under bolted 3-phase symmetrical fault.
        - Does NOT represent dynamic sub-cycle transient waveforms, asymmetric DC offset,
          protection coordination, interrupting capacity, or mechanical withstand.
    """
    if rated_kva is None or rated_lv_v_ll is None or impedance_pct is None:
        return None
    if not (math.isfinite(rated_kva) and math.isfinite(rated_lv_v_ll) and math.isfinite(impedance_pct)):
        return None
    if rated_kva <= 0 or rated_lv_v_ll <= 0 or impedance_pct <= 0:
        return None
    z_pu = impedance_pct / 100.0
    i_rated_a = (rated_kva * 1000.0) / (math.sqrt(3.0) * rated_lv_v_ll)
    i_sc_ka = (i_rated_a / z_pu) / 1000.0
    return round(i_sc_ka, 3)



def extract_electrical_features(
    event: CanonicalEvent,
    profile: AssetProfile | None = None,
    load_reference_kva: float = 142.898,
) -> DerivedFeatures:
    """Extract deterministic electrical features from a CanonicalEvent.

    Adheres strictly to the locked derived feature specifications and preserves
    observed vs derived value separation.
    """
    # Index usable measurements by signal_id and (signal_id, phase)
    meas_by_sig: dict[str, float] = {}
    meas_by_sig_phase: dict[tuple[str, str | None], float] = {}

    for m in event.measurements:
        if m.quality.severity == QualitySeverity.BAD:
            continue
        if isinstance(m.value, (int, float)) and not isinstance(m.value, bool):
            val = float(m.value)
            meas_by_sig[m.signal_id] = val
            meas_by_sig_phase[(m.signal_id, m.phase)] = val

    # 1. Active & Reactive Power
    p_kw = meas_by_sig.get("active_power_total") or meas_by_sig.get("active_power")
    if p_kw is None and "active_power_l1" in meas_by_sig and "active_power_l2" in meas_by_sig and "active_power_l3" in meas_by_sig:
        p_kw = meas_by_sig["active_power_l1"] + meas_by_sig["active_power_l2"] + meas_by_sig["active_power_l3"]

    q_kvar = meas_by_sig.get("reactive_power_total") or meas_by_sig.get("reactive_power")
    if q_kvar is None and "reactive_power_l1" in meas_by_sig and "reactive_power_l2" in meas_by_sig and "reactive_power_l3" in meas_by_sig:
        q_kvar = meas_by_sig["reactive_power_l1"] + meas_by_sig["reactive_power_l2"] + meas_by_sig["reactive_power_l3"]

    s_obs = meas_by_sig.get("apparent_power_total") or meas_by_sig.get("apparent_power")
    if s_obs is None and "apparent_power_l1" in meas_by_sig and "apparent_power_l2" in meas_by_sig and "apparent_power_l3" in meas_by_sig:
        s_obs = meas_by_sig["apparent_power_l1"] + meas_by_sig["apparent_power_l2"] + meas_by_sig["apparent_power_l3"]

    # 2. Phase Currents
    i_l1 = (
        meas_by_sig_phase.get(("current_l1", "L1"))
        or meas_by_sig.get("current_l1")
        or meas_by_sig_phase.get(("current_i1", "L1"))
        or meas_by_sig.get("current_i1")
        or meas_by_sig_phase.get(("current", "L1"))
        or meas_by_sig_phase.get(("current", "A"))
    )
    i_l2 = (
        meas_by_sig_phase.get(("current_l2", "L2"))
        or meas_by_sig.get("current_l2")
        or meas_by_sig_phase.get(("current_i2", "L2"))
        or meas_by_sig.get("current_i2")
        or meas_by_sig_phase.get(("current", "L2"))
        or meas_by_sig_phase.get(("current", "B"))
    )
    i_l3 = (
        meas_by_sig_phase.get(("current_l3", "L3"))
        or meas_by_sig.get("current_l3")
        or meas_by_sig_phase.get(("current_i3", "L3"))
        or meas_by_sig.get("current_i3")
        or meas_by_sig_phase.get(("current", "L3"))
        or meas_by_sig_phase.get(("current", "C"))
    )
    i_n = meas_by_sig_phase.get(("neutral_current", "N")) or meas_by_sig.get("neutral_current")

    # 3. Phase Voltages (Line-to-Neutral preferred, Line-to-Line alternative)
    v_l1 = (
        meas_by_sig_phase.get(("voltage_l1_n", "L1"))
        or meas_by_sig.get("voltage_l1_n")
        or meas_by_sig_phase.get(("voltage_v1", "L1"))
        or meas_by_sig.get("voltage_v1")
        or meas_by_sig_phase.get(("voltage", "L1"))
        or meas_by_sig_phase.get(("voltage", "A"))
    )
    v_l2 = (
        meas_by_sig_phase.get(("voltage_l2_n", "L2"))
        or meas_by_sig.get("voltage_l2_n")
        or meas_by_sig_phase.get(("voltage_v2", "L2"))
        or meas_by_sig.get("voltage_v2")
        or meas_by_sig_phase.get(("voltage", "L2"))
        or meas_by_sig_phase.get(("voltage", "B"))
    )
    v_l3 = (
        meas_by_sig_phase.get(("voltage_l3_n", "L3"))
        or meas_by_sig.get("voltage_l3_n")
        or meas_by_sig_phase.get(("voltage_v3", "L3"))
        or meas_by_sig.get("voltage_v3")
        or meas_by_sig_phase.get(("voltage", "L3"))
        or meas_by_sig_phase.get(("voltage", "C"))
    )

    if v_l1 is None or v_l2 is None or v_l3 is None:
        v_l1 = (
            meas_by_sig_phase.get(("voltage_l1_l2", "L1_L2"))
            or meas_by_sig.get("voltage_l1_l2")
            or meas_by_sig_phase.get(("voltage_v12", "L1_L2"))
            or meas_by_sig.get("voltage_v12")
        )
        v_l2 = (
            meas_by_sig_phase.get(("voltage_l2_l3", "L2_L3"))
            or meas_by_sig.get("voltage_l2_l3")
            or meas_by_sig_phase.get(("voltage_v23", "L2_L3"))
            or meas_by_sig.get("voltage_v23")
        )
        v_l3 = (
            meas_by_sig_phase.get(("voltage_l3_l1", "L3_L1"))
            or meas_by_sig.get("voltage_l3_l1")
            or meas_by_sig_phase.get(("voltage_v31", "L3_L1"))
            or meas_by_sig.get("voltage_v31")
        )

    # Apparent Power derived: S = sqrt(P^2 + Q^2)
    s_derived = calculate_apparent_power(p_kw, q_kvar)

    # Power Factor derived: prefer observed apparent power S_obs directly from meter when valid;
    # otherwise fallback to derived apparent power from compatible active/reactive power.
    s_for_pf = s_obs if (s_obs is not None and s_obs > 1e-3) else s_derived
    pf_derived = calculate_power_factor(p_kw, s_for_pf)

    # Current Mean and Imbalance
    mean_i, i_imbalance = calculate_current_imbalance(i_l1, i_l2, i_l3)

    # Voltage Imbalance
    v_imbalance = calculate_voltage_imbalance(v_l1, v_l2, v_l3)

    # Neutral Current Ratio
    in_ratio = calculate_neutral_current_ratio(i_n, i_l1, i_l2, i_l3)

    # P-Q-S Inconsistency Metric
    pqs_err = calculate_pqs_inconsistency(s_obs, p_kw, q_kvar)

    # Relative Load Index: precedence (1) s_obs, (2) s_derived, (3) current-based proxy
    s_drive = s_obs if s_obs is not None else s_derived
    ref_k = load_reference_kva
    if profile and "load_reference_kva" in profile.fields:
        field_val = profile.fields["load_reference_kva"].value
        if isinstance(field_val, (int, float)) and field_val > 0:
            ref_k = float(field_val)

    rated_k = (
        profile.rated_kva
        if (profile and profile.profile_status == ProfileVerificationStatus.VERIFIED and profile.rated_kva)
        else None
    )
    u_load = calculate_relative_load_index(s_drive, rated_kva=rated_k, reference_kva=ref_k)

    # Prospective short-circuit calculation (Extra C)
    r_kva_for_sc = rated_k or (profile.rated_kva if profile else None) or meas_by_sig.get("rated_kva")
    v_ll_for_sc = (
        (profile.rated_lv_v_ll if profile else None)
        or (meas_by_sig.get("rated_lv_v_ll"))
        or ((profile.rated_voltage_lv_v * math.sqrt(3.0)) if profile and profile.rated_voltage_lv_v else None)
    )
    z_pct_for_sc = (profile.impedance_pct if profile else None) or meas_by_sig.get("impedance_pct")
    isc_ka = calculate_prospective_short_circuit_ka(r_kva_for_sc, v_ll_for_sc, z_pct_for_sc)

    return DerivedFeatures(
        timestamp_utc=event.event_time_utc,
        apparent_power_derived_kva=s_derived,
        power_factor_derived=pf_derived,
        current_mean_a=mean_i,
        current_magnitude_imbalance_pct=i_imbalance,
        voltage_magnitude_imbalance_pct=v_imbalance,
        neutral_current_ratio=in_ratio,
        pqs_inconsistency=pqs_err,
        relative_load_index=u_load,
        thermal_residual_degc=None,  # Populated by Thermal Gate
        prospective_short_circuit_ka=isc_ka,
        transform_version="1.0.0",
    )
