import React, { useState, useEffect } from 'react';
import { Database, Clock, RefreshCw, CheckCircle2 } from 'lucide-react';
import { TwinState, CapabilityManifest, CanonicalEvent } from '../../types/contracts';
import { api } from '../../services/api';
import { TelemetryPhaseGrid } from '../TelemetryPhaseGrid';
import { UIHonestyBadge } from '../common/UIHonestyBadge';

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
    if (propHistoryEvents && propHistoryEvents.length > 0) {
      setEvents(propHistoryEvents);
    } else {
      fetchHistory();
    }
  }, [assetId, propHistoryEvents]);

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-subtle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                Observability & Operating Limits
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                Tier {capabilities?.highest_tier ?? 'C2'}
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
              Live Electrical Telemetry & Capabilities
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Three-phase measurements, derived unbalance indices, dynamic capability gates, and temporal storage event log.
            </p>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <UIHonestyBadge type="relative_load_index" />
          </div>
        </div>
      </div>

      {/* Main Phase Telemetry Grid & Capability Manifest */}
      <TelemetryPhaseGrid twinState={twinState} capabilities={capabilities} />

      {/* Historical Telemetry Stream Table from DuckDB (/v1/assets/{id}/history) */}
      <div className="bg-white rounded-lg p-5 border border-slate-200 shadow-subtle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-100 gap-3 mb-3">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-sky-600" />
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Temporal Storage Event Stream ({events.length} frames queried)
              </h3>
              <p className="text-xs text-slate-500">
                Chronological DuckDB state store with raw SHA-256 provenance hashes.
              </p>
            </div>
          </div>

          <button
            onClick={fetchHistory}
            disabled={isLoadingHistory}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold border border-slate-300 transition-colors self-start sm:self-auto"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingHistory ? 'animate-spin text-sky-600' : ''}`} />
            <span>Refresh Storage Log</span>
          </button>
        </div>

        {events.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500">
            <Clock className="w-6 h-6 mx-auto text-slate-400 mb-2" />
            <p className="font-semibold text-slate-800">No historical events recorded yet</p>
            <p className="text-slate-400 mt-0.5">Click &quot;Ingest Dataset&quot; in the control bar above to load SCADA frames.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-[10px] uppercase font-bold tracking-wider text-slate-500 bg-slate-50">
                  <th className="py-2.5 px-3">Event ID</th>
                  <th className="py-2.5 px-3">Timestamp (UTC)</th>
                  <th className="py-2.5 px-3">Source</th>
                  <th className="py-2.5 px-3">Primary Signals</th>
                  <th className="py-2.5 px-3">Quality Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                {events.slice(0, 15).map((ev) => {
                  const otiVal = ev.measurements.find((m) => m.signal_id.includes('top_oil') || m.original_name === 'OTI')?.value;
                  const vrVal = ev.measurements.find((m) => m.signal_id.includes('voltage_l1') || m.original_name === 'V_R')?.value;
                  const irVal = ev.measurements.find((m) => m.signal_id.includes('current_l1') || m.original_name === 'I_R')?.value;

                  return (
                    <tr key={ev.event_id} className="hover:bg-slate-50 transition-colors">
                      <td className="py-2 px-3 font-semibold text-slate-900">{ev.event_id}</td>
                      <td className="py-2 px-3 text-slate-600">
                        {new Date(ev.event_time_utc).toISOString().replace('T', ' ').slice(0, 19)}
                      </td>
                      <td className="py-2 px-3 text-slate-500">
                        {ev.source?.system || 'tripura_scada'}
                      </td>
                      <td className="py-2 px-3 text-slate-800">
                        <span className="inline-flex gap-3">
                          {otiVal !== undefined && <span>OTI: {String(otiVal)}°C</span>}
                          {vrVal !== undefined && <span>V_R: {String(vrVal)}V</span>}
                          {irVal !== undefined && <span>I_R: {String(irVal)}A</span>}
                        </span>
                      </td>
                      <td className="py-2 px-3">
                        {ev.event_quality_flags.length === 0 ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700 font-sans font-medium text-[10px]">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Normal
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 font-sans font-bold text-[10px]">
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
  );
};
