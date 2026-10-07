import React from 'react';
import {
  AlertTriangle,
  ShieldAlert,
} from 'lucide-react';

import { AnomalyEpisode, TwinState } from '../../types/contracts';
import { UIHonestyBadge } from '../common/UIHonestyBadge';

interface AnomalyTimelineViewProps {
  episodes: AnomalyEpisode[];
  twinState: TwinState | null;
  onSeedTripData: () => void;
  isSeeding: boolean;
}

export const AnomalyTimelineView: React.FC<AnomalyTimelineViewProps> = ({
  episodes,
  twinState,
  onSeedTripData,
  isSeeding,
}) => {
  const cusumPos = twinState?.detector_state?.cusum_pos ?? 3.82;
  const cusumNeg = twinState?.detector_state?.cusum_neg ?? 0.0;
  const persistenceTimer = twinState?.detector_state?.persistence_timers?.['cusum_thermal_shift'] ?? 3600.0;

  return (
    <div className="space-y-8">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between pb-4 border-b border-[#d8e6f2] gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-[#5d768f]">
              DIAGNOSTIC EVIDENCE & FSM EPISODES
            </span>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-[#e8f1f8] text-[#1c3c5c]">
              6-State Lifecycle FSM
            </span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-[#0e1824] tracking-tight">
            Anomaly Episodes & CUSUM.
          </h2>
          <p className="text-xs sm:text-sm text-[#5d768f] font-light mt-0.5">
            Deterministic multi-domain anomaly evidence across 8 detector categories with CUSUM drift detection.
          </p>
        </div>

        {/* Dynamic Anomaly Injectors */}
        <div className="flex items-center gap-2">
          <button
            onClick={onSeedTripData}
            disabled={isSeeding}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#fff5f5] hover:bg-[#fee2e2] text-rose-800 text-xs font-semibold border border-rose-200 transition-all shadow-sm"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />
            <span>Inject Protection Trip Fixture</span>
          </button>
        </div>
      </div>

      {/* CUSUM Residual Tracker Summary */}
      <div className="bg-white rounded-3xl p-6 shadow-card border border-[#d8e6f2]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#edf4fa] gap-3">
          <div>
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block">
              TWO-SIDED ROBUST CUSUM ACCUMULATOR
            </span>
            <h4 className="font-editorial text-xl font-bold text-[#0e1824]">
              Persistent Thermal Drift Detector
            </h4>
          </div>
          <UIHonestyBadge type="DEMO_DEFAULT" customText="h = 3.50 Threshold" />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
          <div className="bg-[#eff5fb] p-4 rounded-2xl border border-[#dce9f4]">
            <span className="text-[10px] font-bold text-[#5d768f] block mb-1">
              POSITIVE CUSUM (C⁺)
            </span>
            <div className="text-3xl font-extrabold font-sans tracking-tight text-amber-800">
              {cusumPos.toFixed(2)}
            </div>
            <span className="text-[11px] text-[#5d768f] font-mono mt-1 block">
              Warning threshold: h = 3.50 (Exceeded)
            </span>
          </div>

          <div className="bg-[#eff5fb] p-4 rounded-2xl border border-[#dce9f4]">
            <span className="text-[10px] font-bold text-[#5d768f] block mb-1">
              NEGATIVE CUSUM (C⁻)
            </span>
            <div className="text-3xl font-extrabold font-sans tracking-tight text-emerald-800">
              {cusumNeg.toFixed(2)}
            </div>
            <span className="text-[11px] text-[#5d768f] font-mono mt-1 block">
              Lower threshold: h = -3.50 (Nominal)
            </span>
          </div>

          <div className="bg-[#eff5fb] p-4 rounded-2xl border border-[#dce9f4]">
            <span className="text-[10px] font-bold text-[#5d768f] block mb-1">
              PERSISTENCE DURATION
            </span>
            <div className="text-3xl font-extrabold font-sans tracking-tight text-[#0e1824]">
              {(persistenceTimer / 60).toFixed(0)} mins
            </div>
            <span className="text-[11px] text-[#5d768f] font-mono mt-1 block">
              Active persistence debounce window
            </span>
          </div>
        </div>
      </div>

      {/* 6-State Episode FSM Timeline */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#5d768f]">
            ACTIVE & TRACKED EPISODES ({episodes.length})
          </span>
          <span className="text-xs text-[#5d768f] font-mono">
            Lifecycle: NORMAL → WATCH → WARNING → CRITICAL → RECOVERING → CLOSED
          </span>
        </div>

        {episodes.length === 0 ? (
          <div className="bg-white rounded-3xl p-12 text-center border border-[#d8e6f2] shadow-card">
            <h4 className="font-editorial text-2xl text-[#0e1824]">No open anomaly episodes</h4>
            <p className="text-xs text-[#5d768f] mt-1">
              All detectors reporting nominal operating state without active limit excursions.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {episodes.map((ep) => {
              const state = ep.state;
              const isCrit = state === 'CRITICAL';
              const isWarn = state === 'WARNING';

              return (
                <div
                  key={ep.episode_id}
                  className="bg-white rounded-3xl p-6 sm:p-7 shadow-card border border-[#d8e6f2] hover:border-[#bcd5eb] transition-all"
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#edf4fa]">
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-10 h-10 rounded-2xl flex items-center justify-center ${
                          isCrit
                            ? 'bg-rose-100 text-rose-800'
                            : isWarn
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-sky-100 text-sky-800'
                        }`}
                      >
                        <AlertTriangle className="w-5 h-5" />
                      </div>

                      <div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[10px] uppercase font-bold tracking-wider px-2.5 py-0.5 rounded-full ${
                              isCrit
                                ? 'bg-rose-100 text-rose-800'
                                : isWarn
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-sky-100 text-sky-800'
                            }`}
                          >
                            {state}
                          </span>
                          <span className="text-xs font-mono font-semibold text-[#5d768f]">
                            {ep.episode_id}
                          </span>
                        </div>
                        <h4 className="text-xl font-editorial font-bold text-[#0e1824] mt-1">
                          {ep.primary_reason}
                        </h4>
                      </div>
                    </div>

                    <div className="text-left md:text-right text-xs text-[#5d768f] font-mono">
                      <div>Severity Score: <strong>{(ep.severity_score * 100).toFixed(0)}%</strong></div>
                      <div>Category: {ep.category}</div>
                    </div>
                  </div>

                  {/* Hypothesis Codes & Timing */}
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[10px] uppercase font-bold text-[#5d768f]">HYPOTHESES:</span>
                      {ep.hypothesis_codes.map((code) => (
                        <span
                          key={code}
                          className="bg-[#eff5fb] text-[#1c3c5c] px-2.5 py-0.5 rounded-md font-mono text-[11px] border border-[#dce8f3]"
                        >
                          {code}
                        </span>
                      ))}
                    </div>

                    <div className="text-[11px] text-[#829ab1] font-mono">
                      First Observed: {new Date(ep.start_time_utc).toISOString()}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
