"""Tripura CSV Source Adapter.

Phase 2, Substep 2.1 Implementation.
Translates raw Tripura distribution transformer telemetry into immutable long-form
CanonicalEvent instances with complete provenance, UCUM unit validation, and quality metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Literal, Optional
import uuid

import pandas as pd
import yaml

from app.adapters.base import BaseSourceAdapter
from app.core.units import canonicalize_unit_code, validate_unit
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


class TripuraCSVAdapter(BaseSourceAdapter):
    """Canonical source adapter for Tripura telemetry CSVs using tripura_map.yaml."""

    def __init__(
        self,
        mapping_file: Path | str = "backend/app/adapters/tripura_map.yaml",
        adapter_id: str = "tripura_csv_v1",
    ) -> None:
        self._adapter_id = adapter_id
        self._source_system = "tripura_csv"
        self.mapping_file = Path(mapping_file)
        self.mapping_config = self._load_mapping_config()
        self.column_map = self._build_column_index()

    @property
    def adapter_id(self) -> str:
        return self._adapter_id

    @property
    def source_system(self) -> str:
        return self._source_system

    def _load_mapping_config(self) -> Dict[str, Any]:
        """Loads declarative YAML mapping."""
        if not self.mapping_file.exists():
            raise FileNotFoundError(f"Tripura mapping file missing: {self.mapping_file.resolve()}")
        with open(self.mapping_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _build_column_index(self) -> Dict[str, Dict[str, Any]]:
        """Flattens source mappings into a column-keyed lookup index."""
        col_index: Dict[str, Dict[str, Any]] = {}
        sources = self.mapping_config.get("sources", {})
        for src_file, src_info in sources.items():
            mappings = src_info.get("mappings", {})
            for col_name, map_info in mappings.items():
                info = dict(map_info)
                info["source_file"] = src_file
                # Infer electrical phase if not explicitly specified
                if "phase" not in info:
                    info["phase"] = self._infer_phase(col_name)
                col_index[col_name] = info
        return col_index

    @staticmethod
    def _infer_phase(col_name: str) -> Optional[str]:
        """Infers phase association from standard electrical column naming."""
        if col_name.endswith("L1") or col_name in ("VL1", "IL1", "WL1", "VAL1", "RVAL1", "PFL1", "THDVL1", "THDIL1", "MDIL1"):
            return "L1"
        if col_name.endswith("L2") or col_name in ("VL2", "IL2", "WL2", "VAL2", "RVAL2", "PFL2", "THDVL2", "THDIL2", "MDIL2"):
            return "L2"
        if col_name.endswith("L3") or col_name in ("VL3", "IL3", "WL3", "VAL3", "RVAL3", "PFL3", "THDVL3", "THDIL3", "MDIL3"):
            return "L3"
        if col_name in ("VL12", "V12"):
            return "L1_L2"
        if col_name in ("VL23", "V23"):
            return "L2_L3"
        if col_name in ("VL31", "V31"):
            return "L3_L1"
        if col_name in ("INUT", "IN", "I_N"):
            return "N"
        return None

    def transform_record(
        self,
        raw_record: Dict[str, Any],
        asset_id: str = "TRIPURA_DTR_01",
        source_uri: str = "data/tripura_raw",
        source_record_id: Optional[str] = None,
    ) -> CanonicalEvent:
        """Transforms a raw single-row dictionary into a validated CanonicalEvent."""
        ts_col = self.mapping_config.get("timestamp_column", "DeviceTimeStamp")
        if ts_col not in raw_record:
            raise KeyError(f"Missing required timestamp column '{ts_col}' in raw record")

        raw_ts_str = str(raw_record[ts_col])
        try:
            # Parse timestamp to UTC datetime
            dt = pd.to_datetime(raw_ts_str)
            if dt.tzinfo is None:
                event_time_utc = dt.to_pydatetime().replace(tzinfo=timezone.utc)
            else:
                event_time_utc = dt.to_pydatetime().astimezone(timezone.utc)
        except Exception as exc:
            raise ValueError(f"Failed to parse timestamp '{raw_ts_str}': {exc}") from exc

        # Compute deterministic raw sha256 hash
        serialized_raw = json.dumps(raw_record, sort_keys=True, default=str).encode("utf-8")
        raw_sha256 = hashlib.sha256(serialized_raw).hexdigest()

        rec_id = source_record_id if source_record_id is not None else raw_ts_str

        # Deterministic UUIDv5 event ID
        event_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:transformer:tripura:{asset_id}:{raw_ts_str}:{rec_id}"))

        source_ref = SourceRef(
            system=self.source_system,
            adapter_id=self.adapter_id,
            source_record_id=str(rec_id),
            source_uri=str(source_uri),
            raw_sha256=raw_sha256,
        )

        measurements: List[Measurement] = []
        event_flags: List[str] = []

        for col_name, raw_val in raw_record.items():
            if col_name == ts_col or col_name == "ts":
                continue
            if col_name not in self.column_map:
                continue

            map_info = self.column_map[col_name]
            canon_name = map_info["canonical_name"]
            unit_raw = map_info.get("unit", "1")
            canon_unit = canonicalize_unit_code(unit_raw)
            phase = map_info.get("phase")
            status = map_info.get("status", "mapped")

            if raw_val is None or (isinstance(raw_val, float) and pd.isna(raw_val)):
                continue

            # Determine value type and converted value
            dtype_spec = map_info.get("dtype", "float64")
            try:
                if dtype_spec.startswith("int") or isinstance(raw_val, (int, bool)):
                    val: float | int | str | bool = int(raw_val)
                    val_type: Literal["float", "int", "str", "bool"] = "int"
                elif dtype_spec.startswith("float") or isinstance(raw_val, float):
                    val = float(raw_val)
                    val_type = "float"
                else:
                    val = str(raw_val)
                    val_type = "str"
            except (ValueError, TypeError):
                val = str(raw_val)
                val_type = "str"

            # Check quality and physical bounds
            q_severity = QualitySeverity.GOOD
            q_flags: List[str] = []

            if status == "unresolved_channel":
                q_flags.append("UNRESOLVED_CHANNEL")

            bounds = map_info.get("physical_bounds")
            if bounds and isinstance(val, (int, float)):
                min_b, max_b = bounds
                if val < min_b or val > max_b:
                    # Mark out of range
                    q_severity = QualitySeverity.BAD if (val < min_b and min_b >= 0) else QualitySeverity.UNCERTAIN
                    q_flags.append("OUT_OF_RANGE")

            meas = Measurement(
                signal_id=canon_name,
                phase=phase,  # type: ignore[arg-type]
                value=val,
                value_type=val_type,
                unit_ucum=canon_unit,
                original_name=col_name,
                original_value=str(raw_val),
                original_unit=unit_raw,
                quality=MeasurementQuality(
                    severity=q_severity,
                    flags=q_flags,
                    source_code=map_info.get("source_file"),
                ),
            )
            measurements.append(meas)

        if not measurements:
            raise ValueError(f"No valid measurements mapped for record with timestamp '{raw_ts_str}'")

        # Explicitly declare historical source timezone status without fabricating verified timezone
        event_flags_final = list(event_flags)
        if "HISTORICAL_SOURCE_TIMEZONE_UNVERIFIED" not in event_flags_final:
            event_flags_final.append("HISTORICAL_SOURCE_TIMEZONE_UNVERIFIED")

        return CanonicalEvent(
            schema_version="1.0.0",
            event_id=event_uuid,
            asset_id=asset_id,
            event_time_utc=event_time_utc,
            received_time_utc=None,  # Do not fabricate a historical receive timestamp
            source=source_ref,
            measurements=measurements,
            event_quality_flags=event_flags_final,
            mapping_version="1.0.0",
        )

    def stream_events(
        self,
        source_input: pd.DataFrame | List[Dict[str, Any]] | Path | str,
        asset_id: str = "TRIPURA_DTR_01",
    ) -> Iterator[CanonicalEvent]:
        """Streams CanonicalEvents deterministically from DataFrame, list of records, or Parquet/CSV file."""
        if isinstance(source_input, (str, Path)):
            p = Path(source_input)
            if p.suffix == ".parquet":
                df = pd.read_parquet(p)
            else:
                df = pd.read_csv(p)
            source_uri = str(p)
        elif isinstance(source_input, pd.DataFrame):
            df = source_input
            source_uri = "dataframe://in_memory"
        elif isinstance(source_input, list):
            for i, rec in enumerate(source_input):
                yield self.transform_record(
                    raw_record=rec,
                    asset_id=asset_id,
                    source_uri="list://in_memory",
                    source_record_id=str(i),
                )
            return
        else:
            raise TypeError(f"Unsupported source input type: {type(source_input)}")

        for idx, row in df.iterrows():
            rec_dict = row.to_dict()
            yield self.transform_record(
                raw_record=rec_dict,
                asset_id=asset_id,
                source_uri=source_uri,
                source_record_id=str(idx),
            )
