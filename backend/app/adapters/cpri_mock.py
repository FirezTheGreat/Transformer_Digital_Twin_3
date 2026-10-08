"""CPRI Mock Telemetry Source Adapter.

Phase 2, Substep 2.1 Implementation.
Translates synthetic CPRI-formatted mock telemetry streams into the standard CanonicalEvent contract,
proving multi-source adapter isolation and schema uniformity.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Literal, Optional
import uuid

import pandas as pd

from app.adapters.base import BaseSourceAdapter
from app.core.units import canonicalize_unit_code
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


class CPRIMockAdapter(BaseSourceAdapter):
    """Source adapter for synthetic CPRI-style telemetry streams."""

    CPRI_TAG_MAP: Dict[str, Dict[str, Any]] = {
        # 3-Phase Voltages (Phase & Alternate namings)
        "v_r": {"canonical_name": "voltage_v1", "phase": "L1", "unit": "V", "type": "float"},
        "v_y": {"canonical_name": "voltage_v2", "phase": "L2", "unit": "V", "type": "float"},
        "v_b": {"canonical_name": "voltage_v3", "phase": "L3", "unit": "V", "type": "float"},
        "vl1": {"canonical_name": "voltage_v1", "phase": "L1", "unit": "V", "type": "float"},
        "vl2": {"canonical_name": "voltage_v2", "phase": "L2", "unit": "V", "type": "float"},
        "vl3": {"canonical_name": "voltage_v3", "phase": "L3", "unit": "V", "type": "float"},
        "voltage": {"canonical_name": "voltage_v1", "phase": None, "unit": "V", "type": "float"},

        # 3-Phase Currents (Phase & Alternate namings)
        "i_r": {"canonical_name": "current_i1", "phase": "L1", "unit": "A", "type": "float"},
        "i_y": {"canonical_name": "current_i2", "phase": "L2", "unit": "A", "type": "float"},
        "i_b": {"canonical_name": "current_i3", "phase": "L3", "unit": "A", "type": "float"},
        "il1": {"canonical_name": "current_i1", "phase": "L1", "unit": "A", "type": "float"},
        "il2": {"canonical_name": "current_i2", "phase": "L2", "unit": "A", "type": "float"},
        "il3": {"canonical_name": "current_i3", "phase": "L3", "unit": "A", "type": "float"},
        "current": {"canonical_name": "current_i1", "phase": None, "unit": "A", "type": "float"},
        "inut": {"canonical_name": "neutral_current", "phase": "N", "unit": "A", "type": "float"},
        "neutral_current": {"canonical_name": "neutral_current", "phase": "N", "unit": "A", "type": "float"},

        # Electrical Powers & Frequency
        "active_kw": {"canonical_name": "active_power_total", "phase": None, "unit": "kW", "type": "float"},
        "kw": {"canonical_name": "active_power_total", "phase": None, "unit": "kW", "type": "float"},
        "reactive_kvar": {"canonical_name": "reactive_power_total", "phase": None, "unit": "kvar", "type": "float"},
        "kvar": {"canonical_name": "reactive_power_total", "phase": None, "unit": "kvar", "type": "float"},
        "apparent_kva": {"canonical_name": "apparent_power_total", "phase": None, "unit": "kVA", "type": "float"},
        "kva": {"canonical_name": "apparent_power_total", "phase": None, "unit": "kVA", "type": "float"},
        "pf_3ph": {"canonical_name": "power_factor_total", "phase": None, "unit": "dimensionless", "type": "float"},
        "pf": {"canonical_name": "power_factor_total", "phase": None, "unit": "dimensionless", "type": "float"},
        "power_factor": {"canonical_name": "power_factor_total", "phase": None, "unit": "dimensionless", "type": "float"},
        "freq": {"canonical_name": "frequency", "phase": None, "unit": "Hz", "type": "float"},
        "frequency": {"canonical_name": "frequency", "phase": None, "unit": "Hz", "type": "float"},

        # Harmonics & Imbalance
        "thd": {"canonical_name": "thd_total", "phase": None, "unit": "%", "type": "float"},
        "thd_pct": {"canonical_name": "thd_total", "phase": None, "unit": "%", "type": "float"},
        "voltage_unbalance": {"canonical_name": "voltage_magnitude_imbalance_pct", "phase": None, "unit": "%", "type": "float"},
        "voltage_unbalance_pct": {"canonical_name": "voltage_magnitude_imbalance_pct", "phase": None, "unit": "%", "type": "float"},
        "current_unbalance": {"canonical_name": "current_magnitude_imbalance_pct", "phase": None, "unit": "%", "type": "float"},
        "current_unbalance_pct": {"canonical_name": "current_magnitude_imbalance_pct", "phase": None, "unit": "%", "type": "float"},

        # Thermal Telemetry (Continuous measurements strictly distinct from discrete contacts)
        "top_oil_degc": {"canonical_name": "top_oil_temperature", "phase": None, "unit": "Cel", "type": "float"},
        "oil_temp": {"canonical_name": "top_oil_temperature", "phase": None, "unit": "Cel", "type": "float"},
        "oil_temp_degc": {"canonical_name": "top_oil_temperature", "phase": None, "unit": "Cel", "type": "float"},
        "ambient_degc": {"canonical_name": "ambient_temperature", "phase": None, "unit": "Cel", "type": "float"},
        "ambient_temp": {"canonical_name": "ambient_temperature", "phase": None, "unit": "Cel", "type": "float"},
        "winding_temp_degc": {"canonical_name": "winding_temperature", "phase": None, "unit": "Cel", "type": "float"},
        "winding_temp": {"canonical_name": "winding_temperature", "phase": None, "unit": "Cel", "type": "float"},
        "winding_temperature": {"canonical_name": "winding_temperature", "phase": None, "unit": "Cel", "type": "float"},

        # Physical Condition Telemetry
        "vibration": {"canonical_name": "vibration_rms", "phase": None, "unit": "m/s2", "type": "float"},
        "vibration_rms": {"canonical_name": "vibration_rms", "phase": None, "unit": "m/s2", "type": "float"},
        "oil_level": {"canonical_name": "oil_level_pct", "phase": None, "unit": "%", "type": "float"},
        "oil_level_pct": {"canonical_name": "oil_level_pct", "phase": None, "unit": "%", "type": "float"},
        "bushing_temp_degc": {"canonical_name": "bushing_temperature", "phase": None, "unit": "Cel", "type": "float"},
        "bushing_temp": {"canonical_name": "bushing_temperature", "phase": None, "unit": "Cel", "type": "float"},
    }

    def __init__(self, adapter_id: str = "cpri_mock_v1") -> None:
        self._adapter_id = adapter_id
        self._source_system = "cpri_mock"

    @property
    def adapter_id(self) -> str:
        return self._adapter_id

    @property
    def source_system(self) -> str:
        return self._source_system

    def transform_record(
        self,
        raw_record: Dict[str, Any],
        asset_id: str = "CPRI_MOCK_TX_01",
        source_uri: str = "fixtures/cpri_mock_stream.json",
        source_record_id: Optional[str] = None,
    ) -> CanonicalEvent:
        """Transforms a CPRI mock record dictionary into a CanonicalEvent."""
        # 1. Source-driven transformer ID extraction
        resolved_asset_id = (
            str(raw_record.get("transformer_id") or raw_record.get("asset_id") or raw_record.get("DeviceID") or asset_id)
        ).strip()

        ts_raw = raw_record.get("timestamp") or raw_record.get("DeviceTimeStamp")
        if not ts_raw:
            raise KeyError("Missing required 'timestamp' field in CPRI mock record")

        try:
            dt = pd.to_datetime(ts_raw)
            if dt.tzinfo is None:
                event_time_utc = dt.to_pydatetime().replace(tzinfo=timezone.utc)
            else:
                event_time_utc = dt.to_pydatetime().astimezone(timezone.utc)
        except Exception as exc:
            raise ValueError(f"Failed to parse timestamp '{ts_raw}': {exc}") from exc

        rec_id = source_record_id if source_record_id is not None else str(ts_raw)
        serialized = json.dumps(raw_record, sort_keys=True, default=str).encode("utf-8")
        raw_sha256 = hashlib.sha256(serialized).hexdigest()

        event_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:transformer:cpri:{resolved_asset_id}:{ts_raw}:{rec_id}"))

        source_ref = SourceRef(
            system=self.source_system,
            adapter_id=self.adapter_id,
            source_record_id=str(rec_id),
            source_uri=str(source_uri),
            raw_sha256=raw_sha256,
        )

        measurements: List[Measurement] = []
        unmapped_keys: List[str] = []

        for raw_key, raw_val in raw_record.items():
            if raw_key in ("timestamp", "DeviceTimeStamp", "transformer_id", "asset_id", "DeviceID"):
                continue
            
            clean_key = raw_key.lower().strip()
            if clean_key not in self.CPRI_TAG_MAP:
                unmapped_keys.append(raw_key)
                continue

            tag_info = self.CPRI_TAG_MAP[clean_key]
            canon_name = tag_info["canonical_name"]
            unit_code = canonicalize_unit_code(tag_info["unit"])
            phase = tag_info["phase"]

            if raw_val is None or (isinstance(raw_val, float) and pd.isna(raw_val)):
                continue

            meas = Measurement(
                signal_id=canon_name,
                phase=phase,  # type: ignore[arg-type]
                value=float(raw_val) if tag_info["type"] == "float" else raw_val,
                value_type="float" if tag_info["type"] == "float" else "str",
                unit_ucum=unit_code,
                original_name=raw_key,
                original_value=str(raw_val),
                original_unit=tag_info["unit"],
                quality=MeasurementQuality(
                    severity=QualitySeverity.GOOD,
                    flags=[],
                    source_code="CPRI_TELEMETRY",
                ),
            )
            measurements.append(meas)

        if not measurements:
            raise ValueError(f"No measurements mapped for CPRI record with timestamp '{ts_raw}'")

        quality_flags: List[str] = []

        return CanonicalEvent(
            schema_version="1.0.0",
            event_id=event_uuid,
            asset_id=resolved_asset_id,
            event_time_utc=event_time_utc,
            received_time_utc=None,  # Nullable when no native receive timestamp is present
            source=source_ref,
            measurements=measurements,
            event_quality_flags=quality_flags,
            mapping_version="1.0.0",
        )

    def stream_events(
        self,
        source_input: List[Dict[str, Any]] | Path | str,
        asset_id: str = "CPRI_MOCK_TX_01",
    ) -> Iterator[CanonicalEvent]:
        """Streams CanonicalEvents from a list of CPRI records or JSON fixture file."""
        if isinstance(source_input, (str, Path)):
            p = Path(source_input)
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            records = data.get("records", []) if isinstance(data, dict) else data
            source_uri = str(p)
        elif isinstance(source_input, list):
            records = source_input
            source_uri = "list://in_memory"
        else:
            raise TypeError(f"Unsupported source input type: {type(source_input)}")

        for idx, rec in enumerate(records):
            yield self.transform_record(
                raw_record=rec,
                asset_id=asset_id,
                source_uri=source_uri,
                source_record_id=str(idx),
            )
