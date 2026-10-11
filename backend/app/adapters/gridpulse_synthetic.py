"""GridPulse Synthetic v1 Telemetry Source Adapter.

Translates candidate gridpulse_synthetic_v1 records into immutable
CanonicalEvent and Measurement instances conforming to project telemetry standards,
strict UCUM unit validation, full electrical, thermal, oil-level, and pressure domain support.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
import uuid

import pandas as pd

from app.adapters.base import BaseSourceAdapter
from app.core.units import canonicalize_unit_code, validate_unit
from app.models.profile import (
    AssetProfile,
    InsulationClass,
    ProfileField,
    ProfileVerificationStatus,
)
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)

logger = logging.getLogger("GridPulseSyntheticAdapter")

# Authoritative Tag Mapping for Candidate Dataset
SYNTHETIC_V1_TAG_MAP: Dict[str, Dict[str, Any]] = {
    # Voltages
    "v_l1n_v": {"signal_id": "voltage_v1", "phase": "L1", "unit": "V", "orig_unit": "V"},
    "v_l2n_v": {"signal_id": "voltage_v2", "phase": "L2", "unit": "V", "orig_unit": "V"},
    "v_l3n_v": {"signal_id": "voltage_v3", "phase": "L3", "unit": "V", "orig_unit": "V"},
    "v_l12_v": {"signal_id": "voltage_v12", "phase": "L1_L2", "unit": "V", "orig_unit": "V"},
    "v_l23_v": {"signal_id": "voltage_v23", "phase": "L2_L3", "unit": "V", "orig_unit": "V"},
    "v_l31_v": {"signal_id": "voltage_v31", "phase": "L3_L1", "unit": "V", "orig_unit": "V"},
    # Currents
    "i_l1_a": {"signal_id": "current_i1", "phase": "L1", "unit": "A", "orig_unit": "A"},
    "i_l2_a": {"signal_id": "current_i2", "phase": "L2", "unit": "A", "orig_unit": "A"},
    "i_l3_a": {"signal_id": "current_i3", "phase": "L3", "unit": "A", "orig_unit": "A"},
    "i_n_a": {"signal_id": "neutral_current", "phase": "N", "unit": "A", "orig_unit": "A"},
    # Power & Frequency
    "p_kw": {"signal_id": "active_power_total", "phase": None, "unit": "kW", "orig_unit": "kW"},
    "q_kvar": {"signal_id": "reactive_power_total", "phase": None, "unit": "kvar", "orig_unit": "kvar"},
    "s_kva": {"signal_id": "apparent_power_total", "phase": None, "unit": "kVA", "orig_unit": "kVA"},
    "pf": {"signal_id": "power_factor_total", "phase": None, "unit": "1", "orig_unit": "dimensionless"},
    "freq_hz": {"signal_id": "frequency", "phase": None, "unit": "Hz", "orig_unit": "Hz"},
    # Imbalances & Load
    "v_unbalance_pct": {"signal_id": "voltage_magnitude_imbalance_pct", "phase": None, "unit": "%", "orig_unit": "%"},
    "i_unbalance_pct": {"signal_id": "current_magnitude_imbalance_pct", "phase": None, "unit": "%", "orig_unit": "%"},
    "load_ratio": {"signal_id": "load_ratio", "phase": None, "unit": "1", "orig_unit": "ratio"},
    # Thermal
    "ambient_c": {"signal_id": "ambient_temperature", "phase": None, "unit": "Cel", "orig_unit": "°C"},
    "top_oil_c": {"signal_id": "top_oil_temperature", "phase": None, "unit": "Cel", "orig_unit": "°C"},
    # Oil Domain
    "oil_level_pct": {"signal_id": "oil_level_pct", "phase": None, "unit": "%", "orig_unit": "%"},
    "oil_level_ref_pct": {"signal_id": "oil_level_ref_pct", "phase": None, "unit": "%", "orig_unit": "%"},
    "oil_level_ref_temp_c": {"signal_id": "oil_level_ref_temp_c", "phase": None, "unit": "Cel", "orig_unit": "°C"},
    "oil_level_corrected_pct": {"signal_id": "oil_level_corrected_pct", "phase": None, "unit": "%", "orig_unit": "%"},
    "oil_level_trend_pct_per_day": {"signal_id": "oil_level_trend_pct_per_day", "phase": None, "unit": "percent/day", "orig_unit": "%/day"},
    "oil_level_low_alarm": {"signal_id": "oil_level_low_alarm", "phase": None, "unit": "1", "orig_unit": "binary"},
    # Pressure Domain
    "tank_pressure_kpa_g": {"signal_id": "tank_pressure_kpa_g", "phase": None, "unit": "kPa", "orig_unit": "kPa(g)"},
    "pressure_alarm": {"signal_id": "pressure_alarm", "phase": None, "unit": "1", "orig_unit": "binary"},
    "prd_operated": {"signal_id": "pressure_relief_operated", "phase": None, "unit": "1", "orig_unit": "binary"},
    "pressure_corrected_kpa_g": {"signal_id": "pressure_corrected_kpa_g", "phase": None, "unit": "kPa", "orig_unit": "kPa(g)"},
    "pressure_trend_kpa_per_day": {"signal_id": "pressure_trend_kpa_per_day", "phase": None, "unit": "kPa/day", "orig_unit": "kPa/day"},
    # Protection Contacts
    "lv_breaker_closed": {"signal_id": "lv_breaker_closed", "phase": None, "unit": "1", "orig_unit": "binary"},
    "lv_breaker_trip": {"signal_id": "lv_breaker_trip", "phase": None, "unit": "1", "orig_unit": "binary"},
    "hv_fuse_operated": {"signal_id": "hv_fuse_operated", "phase": None, "unit": "1", "orig_unit": "binary"},
    "oti_alarm": {"signal_id": "oti_alarm_contact", "phase": None, "unit": "1", "orig_unit": "binary"},
    "oti_trip": {"signal_id": "oti_trip_contact", "phase": None, "unit": "1", "orig_unit": "binary"},
}

SYNTHETIC_ASSET_PROFILES: Dict[str, AssetProfile] = {
    "DT-01": AssetProfile(
        asset_id="DT-01",
        phase_topology="THREE_PHASE_4W",
        nominal_frequency_hz=50.0,
        rated_kva=250.0,
        rated_voltage_hv_v=11000.0,
        rated_voltage_lv_v=250.0,
        rated_lv_v_ll=433.0,
        impedance_pct=4.5,
        tank_type="CONSERVATOR",
        has_oil_level_gauge=True,
        has_pressure_sensor=False,
        cooling_class="ONAN",
        insulation_paper_class=InsulationClass.NON_THERMALLY_UPGRADED,
        expected_cadence_s=1800,
        profile_status=ProfileVerificationStatus.VERIFIED,
        profile_version="1.0.0",
    ),
    "DT-02": AssetProfile(
        asset_id="DT-02",
        phase_topology="THREE_PHASE_4W",
        nominal_frequency_hz=50.0,
        rated_kva=500.0,
        rated_voltage_hv_v=11000.0,
        rated_voltage_lv_v=250.0,
        rated_lv_v_ll=433.0,
        impedance_pct=4.5,
        tank_type="CONSERVATOR",
        has_oil_level_gauge=True,
        has_pressure_sensor=False,
        cooling_class="ONAN",
        insulation_paper_class=InsulationClass.NON_THERMALLY_UPGRADED,
        expected_cadence_s=1800,
        profile_status=ProfileVerificationStatus.VERIFIED,
        profile_version="1.0.0",
    ),
    "DT-03": AssetProfile(
        asset_id="DT-03",
        phase_topology="THREE_PHASE_4W",
        nominal_frequency_hz=50.0,
        rated_kva=250.0,
        rated_voltage_hv_v=11000.0,
        rated_voltage_lv_v=250.0,
        rated_lv_v_ll=433.0,
        impedance_pct=4.5,
        tank_type="SEALED_CORRUGATED",
        has_oil_level_gauge=False,
        has_pressure_sensor=True,
        cooling_class="ONAN",
        insulation_paper_class=InsulationClass.NON_THERMALLY_UPGRADED,
        expected_cadence_s=1800,
        profile_status=ProfileVerificationStatus.VERIFIED,
        profile_version="1.0.0",
    ),
    "DT-04": AssetProfile(
        asset_id="DT-04",
        phase_topology="THREE_PHASE_4W",
        nominal_frequency_hz=50.0,
        rated_kva=160.0,
        rated_voltage_hv_v=11000.0,
        rated_voltage_lv_v=250.0,
        rated_lv_v_ll=433.0,
        impedance_pct=4.5,
        tank_type="CONSERVATOR",
        has_oil_level_gauge=True,
        has_pressure_sensor=False,
        cooling_class="ONAN",
        insulation_paper_class=InsulationClass.NON_THERMALLY_UPGRADED,
        expected_cadence_s=1800,
        profile_status=ProfileVerificationStatus.VERIFIED,
        profile_version="1.0.0",
    ),
}


class GridPulseSyntheticAdapter(BaseSourceAdapter):
    """Source adapter for gridpulse_synthetic_v1 benchmark telemetry."""

    def __init__(self) -> None:
        self._adapter_id = "gridpulse_synthetic_v1_adapter"
        self._source_system = "gridpulse_synthetic_v1"
        self._mapping_version = "synth-1.0.0"

    @property
    def adapter_id(self) -> str:
        return self._adapter_id

    @property
    def source_system(self) -> str:
        return self._source_system

    def transform_record(
        self,
        raw_record: Dict[str, Any],
        asset_id: str,
        source_uri: str,
        source_record_id: Optional[str] = None,
    ) -> CanonicalEvent:
        """Transforms a raw row dictionary into a CanonicalEvent."""
        raw_json = json.dumps(raw_record, sort_keys=True, default=str)
        raw_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

        # Parse timestamp
        t_raw = raw_record.get("timestamp_utc") or raw_record.get("timestamp")
        if isinstance(t_raw, str):
            event_time = datetime.fromisoformat(t_raw.replace("Z", "+00:00"))
        elif isinstance(t_raw, datetime):
            event_time = t_raw
        else:
            raise ValueError(f"Invalid timestamp in record: {t_raw}")

        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        rec_id = source_record_id or f"{asset_id}_{event_time.strftime('%Y%m%d%H%M%S')}"
        # Stable deterministic UUIDv5 scoped by asset, timestamp, and source record ID
        ev_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"gridpulse_synth:{asset_id}:{event_time.isoformat()}:{rec_id}"))

        source_ref = SourceRef(
            system=self.source_system,
            adapter_id=self.adapter_id,
            source_record_id=rec_id,
            source_uri=source_uri,
            raw_sha256=raw_hash,
        )

        dq_flag = str(raw_record.get("dq_flag", "OK")).strip().upper()
        event_flags = []
        if dq_flag != "OK":
            event_flags.append(dq_flag)

        partition = str(raw_record.get("partition", "")).strip().upper()
        if partition in ("FIT", "CAL", "TEST"):
            event_flags.append(f"PARTITION_{partition}")


        measurements: List[Measurement] = []

        for src_col, mapping in SYNTHETIC_V1_TAG_MAP.items():
            if src_col not in raw_record:
                continue

            raw_val = raw_record[src_col]
            if raw_val is None or (isinstance(raw_val, float) and math.isnan(raw_val)):
                continue

            # Determine quality
            flags: List[str] = []
            if dq_flag == "COMM_LOSS":
                severity = QualitySeverity.BAD
                flags.append("COMM_LOSS")
            else:
                severity = QualitySeverity.GOOD

            # Value normalization
            val_type: str = "float"
            norm_val: float | int | str | bool
            if isinstance(raw_val, bool):
                val_type = "bool"
                norm_val = raw_val
            elif isinstance(raw_val, int):
                val_type = "int"
                norm_val = raw_val
            elif isinstance(raw_val, float):
                val_type = "float"
                norm_val = float(raw_val)
            else:
                # Attempt float parse
                try:
                    norm_val = float(raw_val)
                    val_type = "float"
                except (ValueError, TypeError):
                    norm_val = str(raw_val)
                    val_type = "str"

            unit_ucum = canonicalize_unit_code(mapping["unit"])

            meas = Measurement(
                signal_id=mapping["signal_id"],
                phase=mapping["phase"],
                value=norm_val,
                value_type=val_type,  # type: ignore[arg-type]
                unit_ucum=unit_ucum,
                original_name=src_col,
                original_value=str(raw_val),
                original_unit=mapping["orig_unit"],
                quality=MeasurementQuality(
                    severity=severity,
                    flags=flags,
                    source_code=dq_flag if dq_flag != "OK" else None,
                ),
            )
            measurements.append(meas)

        if not measurements:
            # Fallback measurement if all were missing/NaN to maintain contract min_length=1
            meas = Measurement(
                signal_id="data_quality_heartbeat",
                phase=None,
                value=1 if dq_flag == "OK" else 0,
                value_type="int",
                unit_ucum="1",
                original_name="dq_flag",
                original_value=dq_flag,
                original_unit="dimensionless",
                quality=MeasurementQuality(
                    severity=QualitySeverity.BAD if dq_flag != "OK" else QualitySeverity.GOOD,
                    flags=event_flags,
                ),
            )
            measurements.append(meas)

        return CanonicalEvent(
            schema_version="1.0.0",
            event_id=ev_uuid,
            asset_id=asset_id,
            event_time_utc=event_time,
            received_time_utc=None,
            source=source_ref,
            measurements=measurements,
            event_quality_flags=event_flags,
            mapping_version=self._mapping_version,
        )

    def stream_events(
        self,
        source_input: Any,
        asset_id: str,
    ) -> Iterator[CanonicalEvent]:
        """Streams CanonicalEvents from a CSV file path or pandas DataFrame."""
        if isinstance(source_input, (str, Path)):
            df = pd.read_csv(source_input, low_memory=False)
            source_uri = str(source_input)
        elif isinstance(source_input, pd.DataFrame):
            df = source_input
            source_uri = "memory://dataframe"
        else:
            raise TypeError(f"Unsupported source_input type: {type(source_input)}")

        if "asset_id" in df.columns:
            df_asset = df[df["asset_id"] == asset_id].copy()
        else:
            df_asset = df.copy()

        # Deterministic chronological order
        time_col = "timestamp_utc" if "timestamp_utc" in df_asset.columns else "timestamp"
        df_asset = df_asset.sort_values(by=[time_col]).reset_index(drop=True)

        for idx, row in df_asset.iterrows():
            record_dict = row.to_dict()
            yield self.transform_record(
                raw_record=record_dict,
                asset_id=asset_id,
                source_uri=source_uri,
                source_record_id=f"row_{idx}",
            )
