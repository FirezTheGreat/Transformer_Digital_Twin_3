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
      // Fallback
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
    <div className="space-y-8">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between pb-4 border-b border-[#d8e6f2] gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-[#5d768f]">
              CONTINUOUS OBSERVABILITY & CAPABILITY CONFINEMENT
            </span>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-[#e8f1f8] text-[#1c3c5c]">
              Tier {capabilities?.highest_tier ?? 'C2'}
            </span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-[#0e1824] tracking-tight">
            Telemetry & Tiers.
          </h2>
          <p className="text-xs sm:text-sm text-[#5d768f] font-light mt-0.5">
            Three-phase electrical measurements, derived physical indices, dynamic C0–C4 operational capability gating, and chronological DuckDB event store.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <UIHonestyBadge type="relative_load_index" />
        </div>
      </div>

      {/* Main Phase Telemetry and Capability Manifest */}
      <TelemetryPhaseGrid twinState={twinState} capabilities={capabilities} />

      {/* Historical Telemetry Stream Table from DuckDB (/v1/assets/{id}/history) */}
      <div className="bg-white rounded-3xl p-6 shadow-card border border-[#d8e6f2]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#edf4fa] gap-3 mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-sky-50 border border-sky-200 text-[#0284c7] flex items-center justify-center">
              <Database className="w-4 h-4" />
            </div>
            <div>
              <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block">
                DUCKDB TEMPORAL STORAGE FEED
              </span>
              <h3 className="font-editorial text-xl font-bold text-[#0e1824]">
                Canonical Historical Events ({events.length} frames queried)
              </h3>
            </div>
          </div>

          <button
            onClick={fetchHistory}
            disabled={isLoadingHistory}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[#eff5fb] hover:bg-[#e4eff8] text-[#0e1824] text-xs font-semibold border border-[#d2e2ef] transition-colors self-start sm:self-auto"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingHistory ? 'animate-spin text-[#0284c7]' : ''}`} />
            <span>Refresh Storage Log</span>
          </button>
        </div>

        {events.length === 0 ? (
          <div className="py-10 text-center text-xs text-[#5d768f]">
            <Clock className="w-8 h-8 mx-auto text-[#a0aec0] mb-2" />
            <p className="font-medium text-[#0e1824]">No historical events recorded yet for this asset.</p>
            <p className="mt-1">Click &quot;Seed Data&quot; in the Replay Bar above to ingest the canonical 74-frame dataset into DuckDB.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#edf4fa] text-[10px] uppercase font-bold tracking-wider text-[#5d768f]">
                  <th className="py-3 px-3">Event ID</th>
                  <th className="py-3 px-3">Event Timestamp (UTC)</th>
                  <th className="py-3 px-3">Source Adapter</th>
                  <th className="py-3 px-3">Measurements</th>
                  <th className="py-3 px-3">Quality Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f2f7fb] font-mono text-[11px]">
                {events.slice(0, 15).map((ev) => {
                  const otiVal = ev.measurements.find((m) => m.signal_id.includes('top_oil') || m.original_name === 'OTI')?.value;
                  const vrVal = ev.measurements.find((m) => m.signal_id.includes('voltage_l1') || m.original_name === 'V_R')?.value;
                  const irVal = ev.measurements.find((m) => m.signal_id.includes('current_l1') || m.original_name === 'I_R')?.value;

                  return (
                    <tr key={ev.event_id} className="hover:bg-[#f8fbfe] transition-colors">
                      <td className="py-2.5 px-3 font-semibold text-[#0e1824]">{ev.event_id}</td>
                      <td className="py-2.5 px-3 text-[#486581]">
                        {new Date(ev.event_time_utc).toISOString().replace('T', ' ').slice(0, 19)}
                      </td>
                      <td className="py-2.5 px-3 text-[#64748b]">
                        {ev.source?.system || 'tripura_scada'}
                      </td>
                      <td className="py-2.5 px-3 text-[#0e1824]">
                        <span className="inline-flex gap-2">
                          {otiVal !== undefined && <span>OTI: {String(otiVal)}°C</span>}
                          {vrVal !== undefined && <span>V_R: {String(vrVal)}V</span>}
                          {irVal !== undefined && <span>I_R: {String(irVal)}A</span>}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        {ev.event_quality_flags.length === 0 ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700 font-sans font-medium text-[10px]">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> NORMAL
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-sans font-bold text-[10px]">
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
