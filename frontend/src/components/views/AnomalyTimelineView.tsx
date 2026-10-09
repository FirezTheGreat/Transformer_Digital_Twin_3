import React, { useState } from 'react';
import {
  AlertTriangle,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
} from 'lucide-react';

import { AnomalyEpisode, TwinState } from '../../types/contracts';

interface AnomalyTimelineViewProps {
  episodes: AnomalyEpisode[];
  twinState: TwinState | null;
  onSeedTripData: () => void;
  isSeeding: boolean;
}

export const AnomalyTimelineView: React.FC<AnomalyTimelineViewProps> = ({
  episodes,
  twinState: _twinState,
  onSeedTripData,
  isSeeding,
}) => {
  const [showDetectorMath, setShowDetectorMath] = useState<boolean>(false);

  const critCount = episodes.filter((e) => e.state === 'CRITICAL').length;
  const warnCount = episodes.filter((e) => e.state === 'WARNING').length;

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="eyebrow">Diagnostic Evidence</span>
            <span className="text-faint">·</span>
            <span className="eyebrow">8 Anomaly Detector Families</span>
          </div>
          <h1 className="page-title">Anomalies &amp; Evidence</h1>
          <p className="text-[13px] text-muted mt-2.5 max-w-2xl">
            Multi-domain anomaly detection tracking statistical rate-of-change, thermal residual drift, and discrete protection trips.
          </p>
        </div>

        <button
          onClick={onSeedTripData}
          disabled={isSeeding}
          className="btn btn-danger self-start lg:self-auto"
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>{isSeeding ? 'Injecting...' : 'Inject Protection Trip Fixture'}</span>
        </button>
      </div>

      {/* Episode Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-line border border-line rounded-card overflow-hidden">
        {[
          { label: 'Tracked Episodes', value: episodes.length, dot: 'bg-faint' },
          { label: 'Critical', value: critCount, dot: critCount > 0 ? 'bg-crit' : 'bg-line-strong' },
          { label: 'Warning', value: warnCount, dot: warnCount > 0 ? 'bg-warn' : 'bg-line-strong' },
        ].map((s) => (
          <div key={s.label} className="bg-surface p-5">
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <span className="eyebrow">{s.label}</span>
              <span className={`dot w-2 h-2 ${s.dot}`} />
            </div>
            <div className="metric-value text-[38px] mt-4">{s.value}</div>
          </div>
        ))}
      </div>

      {/* Active & Tracked Episodes Event Ledger */}
      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
          <h2 className="section-title">Active Anomaly Episodes ({episodes.length})</h2>
          <span className="text-[11px] text-muted font-mono">
            FSM: OPEN → CORROBORATED → RESOLVED / CLOSED
          </span>
        </div>

        {episodes.length === 0 ? (
          <div className="card-muted p-10 text-center">
            <span className="chip chip-ok mb-3">
              <CheckCircle2 className="w-3 h-3" /> Nominal
            </span>
            <p className="card-title">No active anomaly episodes</p>
            <p className="text-xs text-muted mt-1">
              All multi-domain detectors are operating within nominal thresholds.
            </p>
          </div>
        ) : (
          <div className="card divide-y divide-line overflow-hidden">
            {episodes.map((ep) => {
              const state = ep.state;
              const isCrit = state === 'CRITICAL';
              const isWarn = state === 'WARNING';
              const tone = isCrit ? 'crit' : isWarn ? 'warn' : 'accent';

              return (
                <div
                  key={ep.episode_id}
                  className="relative p-5 pl-6 hover:bg-surface-2 transition-colors"
                >
                  <span
                    className={`absolute left-0 top-0 bottom-0 w-[3px] ${
                      tone === 'crit' ? 'bg-crit' : tone === 'warn' ? 'bg-warn' : 'bg-accent'
                    }`}
                  />
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    <div className="flex items-start gap-3 min-w-0">
                      <AlertTriangle
                        className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                          tone === 'crit' ? 'text-crit' : tone === 'warn' ? 'text-warn' : 'text-accent'
                        }`}
                        strokeWidth={1.75}
                      />
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`chip ${
                              tone === 'crit' ? 'chip-crit' : tone === 'warn' ? 'chip-warn' : 'chip-accent'
                            }`}
                          >
                            {state}
                          </span>
                          <span className="text-[11px] font-mono text-muted">{ep.episode_id}</span>
                          <span className="text-faint">·</span>
                          <span className="text-xs font-medium text-ink-2">{ep.category}</span>
                        </div>
                        <h3 className="card-title mt-2">{ep.primary_reason}</h3>

                        {/* Hypothesis Codes */}
                        <div className="mt-3 flex flex-wrap items-center gap-1.5">
                          <span className="eyebrow text-[11px] mr-1">Hypotheses</span>
                          {ep.hypothesis_codes.map((code) => (
                            <span
                              key={code}
                              className="px-1.5 py-0.5 rounded font-mono text-[11px] text-ink-2 border border-line bg-surface-2"
                            >
                              {code}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="sm:text-right flex-shrink-0 pl-7 sm:pl-0">
                      <span className="eyebrow text-[11px]">Severity</span>
                      <div className="metric-value text-[28px] mt-1.5">
                        {(ep.severity_score * 100).toFixed(0)}
                        <span className="metric-unit ml-0.5">%</span>
                      </div>
                      <div className="text-[11px] font-mono text-muted mt-1.5">
                        Seen: {new Date(ep.start_time_utc).toISOString().replace('T', ' ').slice(0, 19)}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* CUSUM Statistical Drift Tracker - Disabled / Not Qualified */}
      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
          <h2 className="section-title">Statistical drift detector</h2>
          <span className="chip chip-outline font-mono">Frozen / Disabled</span>
        </div>
        <div className="card p-5">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-4 border-b border-line">
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1.5">
                <span className="eyebrow">Statistical Drift Detector</span>
                <span className="chip chip-neutral font-mono">DISABLED — NOT QUALIFIED</span>
              </div>
              <h3 className="card-title">Two-Sided Robust CUSUM Accumulator (Thermal Residual)</h3>
              <p className="text-xs text-muted mt-1">
                Thermal residual anomaly detection is not qualified for the current Tripura model artifact.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-line border border-line rounded-card overflow-hidden mt-4">
            {[
              { label: 'Positive Accumulator (C⁺)', note: 'Decision threshold: — (Disabled)' },
              { label: 'Negative Accumulator (C⁻)', note: 'Lower threshold: — (Disabled)' },
              { label: 'Persistence Window', note: 'Gate status: Inactive' },
            ].map((c) => (
              <div key={c.label} className="bg-surface-2 p-4">
                <span className="eyebrow text-[11px] block">{c.label}</span>
                <div className="metric-value text-[28px] font-normal text-faint mt-3">—</div>
                <span className="text-[11px] text-muted mt-2 block">{c.note}</span>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <button
              onClick={() => setShowDetectorMath(!showDetectorMath)}
              className="link inline-flex items-center gap-1"
            >
              <span>{showDetectorMath ? 'Hide detector details' : 'How does the CUSUM detector work?'}</span>
              {showDetectorMath ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>

            {showDetectorMath && (
              <div className="mt-3 text-xs text-ink-2 bg-surface-2 p-4 rounded-card border border-line space-y-1.5 leading-relaxed">
                <p>
                  <strong className="font-semibold text-ink">Algorithm:</strong> Cumulative sum of normalized thermal residuals: <span className="font-mono text-ink">C⁺_k = max(0, C⁺_{`k-1`} + (r_k - μ) / σ - k_drift)</span>.
                </p>
                <p>
                  Filters out high-frequency sensor noise while reliably detecting sustained upward or downward thermal shifts caused by overloading or cooling degradation.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
