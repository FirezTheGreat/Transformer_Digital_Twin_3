"""CPRI Synthetic Benchmark v3.0.2 Telemetry Source Adapter.

Translates v3.0.2 benchmark records (from clean DATA6.xz or DQ DATA5.xz) into immutable
CanonicalEvent and Measurement instances conforming to project telemetry standards,
strict UCUM unit validation, explicit 3-phase current separation, and zero oracle-label leakage.
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
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)

logger = logging.getLogger("CPRIv3Adapter")


# Authoritative Signal Mapping Definition
# Maps CPRI v3.0.2 column keys to canonical signal parameters
CPRI_V3_TAG_MAP: Dict[str, Dict[str, Any]] = {
    # 3-Phase Line-to-Neutral Voltages
    "x_v_l1n_v": {
        "signal_id": "voltage_v1",
        "phase": "L1",
        "unit": "V",
        "orig_unit": "V",
        "description": "Phase L1-to-Neutral Voltage",
    },
    "x_v_l2n_v": {
        "signal_id": "voltage_v2",
        "phase": "L2",
        "unit": "V",
        "orig_unit": "V",
        "description": "Phase L2-to-Neutral Voltage",
    },
    "x_v_l3n_v": {
        "signal_id": "voltage_v3",
        "phase": "L3",
        "unit": "V",
        "orig_unit": "V",
        "description": "Phase L3-to-Neutral Voltage",
    },
    # Line-to-Line Mean Voltage
    "x_voltage_ll_v": {
        "signal_id": "voltage_v_ll",
        "phase": None,
        "unit": "V",
        "orig_unit": "V",
        "description": "Mean Line-to-Line Voltage",
    },
    # 3-Phase Currents
    "x_i_l1_a": {
        "signal_id": "current_i1",
        "phase": "L1",
        "unit": "A",
        "orig_unit": "A",
        "description": "Phase L1 Current",
    },
    "x_i_l2_a": {
        "signal_id": "current_i2",
        "phase": "L2",
        "unit": "A",
        "orig_unit": "A",
        "description": "Phase L2 Current",
    },
    "x_i_l3_a": {
        "signal_id": "current_i3",
        "phase": "L3",
        "unit": "A",
        "orig_unit": "A",
        "description": "Phase L3 Current",
    },
    # Aggregate & Neutral Currents
    "x_current_a": {
        "signal_id": "current_mean",
        "phase": None,
        "unit": "A",
        "orig_unit": "A",
        "description": "Mean Phase Current",
    },
    "x_neutral_current_a": {
        "signal_id": "neutral_current",
        "phase": "N",
        "unit": "A",
        "orig_unit": "A",
        "description": "Neutral Conductor Current",
    },
    # Powers & Frequency
    "x_active_power_kw": {
        "signal_id": "active_power_total",
        "phase": None,
        "unit": "kW",
        "orig_unit": "kW",
        "description": "Total Active Power",
    },
    "x_reactive_power_kvar": {
        "signal_id": "reactive_power_total",
        "phase": None,
        "unit": "kvar",
        "orig_unit": "kvar",
        "description": "Total Reactive Power",
    },
    "x_apparent_power_kva": {
        "signal_id": "apparent_power_total",
        "phase": None,
        "unit": "kVA",
        "orig_unit": "kVA",
        "description": "Total Apparent Power",
    },
    "x_power_factor": {
        "signal_id": "power_factor_total",
        "phase": None,
        "unit": "1",
        "orig_unit": "dimensionless",
        "description": "Total Power Factor",
    },
    "x_frequency_hz": {
        "signal_id": "frequency",
        "phase": None,
        "unit": "Hz",
        "orig_unit": "Hz",
        "description": "System Frequency",
    },
    # Harmonics
    "x_voltage_thd_pct": {
        "signal_id": "thd_voltage",
        "phase": None,
        "unit": "%",
        "orig_unit": "%",
        "description": "Total Harmonic Distortion (Voltage)",
    },
    "x_current_thd_pct": {
        "signal_id": "thd_current",
        "phase": None,
        "unit": "%",
        "orig_unit": "%",
        "description": "Total Harmonic Distortion (Current)",
    },
    # Imbalances
    "x_voltage_unbalance_pct": {
        "signal_id": "voltage_magnitude_imbalance_pct",
        "phase": None,
        "unit": "%",
        "orig_unit": "%",
        "description": "Voltage Magnitude Imbalance Percentage",
    },
    "x_current_unbalance_pct": {
        "signal_id": "current_magnitude_imbalance_pct",
        "phase": None,
        "unit": "%",
        "orig_unit": "%",
        "description": "Current Magnitude Imbalance Percentage",
    },
    # Thermal Telemetry
    "x_ambient_temp_c": {
        "signal_id": "ambient_temperature",
        "phase": None,
        "unit": "Cel",
        "orig_unit": "°C",
        "description": "Ambient Temperature",
    },
    "x_oil_temp_c": {
        "signal_id": "top_oil_temperature",
        "phase": None,
        "unit": "Cel",
        "orig_unit": "°C",
        "description": "Top-Oil Temperature",
    },
    "x_winding_temp_c": {
        "signal_id": "winding_temperature_indicator",
        "phase": None,
        "unit": "Cel",
        "orig_unit": "°C",
        "description": "Simulated Winding Temperature Indicator (WTI)",
    },
    "x_bushing_temp_c": {
        "signal_id": "bushing_temperature",
        "phase": None,
        "unit": "Cel",
        "orig_unit": "°C",
        "description": "Bushing Temperature",
    },
    # Condition & Fluid
    "x_vibration_mm_s_rms": {
        "signal_id": "vibration_rms",
        "phase": None,
        "unit": "mm/s",
        "orig_unit": "mm/s",
        "description": "Tank-Wall Vibration RMS",
    },
    "x_oil_level_pct": {
        "signal_id": "oil_level_pct",
        "phase": None,
        "unit": "%",
        "orig_unit": "%",
        "description": "Conservator Oil Level Gauge Percentage",
    },
    # Declared Rating
    "x_rating_kva": {
        "signal_id": "rated_kva",
        "phase": None,
        "unit": "kVA",
        "orig_unit": "kVA",
        "description": "Declared Synthetic Transformer Rating",
    },
}

# Explicitly excluded oracle / evaluation columns
ORACLE_COLUMNS: set[str] = {
    "y_anomaly",
    "y_fault_type",
    "y_fault_domain",
    "y_severity",
    "y_event_id",
    "y_thermal_alert_level",
    "y_wti_alarm",
    "y_fit_eligible",
    "y_dq_defect",
    "y_dq_id",
}


class CPRIv3SourceAdapter(BaseSourceAdapter):
    """Canonical source adapter for CPRI synthetic benchmark v3.0.2 telemetry."""

    def __init__(
        self,
        adapter_id: str = "cpri_v3_adapter",
        source_system: str = "cpri_v3_synthetic",
        mapping_version: str = "3.0.2",
    ) -> None:
        self._adapter_id = adapter_id
        self._source_system = source_system
        self._mapping_version = mapping_version

    @property
    def adapter_id(self) -> str:
        return self._adapter_id

    @property
    def source_system(self) -> str:
        return self._source_system

    @property
    def mapping_version(self) -> str:
        return self._mapping_version

    def transform_record(
        self,
        raw_record: Dict[str, Any],
        asset_id: Optional[str] = None,
        source_uri: str = "temp_dataset/DATA6.xz",
        source_record_id: Optional[str] = None,
    ) -> CanonicalEvent:
        """Transforms a single raw v3.0.2 record into an immutable CanonicalEvent.

        Args:
            raw_record: Dictionary of column name to value.
            asset_id: Optional override; if None, resolved from 'meta_transformer_id'.
            source_uri: Identifier for provenance source.
            source_record_id: Optional record index or identifier.

        Returns:
            CanonicalEvent: Conforming canonical telemetry event envelope.
        """
        # Resolve asset ID
        resolved_asset_id = (
            str(asset_id).strip()
            if asset_id is not None
            else str(raw_record.get("meta_transformer_id", "TX_UNKNOWN")).strip()
        )

        # Parse timestamp preserving timezone and normalize to UTC
        raw_ts = raw_record.get("meta_timestamp") or raw_record.get("Timestamp")
        if raw_ts is None:
            raise ValueError("Record missing required timestamp ('meta_timestamp' or 'Timestamp')")

        if isinstance(raw_ts, datetime):
            dt = raw_ts
        else:
            dt = pd.to_datetime(raw_ts)

        if dt.tzinfo is None:
            # Default to Asia/Kolkata +05:30 if naive
            dt_aware = dt.tz_localize("Asia/Kolkata")
        else:
            dt_aware = dt

        event_time_utc = dt_aware.astimezone(timezone.utc)

        # Generate deterministic event_id via UUIDv5
        rec_id = source_record_id or f"{resolved_asset_id}:{event_time_utc.isoformat()}"
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:cpri:v3:{rec_id}"))

        # Build measurements
        measurements: List[Measurement] = []
        envelope_quality_flags: List[str] = []

        for raw_col, map_spec in CPRI_V3_TAG_MAP.items():
            if raw_col not in raw_record:
                continue

            raw_val = raw_record[raw_col]
            sig_id = map_spec["signal_id"]
            phase = map_spec["phase"]
            unit_ucum = map_spec["unit"]
            orig_unit = map_spec["orig_unit"]

            # Handle missing / NaN / null values deterministically
            if raw_val is None or (isinstance(raw_val, float) and (math.isnan(raw_val) or pd.isna(raw_val))):
                envelope_quality_flags.append(f"MISSING_{sig_id.upper()}")
                continue

            try:
                val_num = float(raw_val)
                quality = MeasurementQuality(
                    severity=QualitySeverity.GOOD,
                    flags=[],
                    source_code="RAW_VALID",
                )
            except (ValueError, TypeError):
                envelope_quality_flags.append(f"INVALID_{sig_id.upper()}")
                continue

            meas = Measurement(
                signal_id=sig_id,
                phase=phase,
                value=val_num,
                value_type="float",
                unit_ucum=unit_ucum,
                original_name=raw_col,
                original_value=str(raw_val),
                original_unit=orig_unit,
                quality=quality,
            )
            measurements.append(meas)

        if not measurements:
            raise ValueError(f"No valid telemetry measurements found in record for {resolved_asset_id}")

        # Compute SHA-256 of raw payload for provenance
        payload_str = json.dumps(
            {k: str(v) for k, v in raw_record.items() if k not in ORACLE_COLUMNS},
            sort_keys=True,
        )
        raw_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        source_ref = SourceRef(
            system=self.source_system,
            adapter_id=self.adapter_id,
            source_record_id=str(rec_id),
            source_uri=source_uri,
            raw_sha256=raw_hash,
        )

        return CanonicalEvent(
            schema_version="1.0.0",
            event_id=event_id,
            asset_id=resolved_asset_id,
            event_time_utc=event_time_utc,
            received_time_utc=None,  # Historical telemetry without native receive timestamp
            source=source_ref,
            measurements=measurements,
            event_quality_flags=sorted(list(set(envelope_quality_flags))),
            mapping_version=self.mapping_version,
        )

    def stream_events(
        self,
        source_input: Any,
        asset_id: Optional[str] = None,
    ) -> Iterator[CanonicalEvent]:
        """Streams CanonicalEvents from an iterable of dicts or DataFrame."""
        if isinstance(source_input, pd.DataFrame):
            records = source_input.to_dict(orient="records")
        elif isinstance(source_input, list):
            records = source_input
        else:
            raise TypeError(f"Unsupported source_input type: {type(source_input)}")

        for idx, rec in enumerate(records):
            yield self.transform_record(
                raw_record=rec,
                asset_id=asset_id,
                source_record_id=f"row_{idx}",
            )
