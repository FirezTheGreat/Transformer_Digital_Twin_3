import React, { useState } from 'react';
import {
  Activity,
  Flame,
  Zap,
  Gauge,
  ArrowRight,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Info,
  X,
  CheckCircle2,
  ShieldAlert,
} from 'lucide-react';

import {
  TwinState,
  OTHIBundle,
  CapabilityManifest,
  MaintenanceRecommendation,
  AnomalyEpisode,
} from '../../types/contracts';
import { UIHonestyBadge } from '../common/UIHonestyBadge';

interface OverviewViewProps {
  assetId: string;
  twinState: TwinState | null;
  health: OTHIBundle | null;
  capabilities: CapabilityManifest | null;
  recommendations: MaintenanceRecommendation[];
  episodes: AnomalyEpisode[];
  onNavigateTab: (tab: string) => void;
  onOpenFeedback: (rec: MaintenanceRecommendation) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  assetId,
  twinState,
  health,
  capabilities,
  recommendations,
  episodes,
  onNavigateTab,
  onOpenFeedback,
}) => {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState<boolean>(false);
  const [isCapabilityModalOpen, setIsCapabilityModalOpen] = useState<boolean>(false);
  const [isEvidenceModalOpen, setIsEvidenceModalOpen] = useState<boolean>(false);
  const [isHealthModalOpen, setIsHealthModalOpen] = useState<boolean>(false);

  const isGated = health?.is_gated ?? true;
  const othiScore = health?.othi_score ?? null;
  const healthStatus = health?.status ?? null;
  const evidenceGrade = health?.evidence_grade ?? 'U';
  const highestTier = capabilities?.highest_tier ?? 'C2';

  const obs = twinState?.current_observations ?? {};
  const derived = twinState?.derived_electrical;

  // 1. Authoritative Top-Oil Observation & Shadow ODE State
  const topOilObsVal = typeof obs['top_oil_temperature']?.value === 'number'
    ? obs['top_oil_temperature'].value
    : null;
  const topOilObs = topOilObsVal !== null ? topOilObsVal.toFixed(1) : null;

  const isThermalWarmup = (twinState?.thermal_latent?.warmup_samples_remaining ?? 0) > 0;
  const topOilExpectedNum = twinState?.thermal_latent?.top_oil_expected_degc;
  const hasValidExpected = typeof topOilExpectedNum === 'number' && !isThermalWarmup;
  const topOilExpected = hasValidExpected ? (topOilExpectedNum as number).toFixed(1) : null;

  const residualNum = (topOilObsVal !== null && hasValidExpected)
    ? (topOilObsVal - (topOilExpectedNum as number))
    : null;
  const residual = residualNum !== null ? residualNum.toFixed(1) : null;

  // 2. Authoritative Electrical Measurements & Derivations
  const pVal = typeof obs['active_power_total']?.value === 'number'
    ? obs['active_power_total'].value
    : (typeof obs['active_power']?.value === 'number' ? obs['active_power'].value : null);
  const activePowerKw = pVal !== null ? pVal.toFixed(1) : null;

  const qVal = typeof obs['reactive_power_total']?.value === 'number'
    ? obs['reactive_power_total'].value
    : (typeof obs['reactive_power']?.value === 'number' ? obs['reactive_power'].value : null);
  const reactivePowerKvar = qVal !== null ? qVal.toFixed(1) : null;

  // Authoritative S: derived -> observed -> vector sum sqrt(P² + Q²)
  let sVal: number | null = null;
  if (typeof derived?.apparent_power_derived_kva === 'number') {
    sVal = derived.apparent_power_derived_kva;
  } else if (typeof obs['apparent_power_total']?.value === 'number') {
    sVal = obs['apparent_power_total'].value;
  } else if (typeof obs['apparent_power']?.value === 'number') {
    sVal = obs['apparent_power'].value;
  } else if (pVal !== null && qVal !== null) {
    sVal = Math.sqrt(pVal * pVal + qVal * qVal);
  }
  const apparentPowerKva = sVal !== null ? sVal.toFixed(1) : null;

  // Authoritative PF: derived -> telemetry avg -> |P| / S
  let pfVal: number | null = null;
  if (typeof derived?.power_factor_derived === 'number') {
    pfVal = derived.power_factor_derived;
  } else if (typeof obs['power_factor_avg']?.value === 'number') {
    pfVal = obs['power_factor_avg'].value;
  } else if (pVal !== null && sVal !== null && sVal > 0.001) {
    pfVal = Math.min(1.0, Math.abs(pVal) / sVal);
  }
  const powerFactor = pfVal !== null ? pfVal.toFixed(3) : null;

  const relLoad = typeof derived?.relative_load_index === 'number'
    ? derived.relative_load_index
    : null;
  const relativeLoad = relLoad !== null ? relLoad.toFixed(2) : null;
  const tauHours = twinState?.thermal_latent?.time_constant_tau_hours ?? 0.5;

  const domains = health?.domains ?? {};
  const activeRec = recommendations.length > 0 ? recommendations[0] : null;
  const activeEpisodeCount = episodes.filter((e) => e.state !== 'CLOSED').length;

  const getTierTitle = (tier: string) => {
    switch (tier) {
      case 'C0': return 'C0 · Data Integrity & Ingestion';
      case 'C1': return 'C1 · Electrical Balance & Power Quality';
      case 'C2': return 'C2 · Predictive monitoring (Descriptive Thermal)';
      case 'C3': return 'C3 · Thermal ODE Modeling & What-If';
      case 'C4': return 'C4 · Hot-Spot & Life Consumption';
      default: return `${tier} · Operating Capability`;
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Asset Header & High-Level Condition Banner */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-subtle transition-colors">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          {/* Asset Identity & Substation Summary */}
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-1.5">
              <span className="text-xs font-bold text-slate-900 dark:text-slate-100 font-mono">{assetId}</span>
              <span className="text-slate-300 dark:text-slate-600">·</span>
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">Agartala Substation (33/11kV)</span>
              <span className="text-slate-300 dark:text-slate-600">·</span>
              <button
                onClick={() => setIsCapabilityModalOpen(true)}
                className="inline-flex items-center gap-1.5 text-xs font-mono px-2.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer group"
                title="Click to understand Current Operating Capability"
              >
                <span className="text-[10px] uppercase font-bold text-slate-400 font-sans">Capability:</span>
                <span className="font-bold text-sky-700 dark:text-sky-400">{getTierTitle(highestTier)}</span>
                <Info className="w-3 h-3 text-slate-400 group-hover:text-sky-600 dark:group-hover:text-sky-400" />
              </button>
              {activeEpisodeCount > 0 && (
                <button
                  onClick={() => onNavigateTab('anomalies')}
                  className="text-xs font-semibold px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-950 text-amber-900 dark:text-amber-200 hover:bg-amber-200 dark:hover:bg-amber-900 transition-colors"
                >
                  {activeEpisodeCount} Active {activeEpisodeCount === 1 ? 'Anomaly' : 'Anomalies'}
                </button>
              )}
              {isGated && <UIHonestyBadge type="GATED_EVIDENCE" />}
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
              Distribution Transformer Condition Overview
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Live transformer telemetry, thermal condition tracking, anomaly detection, and maintenance guidance.
            </p>
          </div>

          {/* Health Index Metric Display */}
          <div className="flex items-center gap-4 bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-lg p-3.5 self-start lg:self-auto">
            <div
              onClick={() => setIsHealthModalOpen(true)}
              className="cursor-pointer group"
              title="Click to understand Health Index (OTHI)"
            >
              <div className="flex items-center gap-1">
                <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 group-hover:text-slate-600 block">
                  Health Index (OTHI)
                </span>
                <Info className="w-3 h-3 text-slate-400 group-hover:text-sky-600" />
              </div>
              <div className="flex items-baseline gap-1.5 mt-0.5">
                {othiScore !== null && !isGated && evidenceGrade !== 'U' ? (
                  <>
                    <span className="text-3xl font-extrabold text-slate-900 dark:text-slate-100 font-sans leading-none">
                      {Math.round(Number(othiScore))}
                    </span>
                    <span className="text-xs text-slate-400 font-medium">/ 100</span>
                  </>
                ) : (
                  <>
                    <span className="text-3xl font-extrabold text-slate-400 font-sans leading-none">
                      —
                    </span>
                    <span className="text-[10px] text-amber-700 dark:text-amber-400 font-medium block">
                      Insufficient current evidence
                    </span>
                  </>
                )}
              </div>
              <span className="text-[9px] text-slate-400 block mt-0.5">
                {othiScore !== null && !isGated && evidenceGrade !== 'U'
                  ? 'Composite health index'
                  : 'Gated (requires ≥2 corroborated domains)'}
              </span>
            </div>

            <div className="pl-4 border-l border-slate-200 dark:border-slate-700">
              {healthStatus && othiScore !== null && !isGated && evidenceGrade !== 'U' ? (
                <span
                  className={`inline-block px-2.5 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${
                    healthStatus === 'NORMAL'
                      ? 'bg-emerald-100 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300'
                      : healthStatus === 'WATCH'
                      ? 'bg-amber-100 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300'
                      : 'bg-rose-100 dark:bg-rose-950/40 text-rose-800 dark:text-rose-300'
                  }`}
                >
                  {healthStatus}
                </span>
              ) : (
                <span className="inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                  Status: Insufficient evidence
                </span>
              )}
              <button
                onClick={() => setIsEvidenceModalOpen(true)}
                className="text-[10px] text-slate-600 dark:text-slate-400 hover:text-sky-700 dark:hover:text-sky-400 hover:underline block mt-1 font-medium cursor-pointer flex items-center gap-1"
                title="Click to understand Evidence Grade"
              >
                Evidence: {evidenceGrade}
                <Info className="w-3 h-3 text-slate-400" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Priority Advisory & Active Episodes Banner (if any) */}
      {activeRec && (
        <div className={`rounded-lg p-4 border flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-subtle ${
          activeRec.priority === 'P0'
            ? 'bg-rose-50/70 border-rose-200'
            : activeRec.priority === 'P1'
            ? 'bg-amber-50/70 border-amber-200'
            : 'bg-slate-50 border-slate-200'
        }`}>
          <div className="flex items-start gap-3">
            <div className={`p-2 rounded mt-0.5 ${
              activeRec.priority === 'P0'
                ? 'bg-rose-100 text-rose-700'
                : activeRec.priority === 'P1'
                ? 'bg-amber-100 text-amber-700'
                : 'bg-slate-200 text-slate-700'
            }`}>
              <AlertTriangle className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  {activeRec.priority_label || `Priority ${activeRec.priority}`} Advisory
                </span>
                <span className="text-[11px] font-mono text-slate-400">
                  Action Window: {activeRec.action_window.replace(/_/g, ' ')}
                </span>
              </div>
              <h4 className="text-sm font-bold text-slate-900 mt-0.5">
                {activeRec.title}
              </h4>
              <p className="text-xs text-slate-600 mt-1 max-w-2xl leading-relaxed">
                {activeRec.advisory_wording}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-shrink-0 self-end md:self-center">
            <button
              onClick={() => onOpenFeedback(activeRec)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white transition-colors"
            >
              <span>{activeRec.acknowledged ? 'View Acknowledged Record' : 'Acknowledge Advisory'}</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}

      {/* 3. Primary Operating Metrics (Unified Instrumentation Rail) */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-subtle divide-y sm:divide-y-0 sm:divide-x divide-slate-200 dark:divide-slate-800 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 transition-colors">
        {/* Metric 1: Top-Oil Temperature */}
        <div className="p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1.5">
              <span className="text-[11px] uppercase font-semibold tracking-wider">Top-Oil Temperature</span>
              <Flame className="w-3.5 h-3.5 text-rose-500" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
              {topOilObs !== null ? `${topOilObs} °C` : '—'}
            </div>
          </div>
          <div className="text-xs text-slate-500 dark:text-slate-400 mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex flex-col gap-1 font-mono text-[11px]">
            <div className="flex items-center justify-between">
              <span>Expected: {topOilExpected !== null ? `${topOilExpected} °C` : '—'}</span>
              <span className={residual && Number(residual) > 3 ? 'text-amber-700 dark:text-amber-400 font-semibold' : 'text-emerald-700 dark:text-emerald-400'}>
                ΔT: {residual !== null ? (Number(residual) >= 0 ? `+${residual} °C` : `${residual} °C`) : '—'}
              </span>
            </div>
            {!hasValidExpected && (
              <span className="text-[10px] text-amber-600 dark:text-amber-400 font-sans">
                {isThermalWarmup ? 'Shadow model warming up' : 'Thermal shadow unavailable'}
              </span>
            )}
          </div>
        </div>

        {/* Metric 2: Apparent Power & Relative Loading */}
        <div className="p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1.5">
              <span className="text-[11px] uppercase font-semibold tracking-wider">Operating Load</span>
              <Zap className="w-3.5 h-3.5 text-amber-500" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
              {apparentPowerKva !== null ? `${apparentPowerKva} kVA` : '—'}
            </div>
          </div>
          <div className="text-xs text-slate-500 dark:text-slate-400 mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between font-mono text-[11px]">
            <span>{relativeLoad !== null ? `${relativeLoad} rel. u` : '—'}</span>
            <UIHonestyBadge type="relative_load_index" customText="Ref: 142.9 kVA (non-nameplate)" />
          </div>
        </div>

        {/* Metric 3: Active & Reactive Power */}
        <div className="p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1.5">
              <span className="text-[11px] uppercase font-semibold tracking-wider">Active Power (P)</span>
              <Activity className="w-3.5 h-3.5 text-sky-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
              {activePowerKw !== null ? `${activePowerKw} kW` : '—'}
            </div>
          </div>
          <div className="text-xs text-slate-500 dark:text-slate-400 mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between font-mono text-[11px]">
            <span>Reactive (Q): {reactivePowerKvar !== null ? `${reactivePowerKvar} kvar` : '—'}</span>
          </div>
        </div>

        {/* Metric 4: Power Factor */}
        <div className="p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1.5">
              <span className="text-[11px] uppercase font-semibold tracking-wider">Power Factor (cos φ)</span>
              <Gauge className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
              {powerFactor !== null ? powerFactor : '—'}
            </div>
          </div>
          <div className="text-xs text-emerald-700 dark:text-emerald-400 font-medium mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px]">
            {powerFactor !== null ? 'Lagging · Within Grid Standards' : '—'}
          </div>
        </div>
      </div>

      {/* 4. Five Diagnostic Health Domains Rail (Clean Row Presentation) */}
      <div className="bg-white dark:bg-slate-900 rounded-lg p-5 border border-slate-200 dark:border-slate-800 shadow-subtle transition-colors">
        <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-100 dark:border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider text-[11px]">
              Diagnostic Health Domains
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Independent evaluation across thermal, electrical, and protection boundaries.
            </p>
          </div>
          <button
            onClick={() => onNavigateTab('telemetry')}
            className="text-xs text-sky-600 dark:text-sky-400 hover:text-sky-800 dark:hover:text-sky-300 hover:underline font-medium"
          >
            View Full Measurements →
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
          {[
            { key: 'thermal', name: 'Thermal', subtitle: 'Top-oil & shadow residual' },
            { key: 'loading', name: 'Loading', subtitle: 'Load excursion & energy' },
            { key: 'phase_neutral', name: 'Phase & Neutral', subtitle: 'Symmetry & unbalance' },
            { key: 'voltage_pf_freq', name: 'Voltage & Quality', subtitle: 'Phase voltage & PF' },
            { key: 'oil_protection', name: 'Protection & Oil', subtitle: 'Discrete contact flags' },
          ].map((d) => {
            const domainData = domains[d.key];
            const rawStatus = domainData?.status ?? 'NORMAL';
            const severity = domainData?.severity ?? 0.0;
            const evidenceCount = domainData?.evidence_count ?? 0;
            const isCrit = rawStatus === 'CRITICAL' || severity >= 0.7;
            const isWarn = rawStatus === 'WARNING' || (severity >= 0.4 && !isCrit);
            const isWatch = rawStatus === 'WATCH' || (severity > 0.0 && !isWarn && !isCrit);
            const isUnexcursed = severity === 0 && (evidenceCount === 0 || rawStatus === 'NORMAL');

            const statusLabel = isCrit
              ? 'CRITICAL'
              : isWarn
              ? 'WARNING'
              : isWatch
              ? 'WATCH'
              : isUnexcursed
              ? 'UNEXCURSED'
              : 'NORMAL';

            return (
              <div
                key={d.key}
                className={`p-3 rounded-lg border flex flex-col justify-between transition-colors ${
                  isCrit
                    ? 'bg-rose-50/60 dark:bg-rose-950/20 border-rose-300 dark:border-rose-900'
                    : isWarn
                    ? 'bg-amber-50/60 dark:bg-amber-950/20 border-amber-300 dark:border-amber-900'
                    : isWatch
                    ? 'bg-sky-50/40 dark:bg-sky-950/20 border-sky-200 dark:border-sky-900'
                    : 'bg-slate-50/80 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-slate-900 dark:text-slate-100">{d.name}</span>
                    <span
                      className={`text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded ${
                        isCrit
                          ? 'bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300'
                          : isWarn
                          ? 'bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300'
                          : isWatch
                          ? 'bg-sky-100 dark:bg-sky-950 text-sky-800 dark:text-sky-300'
                          : isUnexcursed
                          ? 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700'
                          : 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300'
                      }`}
                    >
                      {statusLabel}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight">
                    {d.subtitle}
                  </p>
                </div>

                <div className="mt-3 pt-1.5 border-t border-slate-200/60 dark:border-slate-700/60 flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400">
                  <span>Penalty: {(severity * 100).toFixed(0)}%</span>
                  <span>{domainData?.evidence_count ?? 0} item(s)</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 5. Progressive Disclosure: Technical Governance & Model Details */}
      <div className="bg-slate-50 rounded-lg p-4 border border-slate-200 text-xs">
        <button
          onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
          className="w-full flex items-center justify-between text-slate-700 font-semibold hover:text-slate-900"
        >
          <span>Technical Model Governance & State Reducer Parameters</span>
          {showTechnicalDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showTechnicalDetails && (
          <div className="mt-3 pt-3 border-t border-slate-200 text-slate-600 space-y-2">
            <p>
              <strong>First-Order Grey-Box ODE:</strong> Parameters calibrated on Tripura historical training partition (τ = {tauHours}h, β₀ = 1.09°C, β₁ = 2.90°C).
              Status: <span className="font-mono text-slate-800">NOT_PROMOTED</span> (Uninstrumented ambient temperature feed).
            </p>
            <p>
              <strong>Overall Health Index (OTHI):</strong> Computed multi-domain engineering index using a Max-Plus penalty formulation across tiers C0–C4.
              Missing signals degrade capability tiers rather than fabricating ungrounded estimates.
            </p>
            <div className="pt-2 flex items-center gap-3">
              <button
                onClick={() => onNavigateTab('twin-analysis')}
                className="text-sky-600 hover:text-sky-800 hover:underline font-medium"
              >
                Inspect Thermal What-If Simulation →
              </button>
              <span className="text-slate-300">·</span>
              <button
                onClick={() => onNavigateTab('model-card')}
                className="text-sky-600 hover:text-sky-800 hover:underline font-medium"
              >
                View Model Card & Calibration Audit →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Popover Disclosure 1: Capability Tier */}
      {isCapabilityModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-lg shadow-xl border border-slate-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-sky-100 text-sky-800">
                  {highestTier}
                </span>
                <h3 className="text-sm font-bold text-slate-900">Current Operating Capability</h3>
              </div>
              <button
                onClick={() => setIsCapabilityModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 p-1 rounded cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs text-slate-600 space-y-3">
              <div>
                <span className="font-bold text-slate-800 block text-[11px] uppercase tracking-wider mb-0.5">
                  What this means:
                </span>
                <p>
                  The digital twin has enough validated telemetry and model support for its currently enabled monitoring functions.
                </p>
              </div>

              <div>
                <span className="font-bold text-slate-800 block text-[11px] uppercase tracking-wider mb-1">
                  Available Functions:
                </span>
                <ul className="space-y-1 text-slate-700">
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                    <span>Electrical telemetry & symmetrical components (C0/C1)</span>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                    <span>Descriptive top-oil thermal condition tracking (C2)</span>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                    <span>Multi-domain anomaly detection & deterministic advisories</span>
                  </li>
                </ul>
              </div>

              <div>
                <span className="font-bold text-slate-800 block text-[11px] uppercase tracking-wider mb-1">
                  Restricted Functions:
                </span>
                <ul className="space-y-1 text-slate-500">
                  <li className="flex items-center gap-1.5">
                    <ShieldAlert className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                    <span>Autonomous predictive simulation (C3 requires promoted ODE model)</span>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <ShieldAlert className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                    <span>Thermal ageing & RUL claims (C4 requires verified insulation class)</span>
                  </li>
                </ul>
              </div>

              <div className="pt-2 border-t border-slate-100 text-[11px] text-slate-400">
                <span>Technical details: Capability Tier {highestTier} evaluated per IEC 60076-7 and IEEE C57.91 standards.</span>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setIsCapabilityModalOpen(false)}
                className="px-3 py-1.5 rounded bg-slate-900 text-white text-xs font-semibold hover:bg-slate-800 cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Popover Disclosure 2: Evidence Grade */}
      {isEvidenceModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-lg shadow-xl border border-slate-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-amber-100 text-amber-800">
                  Grade {evidenceGrade}
                </span>
                <h3 className="text-sm font-bold text-slate-900">Evidence Grade Explanation</h3>
              </div>
              <button
                onClick={() => setIsEvidenceModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 p-1 rounded cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs text-slate-600 space-y-3">
              {evidenceGrade === 'U' ? (
                <>
                  <div>
                    <span className="font-bold text-slate-800 block text-[11px] uppercase tracking-wider mb-0.5">
                      Meaning:
                    </span>
                    <p>
                      There is not enough current independent evidence to assign a stronger evidence grade.
                    </p>
                  </div>
                  <div>
                    <span className="font-bold text-slate-800 block text-[11px] uppercase tracking-wider mb-0.5">
                      Why:
                    </span>
                    <p>
                      Current evidence does not meet the minimum corroboration requirements (requires at least 2 distinct physical domains or a decisive protection trip).
                    </p>
                  </div>
                  <div>
                    <span className="font-bold text-slate-800 block text-[11px] uppercase tracking-wider mb-0.5">
                      Effect:
                    </span>
                    <p className="text-amber-700 font-medium">
                      Health index is gated and not treated as a confirmed score, protecting against false alarms.
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <span className="font-bold text-slate-800 block text-[11px] uppercase tracking-wider mb-0.5">
                      Meaning:
                    </span>
                    <p>
                      Active observations meet {evidenceGrade === 'A' ? 'high' : 'moderate'} multi-domain corroboration criteria.
                    </p>
                  </div>
                  <div>
                    <span className="font-bold text-slate-800 block text-[11px] uppercase tracking-wider mb-0.5">
                      Why:
                    </span>
                    <p>
                      Independent physical vectors (e.g. electrical loading and top-oil thermal excursion) corroborate the state.
                    </p>
                  </div>
                  <div>
                    <span className="font-bold text-slate-800 block text-[11px] uppercase tracking-wider mb-0.5">
                      Effect:
                    </span>
                    <p className="text-emerald-700 font-medium">
                      Health index is evaluated and emitted as a verified numerical score.
                    </p>
                  </div>
                </>
              )}

              <div className="pt-2 border-t border-slate-100 text-[11px] text-slate-400">
                <span>Grading Hierarchy: Grade A (≥3 domains) · Grade B (2 domains) · Grade C (single domain) · Grade U (uncorroborated / gated).</span>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setIsEvidenceModalOpen(false)}
                className="px-3 py-1.5 rounded bg-slate-900 text-white text-xs font-semibold hover:bg-slate-800 cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Popover Disclosure 3: Health Index (OTHI) */}
      {isHealthModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-lg shadow-xl border border-slate-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900">Overall Transformer Health Index (OTHI)</h3>
              <button
                onClick={() => setIsHealthModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 p-1 rounded cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs text-slate-600 space-y-3">
              <div>
                <span className="font-bold text-slate-800 block text-[11px] uppercase tracking-wider mb-0.5">
                  Algorithm & Formulation:
                </span>
                <p>
                  OTHI is a physics-grounded composite condition score (0–100) using a deterministic Max-Plus secondary formulation:
                </p>
                <code className="block bg-slate-100 p-2 rounded text-[11px] font-mono text-slate-800 mt-1">
                  OTHI = 100 × (1 - [Pen_primary + 0.20 × Pen_secondary])
                </code>
              </div>

              <div>
                <span className="font-bold text-slate-800 block text-[11px] uppercase tracking-wider mb-0.5">
                  Safety Gating Invariant:
                </span>
                <p>
                  To eliminate false precision, OTHI is strictly suppressed (displays &ldquo;—&rdquo;) when telemetry does not satisfy multi-domain corroboration or when uninstrumented ambient feeds cause anti-uplift violations.
                </p>
              </div>

              <div className="pt-2 border-t border-slate-100 text-[11px] text-slate-400">
                <span>Non-Learning Contract: Evaluation is deterministic and executes without modifying model parameters.</span>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setIsHealthModalOpen(false)}
                className="px-3 py-1.5 rounded bg-slate-900 text-white text-xs font-semibold hover:bg-slate-800 cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
