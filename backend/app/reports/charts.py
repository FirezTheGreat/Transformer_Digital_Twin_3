"""Historical Trend Chart Generator for PDF Reports (Phase 9.3).

Generates deterministic, high-resolution engineering figures using Matplotlib
(Agg headless backend) and encodes them as base64 data URIs for embedding in HTML/PDF.

Zero Metric Recalculation: Visualizes strictly authoritative historical CanonicalEvent
observations and timestamps without synthetic smoothing or interpolation.
"""

from __future__ import annotations

import base64
import io
from datetime import datetime
from typing import Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from app.models.telemetry import CanonicalEvent


def _fig_to_base64(fig: plt.Figure) -> str:
    """Convert Matplotlib figure to base64 PNG data URI string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def generate_thermal_trend_chart(events: Sequence[CanonicalEvent]) -> str | None:
    """Generate top-oil and ambient temperature historical trend chart."""
    if not events:
        return None

    times: list[datetime] = []
    top_oil_vals: list[float] = []
    amb_vals: list[float] = []

    for ev in events:
        meas_map = {m.signal_id: m.value for m in ev.measurements}
        to = meas_map.get("top_oil_temperature")
        ta = meas_map.get("ambient_temperature")
        if isinstance(to, (int, float)):
            times.append(ev.event_time_utc)
            top_oil_vals.append(float(to))
            amb_vals.append(float(ta) if isinstance(ta, (int, float)) else float("nan"))

    if not times:
        return None

    fig, ax = plt.subplots(figsize=(7.5, 2.8), dpi=150)
    ax.plot(times, top_oil_vals, label="Observed Top-Oil (°C)", color="#d97706", linewidth=1.5)
    if any(not (v != v) for v in amb_vals):  # not all nan
        ax.plot(times, amb_vals, label="Ambient Temperature (°C)", color="#0284c7", linewidth=1.2, linestyle="--")

    ax.set_title("Thermal Trajectory · Top-Oil & Ambient Temperature", fontsize=10, fontweight="bold", color="#0e1824", pad=8)
    ax.set_ylabel("Temperature (°C)", fontsize=8, color="#354e6b")
    ax.grid(True, linestyle=":", alpha=0.6, color="#cbdff0")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.tick_params(axis="both", labelsize=7.5, colors="#354e6b")
    ax.legend(loc="upper left", fontsize=7.5, framealpha=0.9)
    plt.tight_layout()

    return _fig_to_base64(fig)


def generate_electrical_trend_chart(events: Sequence[CanonicalEvent]) -> str | None:
    """Generate active and reactive power historical trend chart."""
    if not events:
        return None

    times: list[datetime] = []
    p_kw: list[float] = []
    q_kvar: list[float] = []

    for ev in events:
        meas_map = {m.signal_id: m.value for m in ev.measurements}
        p = meas_map.get("active_power_total_w")
        q = meas_map.get("reactive_power_total_var")
        if isinstance(p, (int, float)):
            times.append(ev.event_time_utc)
            p_kw.append(float(p) / 1000.0)
            q_kvar.append(float(q) / 1000.0 if isinstance(q, (int, float)) else 0.0)

    if not times:
        return None

    fig, ax = plt.subplots(figsize=(7.5, 2.8), dpi=150)
    ax.plot(times, p_kw, label="Active Power P (kW)", color="#059669", linewidth=1.5)
    ax.plot(times, q_kvar, label="Reactive Power Q (kvar)", color="#6366f1", linewidth=1.2, linestyle=":")

    ax.set_title("Electrical Load Dynamics · Active & Reactive Power", fontsize=10, fontweight="bold", color="#0e1824", pad=8)
    ax.set_ylabel("Power (kW / kvar)", fontsize=8, color="#354e6b")
    ax.grid(True, linestyle=":", alpha=0.6, color="#cbdff0")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.tick_params(axis="both", labelsize=7.5, colors="#354e6b")
    ax.legend(loc="upper left", fontsize=7.5, framealpha=0.9)
    plt.tight_layout()

    return _fig_to_base64(fig)


def generate_current_balance_chart(events: Sequence[CanonicalEvent]) -> str | None:
    """Generate 3-phase and neutral current historical trend chart."""
    if not events:
        return None

    times: list[datetime] = []
    i1: list[float] = []
    i2: list[float] = []
    i3: list[float] = []
    i_n: list[float] = []

    for ev in events:
        meas_map = {m.signal_id: m.value for m in ev.measurements}
        c1 = meas_map.get("current_l1")
        c2 = meas_map.get("current_l2")
        c3 = meas_map.get("current_l3")
        cn = meas_map.get("neutral_current")
        if isinstance(c1, (int, float)):
            times.append(ev.event_time_utc)
            i1.append(float(c1))
            i2.append(float(c2) if isinstance(c2, (int, float)) else 0.0)
            i3.append(float(c3) if isinstance(c3, (int, float)) else 0.0)
            i_n.append(float(cn) if isinstance(cn, (int, float)) else 0.0)

    if not times:
        return None

    fig, ax = plt.subplots(figsize=(7.5, 2.8), dpi=150)
    ax.plot(times, i1, label="Phase L1 (A)", color="#dc2626", linewidth=1.2)
    ax.plot(times, i2, label="Phase L2 (A)", color="#d97706", linewidth=1.2)
    ax.plot(times, i3, label="Phase L3 (A)", color="#2563eb", linewidth=1.2)
    ax.plot(times, i_n, label="Neutral N (A)", color="#4b5563", linewidth=1.0, linestyle="--")

    ax.set_title("Phase Current Balance & Neutral Return Conductor", fontsize=10, fontweight="bold", color="#0e1824", pad=8)
    ax.set_ylabel("Current (A)", fontsize=8, color="#354e6b")
    ax.grid(True, linestyle=":", alpha=0.6, color="#cbdff0")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.tick_params(axis="both", labelsize=7.5, colors="#354e6b")
    ax.legend(loc="upper left", fontsize=7.5, framealpha=0.9)
    plt.tight_layout()

    return _fig_to_base64(fig)
