"""Structured JSON and CSV Report Exporters (Phase 9.2).

Provides deterministic serialization of authoritative ReportData instances
and historical temporal telemetry for machine-readable audit and engineering consumption.

Zero Metric Recalculation: All serialized values originate strictly from ReportData,
FactBundle, and authoritative StorageEngine events.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Sequence

from app.models.telemetry import CanonicalEvent
from app.reports.report_generator import ReportData


def export_report_json(report_data: ReportData) -> str:
    """Serialize complete authoritative ReportData to a deterministic JSON string.
    
    Guarantees:
    - Zero recalculation of metrics
    - Stable sorted key ordering
    - Strict preservation of null/None fields
    - Full provenance and hash fidelity
    
    Args:
        report_data: Authoritative ReportData instance.
        
    Returns:
        str: Deterministic formatted JSON string.
    """
    raw_dict = report_data.model_dump(mode="json")
    return json.dumps(raw_dict, indent=2, sort_keys=True)


def _format_val(val: Any) -> str:
    """Helper to format nullable primitive values deterministically for CSV."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, float):
        # Format cleanly without trailing .0 if integer-equivalent or standard precision
        return f"{val:.4f}".rstrip("0").rstrip(".") if abs(val) < 1e6 else str(val)
    return str(val)


def export_report_csv(
    report_data: ReportData,
    historical_events: Sequence[CanonicalEvent] | None = None,
) -> str:
    """Serialize ReportData and historical telemetry events to a deterministic CSV document.
    
    Guarantees:
    - Deterministic section and column order
    - Historical time-series telemetry reconstruction without metric recalculation
    - Direct extraction of active anomaly episodes and maintenance advisories
    - Preserves nulls as empty CSV cells
    - Lineage and provenance preservation
    
    Args:
        report_data: Authoritative ReportData instance.
        historical_events: Optional list of chronological historical CanonicalEvents from storage.
        
    Returns:
        str: Deterministic CSV string.
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    # =========================================================================
    # Section 1: Report Metadata & Provenance Header
    # =========================================================================
    writer.writerow(["# SECTION: METADATA_AND_PROVENANCE"])
    meta_headers = [
        "report_id",
        "asset_id",
        "schema_version",
        "generator_version",
        "generated_at_utc",
        "state_time_utc",
        "event_time_watermark_utc",
        "fact_bundle_id",
        "bundle_version",
        "othi_score",
        "health_status",
        "evidence_grade",
        "highest_tier",
        "state_sequence",
        "last_processed_event_id",
        "state_hash",
        "provenance_hash",
    ]
    writer.writerow(meta_headers)

    meta_row = [
        report_data.metadata.report_id,
        report_data.asset.asset_id,
        report_data.metadata.schema_version,
        report_data.metadata.generator_version,
        report_data.metadata.generated_at_utc.isoformat(),
        report_data.timestamps.state_time_utc.isoformat(),
        report_data.timestamps.event_time_watermark_utc.isoformat(),
        report_data.metadata.fact_bundle_id,
        report_data.metadata.bundle_version,
        _format_val(report_data.health.othi_score),
        report_data.health.status.value if report_data.health.status else "",
        report_data.health.evidence_grade.value,
        report_data.capabilities.highest_tier.value,
        str(report_data.state_sequence),
        report_data.last_processed_event_id,
        report_data.state_hash,
        report_data.provenance_hash,
    ]
    writer.writerow(meta_row)
    writer.writerow([])

    # =========================================================================
    # Section 2: Time Series Telemetry (Historical & Current State Snapshot)
    # =========================================================================
    writer.writerow(["# SECTION: TIME_SERIES_TELEMETRY"])
    ts_headers = [
        "timestamp_utc",
        "asset_id",
        "record_type",
        "event_id",
        "top_oil_degc",
        "top_oil_expected_degc",
        "thermal_residual_degc",
        "ambient_degc",
        "active_power_w",
        "reactive_power_var",
        "apparent_power_kva",
        "power_factor",
        "frequency_hz",
        "current_l1_a",
        "current_l2_a",
        "current_l3_a",
        "current_mean_a",
        "current_magnitude_imbalance_pct",
        "voltage_l1_n_v",
        "voltage_l2_n_v",
        "voltage_l3_n_v",
        "voltage_magnitude_imbalance_pct",
        "neutral_current_a",
        "neutral_current_ratio",
        "relative_load_index",
        "source_system",
        "source_adapter_id",
        "source_record_id",
        "source_raw_sha256",
    ]
    writer.writerow(ts_headers)

    # 2A. Write historical events if available
    if historical_events:
        for ev in historical_events:
            meas_map: dict[str, Any] = {m.signal_id: m.value for m in ev.measurements}

            row = [
                ev.event_time_utc.isoformat(),
                ev.asset_id,
                "HISTORICAL_EVENT",
                ev.event_id,
                _format_val(meas_map.get("top_oil_temperature")),
                "",  # Historical raw events do not contain ODE latent state unless computed
                "",  # Residual uncomputed in raw historical frame
                _format_val(meas_map.get("ambient_temperature")),
                _format_val(meas_map.get("active_power_total_w")),
                _format_val(meas_map.get("reactive_power_total_var")),
                "",
                "",
                _format_val(meas_map.get("frequency_hz")),
                _format_val(meas_map.get("current_l1")),
                _format_val(meas_map.get("current_l2")),
                _format_val(meas_map.get("current_l3")),
                "",
                "",
                _format_val(meas_map.get("voltage_l1_n")),
                _format_val(meas_map.get("voltage_l2_n")),
                _format_val(meas_map.get("voltage_l3_n")),
                "",
                _format_val(meas_map.get("neutral_current")),
                "",
                "",
                ev.source.system,
                ev.source.adapter_id,
                ev.source.source_record_id,
                ev.source.raw_sha256,
            ]
            writer.writerow(row)

    # 2B. Write current snapshot row directly from ReportData
    curr_obs = report_data.current_observations
    obs_map: dict[str, Any] = {k: v.value for k, v in curr_obs.items()}
    el = report_data.electrical

    current_snapshot_row = [
        report_data.timestamps.state_time_utc.isoformat(),
        report_data.asset.asset_id,
        "CURRENT_STATE_SNAPSHOT",
        report_data.last_processed_event_id,
        _format_val(report_data.thermal.top_oil_observed_degc),
        _format_val(report_data.thermal.top_oil_expected_degc),
        _format_val(report_data.thermal.thermal_residual_degc),
        _format_val(obs_map.get("ambient_temperature")),
        _format_val(obs_map.get("active_power_total_w")),
        _format_val(obs_map.get("reactive_power_total_var")),
        _format_val(el.apparent_power_derived_kva if el else None),
        _format_val(el.power_factor_derived if el else None),
        _format_val(obs_map.get("frequency_hz")),
        _format_val(obs_map.get("current_l1")),
        _format_val(obs_map.get("current_l2")),
        _format_val(obs_map.get("current_l3")),
        _format_val(el.current_mean_a if el else None),
        _format_val(el.current_magnitude_imbalance_pct if el else None),
        _format_val(obs_map.get("voltage_l1_n")),
        _format_val(obs_map.get("voltage_l2_n")),
        _format_val(obs_map.get("voltage_l3_n")),
        _format_val(el.voltage_magnitude_imbalance_pct if el else None),
        _format_val(obs_map.get("neutral_current")),
        _format_val(el.neutral_current_ratio if el else None),
        _format_val(el.relative_load_index if el else None),
        "TWIN_STATE",
        "REPORT_GENERATOR",
        report_data.metadata.fact_bundle_id,
        report_data.provenance_hash,
    ]
    writer.writerow(current_snapshot_row)
    writer.writerow([])

    # =========================================================================
    # Section 3: Anomaly Event Log
    # =========================================================================
    writer.writerow(["# SECTION: ANOMALY_EPISODES"])
    ep_headers = [
        "episode_id",
        "asset_id",
        "start_time_utc",
        "last_seen_time_utc",
        "state",
        "category",
        "severity_score",
        "is_monitoring_gap",
        "primary_reason",
        "evidence_ids",
        "hypothesis_codes",
    ]
    writer.writerow(ep_headers)

    for ep in report_data.open_episodes:
        ep_row = [
            ep.episode_id,
            ep.asset_id,
            ep.start_time_utc.isoformat(),
            ep.last_seen_time_utc.isoformat(),
            ep.state.value,
            ep.category.value,
            _format_val(ep.severity_score),
            _format_val(ep.is_monitoring_gap),
            ep.primary_reason,
            ";".join(ep.evidence_ids),
            ";".join(ep.hypothesis_codes),
        ]
        writer.writerow(ep_row)
    writer.writerow([])

    # =========================================================================
    # Section 4: Maintenance Recommendations
    # =========================================================================
    writer.writerow(["# SECTION: MAINTENANCE_RECOMMENDATIONS"])
    rec_headers = [
        "recommendation_id",
        "rule_id",
        "rule_version",
        "title",
        "priority",
        "priority_label",
        "action_window",
        "window_provenance_type",
        "advisory_wording",
        "rationale",
        "source_reference",
        "merge_key",
        "acknowledged",
        "created_at_utc",
    ]
    writer.writerow(rec_headers)

    for rec in report_data.active_recommendations:
        rec_row = [
            rec.recommendation_id,
            rec.rule_id,
            rec.rule_version,
            rec.title,
            rec.priority.value,
            rec.priority_label,
            rec.action_window.value,
            rec.window_provenance_type.value,
            rec.advisory_wording,
            rec.rationale,
            rec.source_reference,
            rec.merge_key,
            _format_val(rec.acknowledged),
            rec.created_at_utc.isoformat(),
        ]
        writer.writerow(rec_row)

    return output.getvalue()


__all__ = [
    "export_report_json",
    "export_report_csv",
]
