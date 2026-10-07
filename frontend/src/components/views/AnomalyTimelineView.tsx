import React, { useState } from 'react';
import {
  AlertTriangle,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
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
  const [showDetectorMath, setShowDetectorMath] = useState<boolean>(false);

  const cusumPos = twinState?.detector_state?.cusum_pos ?? 3.82;
  const cusumNeg = twinState?.detector_state?.cusum_neg ?? 0.0;
  const persistenceTimer = twinState?.detector_state?.persistence_timers?.['cusum_thermal_shift'] ?? 3600.0;

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-subtle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                Diagnostic Evidence
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                8 Anomaly Detector Families
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
              Anomaly Episodes & Evidence Ledger
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Multi-domain anomaly detection tracking statistical rate-of-change, thermal residual drift, and discrete protection trips.
            </p>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <button
              onClick={onSeedTripData}
              disabled={isSeeding}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-rose-50 hover:bg-rose-100 text-rose-800 text-xs font-semibold border border-rose-300 transition-colors disabled:opacity-50"
            >
              <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />
              <span>{isSeeding ? 'Injecting...' : 'Inject Protection Trip Fixture'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* CUSUM Statistical Drift Tracker */}
      <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-subtle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-100">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
              Statistical Drift Detector
            </span>
            <h3 className="text-sm font-bold text-slate-900">
              Two-Sided Robust CUSUM Accumulator (Thermal Residual)
            </h3>
          </div>
          <UIHonestyBadge type="DEMO_DEFAULT" customText="Alarm Threshold: h = 3.50" />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
          <div className="bg-slate-50 p-3 rounded border border-slate-200">
            <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-0.5">
              Positive Accumulator (C⁺)
            </span>
            <div className="text-xl font-bold font-mono text-amber-800">
              {cusumPos.toFixed(2)}
            </div>
            <span className="text-[10px] text-slate-500 mt-0.5 block">
              Threshold: h = 3.50 ({cusumPos > 3.5 ? 'Shift Flagged' : 'Normal'})
            </span>
          </div>

          <div className="bg-slate-50 p-3 rounded border border-slate-200">
            <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-0.5">
              Negative Accumulator (C⁻)
            </span>
            <div className="text-xl font-bold font-mono text-emerald-800">
              {cusumNeg.toFixed(2)}
            </div>
            <span className="text-[10px] text-slate-500 mt-0.5 block">
              Lower threshold: h = -3.50 (Nominal)
            </span>
          </div>

          <div className="bg-slate-50 p-3 rounded border border-slate-200">
            <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-0.5">
              Persistence Window
            </span>
            <div className="text-xl font-bold font-mono text-slate-900">
              {(persistenceTimer / 60).toFixed(0)} min
            </div>
            <span className="text-[10px] text-slate-500 mt-0.5 block">
              Continuous debounce timer
            </span>
          </div>
        </div>

        <div className="mt-3 pt-2 border-t border-slate-100">
          <button
            onClick={() => setShowDetectorMath(!showDetectorMath)}
            className="text-xs text-sky-600 hover:text-sky-800 flex items-center gap-1 font-medium"
          >
            <span>{showDetectorMath ? 'Hide detector details' : 'How does the CUSUM detector work?'}</span>
            {showDetectorMath ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>

          {showDetectorMath && (
            <div className="mt-2 text-xs text-slate-600 bg-slate-50 p-3 rounded border border-slate-200 space-y-1">
              <p>
                <strong>Algorithm:</strong> Cumulative sum of normalized thermal residuals: <span className="font-mono text-slate-800">C⁺_k = max(0, C⁺_{`k-1`} + (r_k - μ) / σ - k_drift)</span>.
              </p>
              <p>
                Filters out high-frequency sensor noise while reliably detecting sustained upward or downward thermal shifts caused by overloading or cooling degradation.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Active & Tracked Episodes Event Ledger */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
            Active Anomaly Episodes ({episodes.length})
          </h3>
          <span className="text-xs text-slate-400 font-mono">
            FSM: OPEN → CORROBORATED → RESOLVED / CLOSED
          </span>
        </div>

        {episodes.length === 0 ? (
          <div className="bg-white rounded-lg p-8 text-center border border-slate-200 shadow-subtle text-slate-500">
            <p className="text-sm font-semibold text-slate-800">No active anomaly episodes</p>
            <p className="text-xs text-slate-400 mt-1">
              All multi-domain detectors are operating within nominal thresholds.
            </p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-lg shadow-subtle divide-y divide-slate-100 overflow-hidden">
            {episodes.map((ep) => {
              const state = ep.state;
              const isCrit = state === 'CRITICAL';
              const isWarn = state === 'WARNING';

              return (
                <div
                  key={ep.episode_id}
                  className="p-4 hover:bg-slate-50/70 transition-colors"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div
                        className={`p-1.5 rounded mt-0.5 ${
                          isCrit
                            ? 'bg-rose-100 text-rose-800'
                            : isWarn
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-sky-100 text-sky-800'
                        }`}
                      >
                        <AlertTriangle className="w-4 h-4" />
                      </div>

                      <div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded ${
                              isCrit
                                ? 'bg-rose-100 text-rose-800'
                                : isWarn
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-sky-100 text-sky-800'
                            }`}
                          >
                            {state}
                          </span>
                          <span className="text-[11px] font-mono text-slate-400">
                            {ep.episode_id}
                          </span>
                          <span className="text-slate-300">·</span>
                          <span className="text-xs font-semibold text-slate-600">
                            {ep.category}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-slate-900 mt-1">
                          {ep.primary_reason}
                        </h4>
                      </div>
                    </div>

                    <div className="text-left sm:text-right text-xs text-slate-500 font-mono">
                      <div>Severity: <strong className="text-slate-900">{(ep.severity_score * 100).toFixed(0)}%</strong></div>
                      <div className="text-[10px] text-slate-400">
                        Seen: {new Date(ep.start_time_utc).toISOString().replace('T', ' ').slice(0, 19)}
                      </div>
                    </div>
                  </div>

                  {/* Hypothesis Codes */}
                  <div className="mt-2.5 pl-8 flex flex-wrap items-center gap-2 text-xs">
                    <span className="text-[10px] uppercase font-bold text-slate-400">Hypotheses:</span>
                    {ep.hypothesis_codes.map((code) => (
                      <span
                        key={code}
                        className="bg-slate-50 text-slate-700 px-2 py-0.5 rounded font-mono text-[11px] border border-slate-200"
                      >
                        {code}
                      </span>
                    ))}
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
