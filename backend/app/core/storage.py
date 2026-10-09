"""Storage Engine & Temporal Query Service (DuckDB + Parquet).

Provides ACID-like local storage semantics, temporal queries, sliding-window
aggregations, union-of-events preservation, and model-specific complete-case
filtering views.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import duckdb
import pandas as pd
import pyarrow as pa

from app.models.features import DerivedFeatures
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    RawTelemetryFrame,
    SourceRef,
)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure a datetime object is timezone-aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    """Convert datetime to naive UTC for DuckDB TIMESTAMP compatibility."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class StorageEngine:
    """High-performance temporal storage and query engine backed by DuckDB and Parquet."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        parquet_dir: Path | str | None = None,
        read_only: bool = False,
    ) -> None:
        """Initialize DuckDB connection and ensure relational schema is created."""
        self.db_path = str(db_path) if db_path and str(db_path) != ":memory:" else ":memory:"
        self.parquet_dir = Path(parquet_dir) if parquet_dir else None
        if self.parquet_dir:
            self.parquet_dir.mkdir(parents=True, exist_ok=True)

        self._con = duckdb.connect(self.db_path, read_only=read_only)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create canonical tables and temporal indexes if they do not exist."""
        self._con.execute("""
        CREATE TABLE IF NOT EXISTS raw_frames (
            raw_id VARCHAR PRIMARY KEY,
            source_system VARCHAR NOT NULL,
            received_time_utc TIMESTAMP NOT NULL,
            raw_payload_json VARCHAR NOT NULL,
            raw_sha256 VARCHAR NOT NULL
        );

        CREATE TABLE IF NOT EXISTS canonical_events (
            event_id VARCHAR PRIMARY KEY,
            asset_id VARCHAR NOT NULL,
            event_time_utc TIMESTAMP NOT NULL,
            received_time_utc TIMESTAMP,
            schema_version VARCHAR NOT NULL,
            mapping_version VARCHAR NOT NULL,
            source_system VARCHAR NOT NULL,
            source_adapter_id VARCHAR NOT NULL,
            source_record_id VARCHAR NOT NULL,
            source_uri VARCHAR NOT NULL,
            source_raw_sha256 VARCHAR NOT NULL,
            event_quality_flags_json VARCHAR NOT NULL,
            ingested_at_utc TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS canonical_measurements (
            event_id VARCHAR NOT NULL,
            asset_id VARCHAR NOT NULL,
            event_time_utc TIMESTAMP NOT NULL,
            signal_id VARCHAR NOT NULL,
            phase VARCHAR,
            value_numeric DOUBLE,
            value_text VARCHAR NOT NULL,
            value_type VARCHAR NOT NULL,
            unit_ucum VARCHAR NOT NULL,
            original_name VARCHAR NOT NULL,
            original_value VARCHAR NOT NULL,
            original_unit VARCHAR NOT NULL,
            quality_severity VARCHAR NOT NULL,
            quality_flags_json VARCHAR NOT NULL,
            quality_source_code VARCHAR
        );

        CREATE TABLE IF NOT EXISTS derived_features (
            timestamp_utc TIMESTAMP PRIMARY KEY,
            apparent_power_derived_kva DOUBLE,
            power_factor_derived DOUBLE,
            current_mean_a DOUBLE,
            current_magnitude_imbalance_pct DOUBLE,
            voltage_magnitude_imbalance_pct DOUBLE,
            neutral_current_ratio DOUBLE,
            pqs_inconsistency DOUBLE,
            relative_load_index DOUBLE,
            thermal_residual_degc DOUBLE,
            transform_version VARCHAR NOT NULL
        );

        CREATE TABLE IF NOT EXISTS twin_checkpoints (
            checkpoint_id VARCHAR PRIMARY KEY,
            asset_id VARCHAR NOT NULL,
            state_time_utc TIMESTAMP NOT NULL,
            last_processed_event_id VARCHAR NOT NULL,
            state_sequence BIGINT NOT NULL,
            state_json VARCHAR NOT NULL,
            state_hash VARCHAR NOT NULL,
            created_at_utc TIMESTAMP NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_events_asset_time ON canonical_events(asset_id, event_time_utc);
        CREATE INDEX IF NOT EXISTS idx_meas_asset_sig_time ON canonical_measurements(asset_id, signal_id, event_time_utc);
        CREATE INDEX IF NOT EXISTS idx_meas_event_id ON canonical_measurements(event_id);
        CREATE INDEX IF NOT EXISTS idx_checkpoints_asset_time ON twin_checkpoints(asset_id, state_time_utc DESC);
        """)

    def insert_raw_frames(self, frames: Sequence[RawTelemetryFrame]) -> int:
        """Insert a batch of raw telemetry frames."""
        if not frames:
            return 0

        raw_ids = [f.raw_id for f in frames]
        source_systems = [f.source_system for f in frames]
        received_times = [_to_naive_utc(f.received_time_utc) for f in frames]
        payloads = [json.dumps(f.raw_payload, ensure_ascii=False) for f in frames]
        hashes = [f.raw_sha256 for f in frames]

        tbl = pa.table({
            "raw_id": raw_ids,
            "source_system": source_systems,
            "received_time_utc": pa.array(received_times, type=pa.timestamp("us")),
            "raw_payload_json": payloads,
            "raw_sha256": hashes,
        })

        self._con.register("_temp_raw_frames", tbl)
        self._con.execute("INSERT OR REPLACE INTO raw_frames SELECT * FROM _temp_raw_frames")
        self._con.unregister("_temp_raw_frames")
        return len(frames)

    def insert_canonical_events(self, events: Sequence[CanonicalEvent]) -> int:
        """Insert a batch of CanonicalEvents and their measurements.

        Preserves the complete union of events and individual measurement records
        with full provenance and quality metadata.
        """
        if not events:
            return 0

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        event_ids: list[str] = []
        asset_ids: list[str] = []
        event_times: list[datetime] = []
        received_times: list[datetime | None] = []
        schema_versions: list[str] = []
        mapping_versions: list[str] = []
        source_systems: list[str] = []
        source_adapters: list[str] = []
        source_records: list[str] = []
        source_uris: list[str] = []
        source_hashes: list[str] = []
        event_flags: list[str] = []
        ingested_ats: list[datetime] = []

        m_event_ids: list[str] = []
        m_asset_ids: list[str] = []
        m_event_times: list[datetime] = []
        m_signal_ids: list[str] = []
        m_phases: list[str | None] = []
        m_values_num: list[float | None] = []
        m_values_text: list[str] = []
        m_value_types: list[str] = []
        m_units: list[str] = []
        m_orig_names: list[str] = []
        m_orig_values: list[str] = []
        m_orig_units: list[str] = []
        m_severities: list[str] = []
        m_flags: list[str] = []
        m_source_codes: list[str | None] = []

        for ev in events:
            ev_time_naive = _to_naive_utc(ev.event_time_utc)
            assert ev_time_naive is not None
            rx_time_naive = _to_naive_utc(ev.received_time_utc)

            event_ids.append(ev.event_id)
            asset_ids.append(ev.asset_id)
            event_times.append(ev_time_naive)
            received_times.append(rx_time_naive)
            schema_versions.append(ev.schema_version)
            mapping_versions.append(ev.mapping_version)
            source_systems.append(ev.source.system)
            source_adapters.append(ev.source.adapter_id)
            source_records.append(ev.source.source_record_id)
            source_uris.append(ev.source.source_uri)
            source_hashes.append(ev.source.raw_sha256)
            event_flags.append(json.dumps(ev.event_quality_flags))
            ingested_ats.append(now_utc)

            for m in ev.measurements:
                m_event_ids.append(ev.event_id)
                m_asset_ids.append(ev.asset_id)
                m_event_times.append(ev_time_naive)
                m_signal_ids.append(m.signal_id)
                m_phases.append(m.phase)

                # Convert numeric value where applicable
                if isinstance(m.value, (int, float)) and not isinstance(m.value, bool):
                    m_values_num.append(float(m.value))
                elif isinstance(m.value, bool):
                    m_values_num.append(1.0 if m.value else 0.0)
                else:
                    m_values_num.append(None)

                m_values_text.append(str(m.value))
                m_value_types.append(m.value_type)
                m_units.append(m.unit_ucum)
                m_orig_names.append(m.original_name)
                m_orig_values.append(m.original_value)
                m_orig_units.append(m.original_unit)
                m_severities.append(m.quality.severity.value)
                m_flags.append(json.dumps(m.quality.flags))
                m_source_codes.append(m.quality.source_code)

        # PyArrow table for canonical_events
        events_tbl = pa.table({
            "event_id": event_ids,
            "asset_id": asset_ids,
            "event_time_utc": pa.array(event_times, type=pa.timestamp("us")),
            "received_time_utc": pa.array(received_times, type=pa.timestamp("us")),
            "schema_version": schema_versions,
            "mapping_version": mapping_versions,
            "source_system": source_systems,
            "source_adapter_id": source_adapters,
            "source_record_id": source_records,
            "source_uri": source_uris,
            "source_raw_sha256": source_hashes,
            "event_quality_flags_json": event_flags,
            "ingested_at_utc": pa.array(ingested_ats, type=pa.timestamp("us")),
        })

        # PyArrow table for canonical_measurements
        meas_tbl = pa.table({
            "event_id": m_event_ids,
            "asset_id": m_asset_ids,
            "event_time_utc": pa.array(m_event_times, type=pa.timestamp("us")),
            "signal_id": m_signal_ids,
            "phase": m_phases,
            "value_numeric": m_values_num,
            "value_text": m_values_text,
            "value_type": m_value_types,
            "unit_ucum": m_units,
            "original_name": m_orig_names,
            "original_value": m_orig_values,
            "original_unit": m_orig_units,
            "quality_severity": m_severities,
            "quality_flags_json": m_flags,
            "quality_source_code": m_source_codes,
        })

        self._con.begin()
        try:
            self._con.register("_temp_events", events_tbl)
            self._con.execute("INSERT OR REPLACE INTO canonical_events SELECT * FROM _temp_events")
            self._con.unregister("_temp_events")

            # Remove existing measurements for these event_ids before inserting new ones to ensure idempotency
            id_list_str = ", ".join(f"'{eid}'" for eid in set(event_ids))
            self._con.execute(f"DELETE FROM canonical_measurements WHERE event_id IN ({id_list_str})")

            self._con.register("_temp_measurements", meas_tbl)
            self._con.execute("INSERT INTO canonical_measurements SELECT * FROM _temp_measurements")
            self._con.unregister("_temp_measurements")
            self._con.commit()
        except Exception:
            self._con.rollback()
            raise

        return len(events)

    def insert_derived_features(self, features: Sequence[DerivedFeatures]) -> int:
        """Insert a batch of derived features."""
        if not features:
            return 0

        ts_list = [_to_naive_utc(f.timestamp_utc) for f in features]
        s_list = [f.apparent_power_derived_kva for f in features]
        pf_list = [f.power_factor_derived for f in features]
        imean_list = [f.current_mean_a for f in features]
        iub_list = [f.current_magnitude_imbalance_pct for f in features]
        vub_list = [f.voltage_magnitude_imbalance_pct for f in features]
        in_ratio_list = [f.neutral_current_ratio for f in features]
        pqs_list = [f.pqs_inconsistency for f in features]
        u_list = [f.relative_load_index for f in features]
        residual_list = [f.thermal_residual_degc for f in features]
        v_list = [f.transform_version for f in features]

        tbl = pa.table({
            "timestamp_utc": pa.array(ts_list, type=pa.timestamp("us")),
            "apparent_power_derived_kva": s_list,
            "power_factor_derived": pf_list,
            "current_mean_a": imean_list,
            "current_magnitude_imbalance_pct": iub_list,
            "voltage_magnitude_imbalance_pct": vub_list,
            "neutral_current_ratio": in_ratio_list,
            "pqs_inconsistency": pqs_list,
            "relative_load_index": u_list,
            "thermal_residual_degc": residual_list,
            "transform_version": v_list,
        })

        self._con.register("_temp_features", tbl)
        self._con.execute("INSERT OR REPLACE INTO derived_features SELECT * FROM _temp_features")
        self._con.unregister("_temp_features")
        return len(features)

    def get_canonical_events(
        self,
        asset_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
        offset: int = 0,
        order_asc: bool = True,
    ) -> list[CanonicalEvent]:
        """Query canonical events and reconstruct complete typed CanonicalEvent models."""
        where_clauses = ["asset_id = ?"]
        params: list[Any] = [asset_id]

        if start_time is not None:
            where_clauses.append("event_time_utc >= ?")
            params.append(_to_naive_utc(start_time))
        if end_time is not None:
            where_clauses.append("event_time_utc <= ?")
            params.append(_to_naive_utc(end_time))

        where_sql = " AND ".join(where_clauses)
        order_dir = "ASC" if order_asc else "DESC"
        limit_sql = f"LIMIT {limit}" if limit is not None else ""
        offset_sql = f"OFFSET {offset}" if offset > 0 else ""

        query = f"""
        SELECT
            event_id,
            asset_id,
            event_time_utc,
            received_time_utc,
            schema_version,
            mapping_version,
            source_system,
            source_adapter_id,
            source_record_id,
            source_uri,
            source_raw_sha256,
            event_quality_flags_json
        FROM canonical_events
        WHERE {where_sql}
        ORDER BY event_time_utc {order_dir}, event_id {order_dir}
        {limit_sql} {offset_sql}
        """

        event_rows = self._con.execute(query, params).fetchall()
        if not event_rows:
            return []

        event_ids = [r[0] for r in event_rows]
        id_list_str = ", ".join(f"'{eid}'" for eid in event_ids)

        meas_query = f"""
        SELECT
            event_id,
            signal_id,
            phase,
            value_numeric,
            value_text,
            value_type,
            unit_ucum,
            original_name,
            original_value,
            original_unit,
            quality_severity,
            quality_flags_json,
            quality_source_code
        FROM canonical_measurements
        WHERE event_id IN ({id_list_str})
        ORDER BY signal_id ASC, phase ASC
        """
        meas_rows = self._con.execute(meas_query).fetchall()

        # Group measurements by event_id
        meas_by_event: dict[str, list[Measurement]] = {eid: [] for eid in event_ids}
        for mr in meas_rows:
            (
                eid,
                sig_id,
                phase,
                val_num,
                val_txt,
                val_type,
                unit,
                orig_name,
                orig_val,
                orig_unit,
                severity,
                flags_json,
                src_code,
            ) = mr

            # Reconstruct typed value
            if val_type == "float":
                typed_val: float | int | str | bool = float(val_num) if val_num is not None else float(val_txt)
            elif val_type == "int":
                typed_val = int(round(val_num)) if val_num is not None else int(val_txt)
            elif val_type == "bool":
                typed_val = bool(val_num) if val_num is not None else (val_txt.lower() in ("true", "1"))
            else:
                typed_val = str(val_txt)

            quality = MeasurementQuality(
                severity=QualitySeverity(severity),
                flags=json.loads(flags_json),
                source_code=src_code,
            )

            m = Measurement(
                signal_id=sig_id,
                phase=phase,
                value=typed_val,
                value_type=val_type,
                unit_ucum=unit,
                original_name=orig_name,
                original_value=orig_val,
                original_unit=orig_unit,
                quality=quality,
            )
            meas_by_event[eid].append(m)

        # Assemble CanonicalEvents
        events: list[CanonicalEvent] = []
        for r in event_rows:
            (
                eid,
                aid,
                ev_time,
                rx_time,
                s_ver,
                m_ver,
                src_sys,
                src_adap,
                src_rec,
                src_uri,
                src_sha,
                ev_flags_json,
            ) = r

            ev = CanonicalEvent(
                schema_version=s_ver,
                event_id=eid,
                asset_id=aid,
                event_time_utc=_ensure_utc(ev_time),  # type: ignore[arg-type]
                received_time_utc=_ensure_utc(rx_time),
                source=SourceRef(
                    system=src_sys,
                    adapter_id=src_adap,
                    source_record_id=src_rec,
                    source_uri=src_uri,
                    raw_sha256=src_sha,
                ),
                measurements=meas_by_event.get(eid, []),
                event_quality_flags=json.loads(ev_flags_json),
                mapping_version=m_ver,
            )
            events.append(ev)

        return events

    def get_canonical_event_by_id(self, event_id: str) -> CanonicalEvent | None:
        """Fetch a single CanonicalEvent by its unique event ID."""
        rows = self._con.execute(
            "SELECT asset_id FROM canonical_events WHERE event_id = ?",
            [event_id],
        ).fetchall()
        if not rows:
            return None
        events = self.get_canonical_events(asset_id=rows[0][0], limit=1000, offset=0)
        for ev in events:
            if ev.event_id == event_id:
                return ev
        return None

    def get_measurements_df(
        self,
        asset_id: str,
        signal_ids: Sequence[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        phase: str | None = None,
        quality_severity: str | None = None,
    ) -> pd.DataFrame:
        """Fetch measurement records as a pandas DataFrame."""
        where_clauses = ["asset_id = ?"]
        params: list[Any] = [asset_id]

        if signal_ids:
            placeholders = ", ".join(["?"] * len(signal_ids))
            where_clauses.append(f"signal_id IN ({placeholders})")
            params.extend(signal_ids)

        if start_time is not None:
            where_clauses.append("event_time_utc >= ?")
            params.append(_to_naive_utc(start_time))

        if end_time is not None:
            where_clauses.append("event_time_utc <= ?")
            params.append(_to_naive_utc(end_time))

        if phase is not None:
            where_clauses.append("phase = ?")
            params.append(phase)

        if quality_severity is not None:
            where_clauses.append("quality_severity = ?")
            params.append(quality_severity)

        where_sql = " AND ".join(where_clauses)
        query = f"""
        SELECT
            event_id,
            asset_id,
            event_time_utc,
            signal_id,
            phase,
            value_numeric,
            value_text,
            value_type,
            unit_ucum,
            quality_severity,
            quality_flags_json
        FROM canonical_measurements
        WHERE {where_sql}
        ORDER BY event_time_utc ASC, signal_id ASC, phase ASC
        """
        df = self._con.execute(query, params).df()
        if not df.empty:
            df["event_time_utc"] = pd.to_datetime(df["event_time_utc"], utc=True)
        return df

    def get_sliding_window_aggregates(
        self,
        asset_id: str,
        signal_id: str,
        window_interval: str = "15 minutes",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        phase: str | None = None,
    ) -> pd.DataFrame:
        """Compute sliding/tumbling window aggregates (min, max, mean, std, count)."""
        where_clauses = [
            "asset_id = ?",
            "signal_id = ?",
            "value_numeric IS NOT NULL",
            "quality_severity != 'BAD'",
        ]
        params: list[Any] = [asset_id, signal_id]

        if start_time is not None:
            where_clauses.append("event_time_utc >= ?")
            params.append(_to_naive_utc(start_time))

        if end_time is not None:
            where_clauses.append("event_time_utc <= ?")
            params.append(_to_naive_utc(end_time))

        if phase is not None:
            where_clauses.append("phase = ?")
            params.append(phase)

        where_sql = " AND ".join(where_clauses)
        query = f"""
        SELECT
            time_bucket(INTERVAL '{window_interval}', event_time_utc) AS window_start,
            count(value_numeric) AS sample_count,
            min(value_numeric) AS min_value,
            max(value_numeric) AS max_value,
            avg(value_numeric) AS mean_value,
            stddev_samp(value_numeric) AS std_value
        FROM canonical_measurements
        WHERE {where_sql}
        GROUP BY window_start
        ORDER BY window_start ASC
        """
        df = self._con.execute(query, params).df()
        if not df.empty:
            df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
        return df

    def get_complete_case_matrix(
        self,
        asset_id: str,
        required_signals: Sequence[str],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        accepted_severities: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Model-Specific Complete-Case Analytical View.

        Retrieves tabular data where all specified `required_signals` are present
        and valid for each observation timestamp. Missing unrelated signals do not
        cause timestamps to be dropped, adhering strictly to the union-of-events storage
        and model-specific complete-case filtering principle.
        """
        if not required_signals:
            return pd.DataFrame()

        if accepted_severities is None:
            accepted_severities = ["GOOD", "UNCERTAIN"]

        where_clauses = [
            "asset_id = ?",
            f"signal_id IN ({', '.join(['?'] * len(required_signals))})",
            f"quality_severity IN ({', '.join(['?'] * len(accepted_severities))})",
            "value_numeric IS NOT NULL",
        ]
        params: list[Any] = [asset_id]
        params.extend(required_signals)
        params.extend(accepted_severities)

        if start_time is not None:
            where_clauses.append("event_time_utc >= ?")
            params.append(_to_naive_utc(start_time))

        if end_time is not None:
            where_clauses.append("event_time_utc <= ?")
            params.append(_to_naive_utc(end_time))

        where_sql = " AND ".join(where_clauses)

        # Dynamic pivot query
        pivot_cols = [
            f"max(CASE WHEN signal_id = '{sig}' THEN value_numeric END) AS \"{sig}\""
            for sig in required_signals
        ]
        having_clause = " AND ".join([f"max(CASE WHEN signal_id = '{sig}' THEN value_numeric END) IS NOT NULL" for sig in required_signals])

        query = f"""
        SELECT
            event_time_utc,
            {', '.join(pivot_cols)}
        FROM canonical_measurements
        WHERE {where_sql}
        GROUP BY event_time_utc
        HAVING {having_clause}
        ORDER BY event_time_utc ASC
        """
        df = self._con.execute(query, params).df()
        if not df.empty:
            df["event_time_utc"] = pd.to_datetime(df["event_time_utc"], utc=True)
        return df

    def get_derived_features_df(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> pd.DataFrame:
        """Query derived features as a pandas DataFrame."""
        where_clauses: list[str] = []
        params: list[Any] = []

        if start_time is not None:
            where_clauses.append("timestamp_utc >= ?")
            params.append(_to_naive_utc(start_time))

        if end_time is not None:
            where_clauses.append("timestamp_utc <= ?")
            params.append(_to_naive_utc(end_time))

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"""
        SELECT * FROM derived_features
        {where_sql}
        ORDER BY timestamp_utc ASC
        """
        df = self._con.execute(query, params).df()
        if not df.empty:
            df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        return df

    def get_event_count(self, asset_id: str | None = None) -> int:
        """Get total number of canonical events in storage."""
        if asset_id:
            res = self._con.execute(
                "SELECT count(*) FROM canonical_events WHERE asset_id = ?",
                [asset_id],
            ).fetchone()
        else:
            res = self._con.execute("SELECT count(*) FROM canonical_events").fetchone()
        return int(res[0]) if res else 0

    def get_measurement_count(self, asset_id: str | None = None) -> int:
        """Get total number of canonical measurements in storage."""
        if asset_id:
            res = self._con.execute(
                "SELECT count(*) FROM canonical_measurements WHERE asset_id = ?",
                [asset_id],
            ).fetchone()
        else:
            res = self._con.execute("SELECT count(*) FROM canonical_measurements").fetchone()
        return int(res[0]) if res else 0

    def get_time_bounds(self, asset_id: str) -> tuple[datetime | None, datetime | None]:
        """Get the earliest and latest event_time_utc for an asset."""
        res = self._con.execute(
            "SELECT min(event_time_utc), max(event_time_utc) FROM canonical_events WHERE asset_id = ?",
            [asset_id],
        ).fetchone()
        if not res or res[0] is None:
            return None, None
        return _ensure_utc(res[0]), _ensure_utc(res[1])

    def export_table_to_parquet(self, table_name: str, output_path: Path | str) -> Path:
        """Export an entire table directly to an optimized Parquet file."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out_str = str(out).replace("\\", "/")
        self._con.execute(f"COPY {table_name} TO '{out_str}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        return out

    def import_from_parquet(self, table_name: str, input_path: Path | str) -> int:
        """Import records from a Parquet file into a specified table."""
        in_path = Path(input_path)
        if not in_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {in_path}")
        in_str = str(in_path).replace("\\", "/")
        res = self._con.execute(f"INSERT INTO {table_name} SELECT * FROM read_parquet('{in_str}')")
        count = self._con.execute(f"SELECT count(*) FROM {table_name}").fetchone()
        return int(count[0]) if count else 0

    def insert_checkpoint(
        self,
        checkpoint_id: str,
        asset_id: str,
        state_time_utc: datetime,
        last_processed_event_id: str,
        state_sequence: int,
        state_json: str,
        state_hash: str,
        created_at_utc: datetime | None = None,
    ) -> None:
        """Insert a twin state checkpoint record."""
        now_naive = _to_naive_utc(created_at_utc or datetime.now(timezone.utc))
        state_time_naive = _to_naive_utc(state_time_utc)
        self._con.execute(
            """
            INSERT OR REPLACE INTO twin_checkpoints
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                checkpoint_id,
                asset_id,
                state_time_naive,
                last_processed_event_id,
                state_sequence,
                state_json,
                state_hash,
                now_naive,
            ],
        )

    def get_latest_checkpoint(self, asset_id: str) -> dict[str, Any] | None:
        """Get the most recent checkpoint record for an asset."""
        res = self._con.execute(
            """
            SELECT
                checkpoint_id,
                asset_id,
                state_time_utc,
                last_processed_event_id,
                state_sequence,
                state_json,
                state_hash,
                created_at_utc
            FROM twin_checkpoints
            WHERE asset_id = ?
            ORDER BY state_sequence DESC, state_time_utc DESC
            LIMIT 1
            """,
            [asset_id],
        ).fetchone()
        if not res:
            return None
        return {
            "checkpoint_id": res[0],
            "asset_id": res[1],
            "state_time_utc": _ensure_utc(res[2]),
            "last_processed_event_id": res[3],
            "state_sequence": res[4],
            "state_json": res[5],
            "state_hash": res[6],
            "created_at_utc": _ensure_utc(res[7]),
        }

    def get_checkpoint_by_id(self, checkpoint_id: str) -> dict[str, Any] | None:
        """Get a specific checkpoint record by ID."""
        res = self._con.execute(
            """
            SELECT
                checkpoint_id,
                asset_id,
                state_time_utc,
                last_processed_event_id,
                state_sequence,
                state_json,
                state_hash,
                created_at_utc
            FROM twin_checkpoints
            WHERE checkpoint_id = ?
            """,
            [checkpoint_id],
        ).fetchone()
        if not res:
            return None
        return {
            "checkpoint_id": res[0],
            "asset_id": res[1],
            "state_time_utc": _ensure_utc(res[2]),
            "last_processed_event_id": res[3],
            "state_sequence": res[4],
            "state_json": res[5],
            "state_hash": res[6],
            "created_at_utc": _ensure_utc(res[7]),
        }

    def get_checkpoint_count(self, asset_id: str | None = None) -> int:
        """Get total count of saved checkpoints."""
        if asset_id:
            res = self._con.execute("SELECT count(*) FROM twin_checkpoints WHERE asset_id = ?", [asset_id]).fetchone()
        else:
            res = self._con.execute("SELECT count(*) FROM twin_checkpoints").fetchone()
        return int(res[0]) if res else 0
    def get_checkpoints(self, asset_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Return a list of checkpoint metadata (id, asset, timestamp, sequence, hash, created_at).
        If asset_id is provided, filter to that asset.
        """
        query = """
            SELECT
                checkpoint_id,
                asset_id,
                state_time_utc,
                last_processed_event_id,
                state_sequence,
                state_hash,
                created_at_utc
            FROM twin_checkpoints
        """
        params: list[Any] = []
        if asset_id:
            query += " WHERE asset_id = ?"
            params.append(asset_id)
        query += f" ORDER BY state_sequence DESC, state_time_utc DESC LIMIT {int(limit)}"
        rows = self._con.execute(query, params).fetchall()
        result: list[dict[str, Any]] = []
        for r in rows:
            result.append({
                "checkpoint_id": r[0],
                "asset_id": r[1],
                "state_time_utc": _ensure_utc(r[2]),
                "last_processed_event_id": r[3],
                "state_sequence": r[4],
                "state_hash": r[5],
                "created_at_utc": _ensure_utc(r[6]),
            })
        return result

    def close(self) -> None:
        """Close database connection."""
        self._con.close()

    def __enter__(self) -> StorageEngine:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

