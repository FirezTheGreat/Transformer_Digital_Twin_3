import React, { useState, useEffect } from 'react';
import { Database, Clock, RefreshCw, CheckCircle2 } from 'lucide-react';
import { TwinState, CapabilityManifest, CanonicalEvent } from '../../types/contracts';
import { api } from '../../services/api';
import { TelemetryPhaseGrid } from '../TelemetryPhaseGrid';
import { UIHonestyBadge } from '../common/UIHonestyBadge';
import { TrendChart, LegendItem, TrendSeries, readSignal, formatUtcTick } from '../common/TrendChart';

interface TelemetryViewProps {
  assetId: string;
  twinState: TwinState | null;
  capabilities: CapabilityManifest | null;
  historyEvents?: CanonicalEvent[];
}

export const TelemetryView: React.FC<TelemetryViewProps> = ({
  assetId,
  twinState,
  capabilities,
  historyEvents: propHistoryEvents,
}) => {
  const [events, setEvents] = useState<CanonicalEvent[]>(propHistoryEvents || []);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);

  const fetchHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const res = await api.getAssetHistory(assetId, { limit: 50 });
      if (res && res.events) {
        setEvents(res.events);
      }
    } catch {
      // Fallback to existing
    } finally {
      setIsLoadingHistory(false);
    }
  };

  useEffect(() => {
    if (propHistoryEvents !== undefined) {
      setEvents(propHistoryEvents);
    } else {
      fetchHistory();
    }
  }, [assetId, propHistoryEvents]);

  // Presentation-only: per-frame readings straight from recorded history events
  const trendRows = events.map((ev) => ({
    t: formatUtcTick(ev.event_time_utc),
    topOil: readSignal(ev.measurements, ['top_oil_temperature']),
    iR: readSignal(ev.measurements, ['current_l1', 'current_i1']),
    iY: readSignal(ev.measurements, ['current_l2', 'current_i2']),
    iB: readSignal(ev.measurements, ['current_l3', 'current_i3']),
    vR: readSignal(ev.measurements, ['voltage_l1_n', 'voltage_v1']),
    vY: readSignal(ev.measurements, ['voltage_l2_n', 'voltage_v2']),
    vB: readSignal(ev.measurements, ['voltage_l3_n', 'voltage_v3']),
    p: readSignal(ev.measurements, ['active_power_total', 'active_power']),
  }));

  const panels: { title: string; unit: string; series: TrendSeries[]; area?: boolean }[] = [
    { title: 'Top-oil temperature', unit: '°C', series: [{ key: 'topOil', label: 'Top-oil' }], area: true },
    { title: 'Active power', unit: 'kW', series: [{ key: 'p', label: 'Active power' }], area: true },
    {
      title: 'Phase currents',
      unit: 'A',
      series: [
        { key: 'iR', label: 'I_R', colorIndex: 0 },
        { key: 'iY', label: 'I_Y', colorIndex: 1 },
        { key: 'iB', label: 'I_B', colorIndex: 2 },
      ],
    },
    {
      title: 'Phase voltages (L-N)',
      unit: 'V',
      series: [
        { key: 'vR', label: 'V_R', colorIndex: 0 },
        { key: 'vY', label: 'V_Y', colorIndex: 1 },
        { key: 'vB', label: 'V_B', colorIndex: 2 },
      ],
    },
  ];

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="eyebrow">Observability & Operating Limits</span>
            <span className="chip chip-neutral font-mono">Tier {capabilities?.highest_tier ?? 'C2'}</span>
          </div>
          <h1 className="page-title">Electrical Telemetry</h1>
          <p className="text-[13px] text-muted mt-2.5 max-w-2xl">
            Three-phase measurements, derived unbalance indices, dynamic capability gates, and temporal storage event log.
          </p>
        </div>

        <UIHonestyBadge type="relative_load_index" />
      </div>

      {/* Main Phase Telemetry Grid & Capability Manifest */}
      <TelemetryPhaseGrid twinState={twinState} capabilities={capabilities} assetId={assetId} />

      {/* Recorded Trends (small multiples, one axis each) */}
      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
          <h2 className="section-title">Recorded trends</h2>
          <span className="text-[11px] font-mono text-muted">
            {events.length > 0
              ? `${events.length} frames · ${formatUtcTick(events[0].event_time_utc)} → ${formatUtcTick(
                  events[events.length - 1].event_time_utc
                )} UTC`
              : 'No recorded frames'}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {panels.map((panel) => {
            const hasData = trendRows.some((r) =>
              panel.series.some((s) => r[s.key as keyof typeof r] !== null)
            );
            return (
              <div key={panel.title} className="card-muted p-5">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                  <span className="eyebrow text-ink-2">
                    {panel.title} · {panel.unit}
                  </span>
                  {panel.series.length > 1 && (
                    <div className="flex items-center gap-3">
                      {panel.series.map((s) => (
                        <LegendItem key={s.key} label={s.label} colorIndex={s.colorIndex} />
                      ))}
                    </div>
                  )}
                </div>
                {hasData ? (
                  <TrendChart
                    data={trendRows}
                    xKey="t"
                    series={panel.series}
                    unit={panel.unit}
                    area={panel.area}
                    height={190}
                  />
                ) : (
                  <div className="h-[190px] flex items-center justify-center text-center border border-dashed border-line-strong rounded-card text-[11px] text-muted px-4">
                    No recorded {panel.title.toLowerCase()} yet — start the Digital Twin and step telemetry.
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Historical Telemetry Stream Table (/v1/assets/{id}/history) */}
      <div>
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 mb-3">
          <div>
            <h2 className="section-title flex items-center gap-2.5">
              <Database className="w-[18px] h-[18px] text-muted" strokeWidth={1.75} />
              Historical Telemetry ({events.length} frames recorded)
            </h2>
            <p className="text-xs text-muted mt-1">
              Chronological record of transformer telemetry and data quality.
            </p>
          </div>

          <button
            onClick={fetchHistory}
            disabled={isLoadingHistory}
            className="btn btn-ghost self-start sm:self-auto"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingHistory ? 'animate-spin text-accent' : ''}`} />
            <span>Refresh Telemetry Log</span>
          </button>
        </div>

        <div className="card overflow-hidden">
          {events.length === 0 ? (
            <div className="py-12 text-center text-xs text-muted">
              <Clock className="w-6 h-6 mx-auto text-faint mb-3" strokeWidth={1.5} />
              <p className="card-title">No historical events recorded yet</p>
              <p className="mt-1">Start the Digital Twin or step telemetry to inspect recorded frames.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-line bg-surface-2">
                    <th className="py-3 px-4 eyebrow text-[11px] font-semibold">Event ID</th>
                    <th className="py-3 px-4 eyebrow text-[11px] font-semibold">Timestamp (UTC)</th>
                    <th className="py-3 px-4 eyebrow text-[11px] font-semibold">Source</th>
                    <th className="py-3 px-4 eyebrow text-[11px] font-semibold">Primary Signals</th>
                    <th className="py-3 px-4 eyebrow text-[11px] font-semibold">Quality Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line font-mono text-[11px]">
                  {events.slice(0, 15).map((ev) => {
                    const otiVal = ev.measurements.find((m) => m.signal_id.includes('top_oil') || m.original_name === 'OTI')?.value;
                    const vrVal = ev.measurements.find((m) => m.signal_id.includes('voltage_l1') || m.original_name === 'V_R')?.value;
                    const irVal = ev.measurements.find((m) => m.signal_id.includes('current_l1') || m.original_name === 'I_R')?.value;

                    return (
                      <tr key={ev.event_id} className="hover:bg-surface-2 transition-colors">
                        <td className="py-2.5 px-4 font-medium text-ink whitespace-nowrap">{ev.event_id}</td>
                        <td className="py-2.5 px-4 text-ink-2 whitespace-nowrap">
                          {new Date(ev.event_time_utc).toISOString().replace('T', ' ').slice(0, 19)}
                        </td>
                        <td className="py-2.5 px-4 text-muted whitespace-nowrap">
                          {ev.source?.system || 'tripura_scada'}
                        </td>
                        <td className="py-2.5 px-4 text-ink-2 whitespace-nowrap">
                          <span className="inline-flex gap-4">
                            {otiVal !== undefined && <span>OTI: {String(otiVal)}°C</span>}
                            {vrVal !== undefined && <span>V_R: {String(vrVal)}V</span>}
                            {irVal !== undefined && <span>I_R: {String(irVal)}A</span>}
                          </span>
                        </td>
                        <td className="py-2.5 px-4">
                          {ev.event_quality_flags.length === 0 ? (
                            <span className="inline-flex items-center gap-1.5 text-muted font-sans font-medium text-[11px]">
                              <CheckCircle2 className="w-3 h-3 text-ok" /> Normal
                            </span>
                          ) : (
                            <span className="chip chip-warn font-sans">
                              {ev.event_quality_flags.join(', ')}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
