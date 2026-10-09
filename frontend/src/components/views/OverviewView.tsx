import React, { useState } from 'react';
import {
  Flame,
  Zap,
  Gauge,
  ArrowRight,
  ArrowUpRight,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Info,
  X,
  CheckCircle2,
  ShieldAlert,
  Activity,
} from 'lucide-react';

import {
  TwinState,
  OTHIBundle,
  CapabilityManifest,
  MaintenanceRecommendation,
  AnomalyEpisode,
  CanonicalEvent,
} from '../../types/contracts';
import { UIHonestyBadge } from '../common/UIHonestyBadge';
import { TrendChart, readSignal, formatUtcTick } from '../common/TrendChart';

interface OverviewViewProps {
  assetId: string;
  twinState: TwinState | null;
  health: OTHIBundle | null;
  capabilities: CapabilityManifest | null;
  recommendations: MaintenanceRecommendation[];
  episodes: AnomalyEpisode[];
  historyEvents?: CanonicalEvent[];
  onNavigateTab: (tab: string) => void;
  onOpenFeedback: (rec: MaintenanceRecommendation) => void;
}

/** Presentational metric tile (eyebrow label, large value, unit, contextual footer). */
const MetricTile: React.FC<{
  label: string;
  icon: React.ReactNode;
  value: string | null;
  unit?: string;
  footer: React.ReactNode;
  onOpen?: () => void;
  openTitle?: string;
}> = ({ label, icon, value, unit, footer, onOpen, openTitle }) => (
  <div className="bg-surface p-5 flex flex-col justify-between min-h-[176px]">
    <div>
      <div className="flex items-center justify-between gap-2 pb-3 border-b border-line">
        <span className="eyebrow flex items-center gap-2">
          <span className="text-muted">{icon}</span>
          {label}
        </span>
        {onOpen && (
          <button
            onClick={onOpen}
            title={openTitle}
            className="text-muted hover:text-accent transition-colors -m-1 p-1"
          >
            <ArrowUpRight className="w-4 h-4" strokeWidth={1.75} />
          </button>
        )}
      </div>
      <div className="mt-4 flex items-baseline gap-1.5">
        <span className={`metric-value text-[38px] ${value === null ? 'text-faint font-normal' : ''}`}>
          {value !== null ? value : '—'}
        </span>
        {value !== null && unit && <span className="metric-unit">{unit}</span>}
      </div>
    </div>
    <div className="mt-4 text-[11px] text-muted">{footer}</div>
  </div>
);

type TrendMetric = 'topOil' | 'ambient' | 'activePower' | 'apparentPower';

export const OverviewView: React.FC<OverviewViewProps> = ({
  assetId,
  twinState,
  health,
  capabilities,
  recommendations,
  episodes,
  historyEvents = [],
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


  // Presentation-only: trend series read directly from recorded history events
  const [trendMetric, setTrendMetric] = useState<TrendMetric>('topOil');
  const trendOptions: Record<TrendMetric, { label: string; unit: string; ids: string[] }> = {
    topOil: { label: 'Top-oil', unit: '°C', ids: ['top_oil_temperature'] },
    ambient: { label: 'Ambient', unit: '°C', ids: ['ambient_temperature'] },
    activePower: { label: 'Active power', unit: 'kW', ids: ['active_power_total', 'active_power'] },
    apparentPower: { label: 'Apparent power', unit: 'kVA', ids: ['apparent_power_total', 'apparent_power'] },
  };
  const activeTrend = trendOptions[trendMetric];
  const trendData = historyEvents.map((ev) => ({
    t: formatUtcTick(ev.event_time_utc),
    value: readSignal(ev.measurements, activeTrend.ids),
  }));
  const trendHasData = trendData.some((d) => d.value !== null);
  const trendRange =
    historyEvents.length > 0
      ? `${formatUtcTick(historyEvents[0].event_time_utc)} → ${formatUtcTick(
          historyEvents[historyEvents.length - 1].event_time_utc
        )} UTC`
      : null;

  const isScoreShown = othiScore !== null && !isGated && evidenceGrade !== 'U';
  const asOfIso = twinState?.event_time_watermark_utc || twinState?.state_time_utc || null;
  // Hide the unseeded epoch-0 placeholder watermark
  const asOf = asOfIso && new Date(asOfIso).getTime() > 0
    ? new Date(asOfIso).toISOString().replace('T', ' ').slice(0, 16) + ' UTC'
    : null;

  const priorityChip = (p: string) =>
    p === 'P0' ? 'chip-crit' : p === 'P1' ? 'chip-warn' : 'chip-neutral';

  return (
    <div className="space-y-8">
      {/* 1. Page Header: Asset identity, capability & condition flags */}
      <div className="page-header">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mb-3">
            <span className="eyebrow text-ink">{assetId}</span>
            <span className="text-faint">·</span>
            <span className="eyebrow">Agartala Substation (33/11kV)</span>
          </div>
          <h1 className="page-title">Condition Overview</h1>
          <p className="text-[13px] text-muted mt-2.5 max-w-2xl">
            Live transformer telemetry, thermal condition tracking, anomaly detection, and maintenance guidance.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 lg:justify-end">
          <button
            onClick={() => setIsCapabilityModalOpen(true)}
            className="btn btn-ghost font-medium group"
            title="Click to understand Current Operating Capability"
          >
            <span className="eyebrow text-[11px]">Capability</span>
            <span className="text-ink">{getTierTitle(highestTier)}</span>
            <Info className="w-3.5 h-3.5 text-faint group-hover:text-accent" />
          </button>
          {activeEpisodeCount > 0 && (
            <button
              onClick={() => onNavigateTab('anomalies')}
              className="btn bg-warn/10 text-warn hover:bg-warn/15"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              {activeEpisodeCount} Active {activeEpisodeCount === 1 ? 'Anomaly' : 'Anomalies'}
            </button>
          )}
          {isGated && <UIHonestyBadge type="GATED_EVIDENCE" />}
        </div>
      </div>

      {/* 2. Primary Health + Telemetry Block | Advisories Rail */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-px bg-line border border-line rounded-card overflow-hidden">
          {/* Health Index (visual anchor) */}
          <div className="card-inverse rounded-none sm:col-span-2 xl:col-span-1 xl:row-span-2 p-6 flex flex-col justify-between min-h-[260px]">
            <div>
              <button
                onClick={() => setIsHealthModalOpen(true)}
                className="w-full flex items-center justify-between pb-3 border-b border-on-inverse/15 group"
                title="Click to understand Health Index (OTHI)"
              >
                <span className="text-[11px] font-semibold uppercase tracking-eyebrow text-on-inverse/80 group-hover:text-on-inverse">
                  Health Index · OTHI
                </span>
                <Info className="w-3.5 h-3.5 text-on-inverse/65 group-hover:text-on-inverse" />
              </button>

              <div className="mt-6">
                {isScoreShown ? (
                  <div className="flex items-baseline gap-2">
                    <span className="metric-value text-[84px] text-on-inverse">
                      {Math.round(Number(othiScore))}
                    </span>
                    <span className="text-base text-on-inverse/65">/100</span>
                  </div>
                ) : (
                  <>
                    <span className="metric-value text-[84px] font-normal text-on-inverse/55">—</span>
                    <span className="block text-xs text-on-inverse/80 mt-3">
                      Insufficient current evidence
                    </span>
                  </>
                )}
              </div>

              <div className="mt-5">
                {healthStatus && isScoreShown ? (
                  <span className="inline-flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.12em] text-on-inverse">
                    <span
                      className={`dot w-2 h-2 ${
                        healthStatus === 'NORMAL'
                          ? 'bg-ok'
                          : healthStatus === 'WATCH'
                          ? 'bg-warn'
                          : 'bg-crit'
                      }`}
                    />
                    {healthStatus}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-on-inverse/80">
                    <span className="dot w-2 h-2 border border-on-inverse/50" />
                    Status: Insufficient evidence
                  </span>
                )}
              </div>
            </div>

            <div className="mt-6 pt-3 border-t border-on-inverse/15 space-y-1.5 text-[11px] text-on-inverse/72">
              <button
                onClick={() => setIsEvidenceModalOpen(true)}
                className="flex items-center gap-1.5 text-on-inverse/85 hover:text-on-inverse font-medium"
                title="Click to understand Evidence Grade"
              >
                Evidence grade <span className="font-mono font-semibold">{evidenceGrade}</span>
                <Info className="w-3 h-3" />
              </button>
              <div>
                {isScoreShown ? 'Composite health index' : 'Gated (requires ≥2 corroborated domains)'}
              </div>
              {asOf && <div className="font-mono text-[11px] text-on-inverse/65">As of {asOf}</div>}
            </div>
          </div>

          {/* Top-Oil Temperature */}
          <MetricTile
            label="Top-Oil Temperature"
            icon={<Flame className="w-3.5 h-3.5" strokeWidth={1.75} />}
            value={topOilObs}
            unit="°C"
            onOpen={() => onNavigateTab('twin-analysis')}
            openTitle="Open thermal analysis"
            footer={
              <div className="space-y-1">
                <div className="flex items-center justify-between gap-2 font-mono">
                  <span>Expected {topOilExpected !== null ? `${topOilExpected} °C` : '—'}</span>
                  <span className={residual && Number(residual) > 3 ? 'text-warn font-semibold' : 'text-muted'}>
                    ΔT {residual !== null ? (Number(residual) >= 0 ? `+${residual} °C` : `${residual} °C`) : '—'}
                  </span>
                </div>
                {!hasValidExpected && (
                  <span className="block text-[11px] text-warn">
                    {isThermalWarmup ? 'Shadow model warming up' : 'Thermal shadow unavailable'}
                  </span>
                )}
              </div>
            }
          />

          {/* Operating Load */}
          <MetricTile
            label="Operating Load"
            icon={<Zap className="w-3.5 h-3.5" strokeWidth={1.75} />}
            value={apparentPowerKva}
            unit="kVA"
            onOpen={() => onNavigateTab('telemetry')}
            openTitle="Open electrical telemetry"
            footer={
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono">{relativeLoad !== null ? `${relativeLoad} rel. u` : '—'}</span>
                <UIHonestyBadge type="relative_load_index" customText="Ref: 142.9 kVA (non-nameplate)" />
              </div>
            }
          />

          {/* Active Power */}
          <MetricTile
            label="Active Power (P)"
            icon={<Activity className="w-3.5 h-3.5" strokeWidth={1.75} />}
            value={activePowerKw}
            unit="kW"
            onOpen={() => onNavigateTab('telemetry')}
            openTitle="Open electrical telemetry"
            footer={
              <span className="font-mono">
                Reactive (Q) {reactivePowerKvar !== null ? `${reactivePowerKvar} kvar` : '—'}
              </span>
            }
          />

          {/* Power Factor */}
          <MetricTile
            label="Power Factor (cos φ)"
            icon={<Gauge className="w-3.5 h-3.5" strokeWidth={1.75} />}
            value={powerFactor}
            onOpen={() => onNavigateTab('telemetry')}
            openTitle="Open electrical telemetry"
            footer={
              <span className={powerFactor !== null ? 'text-ink-2 inline-flex items-center gap-1.5' : ''}>
                {powerFactor !== null && <span className="dot bg-ok" />}
                {powerFactor !== null ? 'Lagging · Within Grid Standards' : '—'}
              </span>
            }
          />
        </div>

        {/* Advisories & Episodes Rail */}
        <div className="lg:col-span-4 flex flex-col">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 mb-3">
            <h2 className="section-title sm:whitespace-nowrap">Maintenance advisories</h2>
            <button onClick={() => onNavigateTab('maintenance')} className="link">
              View all
            </button>
          </div>
          <div className="card-muted flex-1 p-5 flex flex-col">
            {recommendations.length === 0 ? (
              <div className="flex-1 flex flex-col items-start justify-center py-6">
                <span className="chip chip-ok mb-3">
                  <CheckCircle2 className="w-3 h-3" /> Nominal
                </span>
                <p className="card-title">No active maintenance advisories</p>
                <p className="text-xs text-muted mt-1">
                  No safety limit excursions or maintenance actions are currently flagged.
                </p>
              </div>
            ) : (
              <ul className="space-y-4 flex-1">
                {recommendations.slice(0, 3).map((rec, idx) => (
                  <li key={rec.recommendation_id} className={idx > 0 ? 'pt-4 border-t border-line' : ''}>
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span className={`chip ${priorityChip(rec.priority)}`}>
                        {rec.priority_label || `Priority ${rec.priority}`}
                      </span>
                      <span className="text-[11px] font-mono text-muted truncate">
                        {rec.action_window.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <h3 className="card-title">{rec.title}</h3>
                    {rec === activeRec && (
                      <p className="text-xs text-muted mt-1 leading-relaxed line-clamp-3">
                        {rec.advisory_wording}
                      </p>
                    )}
                    <button
                      onClick={() => onOpenFeedback(rec)}
                      className="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold text-ink-2 hover:text-accent"
                    >
                      {rec.acknowledged ? 'View Acknowledged Record' : 'Acknowledge Advisory'}
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <div className="mt-5 pt-4 border-t border-line space-y-3">
              <button
                onClick={() => onNavigateTab('anomalies')}
                className="w-full flex items-center justify-between text-xs group"
              >
                <span className="flex items-center gap-2 text-ink-2 group-hover:text-ink">
                  <span className={`dot w-2 h-2 ${activeEpisodeCount > 0 ? 'bg-warn' : 'bg-ok'}`} />
                  Active anomaly episodes
                </span>
                <span className="font-mono font-semibold text-ink num">{activeEpisodeCount}</span>
              </button>
              <button
                onClick={() => onNavigateTab('maintenance')}
                className="btn btn-accent w-full rounded-full py-2.5 text-[13px] font-medium"
              >
                Open advisories
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Trend Chart | Diagnostic Domains */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8 flex flex-col">
          <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
            <h2 className="section-title">Telemetry trend</h2>
            <div className="segmented">
              {(Object.keys(trendOptions) as TrendMetric[]).map((k) => (
                <button key={k} data-active={trendMetric === k} onClick={() => setTrendMetric(k)}>
                  {trendOptions[k].label}
                </button>
              ))}
            </div>
          </div>
          <div className="card-muted flex-1 p-5">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <span className="eyebrow text-ink-2">
                {activeTrend.label} · {activeTrend.unit}
              </span>
              <span className="text-[11px] font-mono text-muted">
                {trendRange ? `${historyEvents.length} recorded frames · ${trendRange}` : 'No recorded frames'}
              </span>
            </div>
            {trendHasData ? (
              <TrendChart
                data={trendData}
                xKey="t"
                series={[{ key: 'value', label: activeTrend.label }]}
                unit={activeTrend.unit}
                area
                height={330}
              />
            ) : (
              <div className="h-[330px] flex flex-col items-center justify-center text-center border border-dashed border-line-strong rounded-card">
                <p className="text-xs font-medium text-ink-2">No {activeTrend.label.toLowerCase()} history yet</p>
                <p className="text-[11px] text-muted mt-1 max-w-xs">
                  Start the Digital Twin and step telemetry to record frames from the history API.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Five Diagnostic Health Domains */}
        <div className="lg:col-span-4 flex flex-col">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 mb-3">
            <h2 className="section-title sm:whitespace-nowrap">Diagnostic domains</h2>
            <button onClick={() => onNavigateTab('telemetry')} className="link">
              View Full Measurements →
            </button>
          </div>
          <div className="card flex-1 divide-y divide-line">
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

              const chipClass = isCrit
                ? 'chip-crit'
                : isWarn
                ? 'chip-warn'
                : isWatch
                ? 'chip-accent'
                : isUnexcursed
                ? 'chip-outline'
                : 'chip-ok';
              const barClass = isCrit ? 'bg-crit' : isWarn ? 'bg-warn' : isWatch ? 'bg-accent' : 'bg-ok';

              return (
                <div key={d.key} className="px-4 py-3.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-[13.5px] font-medium text-ink">{d.name}</div>
                      <div className="text-[11px] text-muted leading-tight mt-0.5">{d.subtitle}</div>
                    </div>
                    <span className={`chip ${chipClass}`}>{statusLabel}</span>
                  </div>
                  <div className="mt-2.5 flex items-center gap-3 text-[11px] text-muted font-mono">
                    <div className="flex-1 h-[3px] rounded-full bg-surface-3 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${barClass}`}
                        style={{ width: `${Math.min(severity * 100, 100)}%` }}
                      />
                    </div>
                    <span className="num">Penalty {(severity * 100).toFixed(0)}%</span>
                    <span className="text-faint">·</span>
                    <span className="num">{domainData?.evidence_count ?? 0} item(s)</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 4. Progressive Disclosure: Technical Governance & Model Details */}
      <div className="card-muted px-5 py-4 text-xs">
        <button
          onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
          className="w-full flex items-center justify-between gap-3 text-ink-2 font-medium hover:text-ink text-left"
        >
          <span className="flex items-center gap-3">
            <span className="eyebrow hidden sm:inline">Governance</span>
            <span>Technical Model Governance & State Reducer Parameters</span>
          </span>
          {showTechnicalDetails ? <ChevronUp className="w-4 h-4 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 flex-shrink-0" />}
        </button>

        {showTechnicalDetails && (
          <div className="mt-4 pt-4 border-t border-line text-muted space-y-2.5 leading-relaxed">
            <p>
              <strong className="text-ink font-semibold">First-Order Grey-Box ODE:</strong> Parameters calibrated on Tripura historical training partition (τ = {tauHours}h, β₀ = 1.09°C, β₁ = 2.90°C).
              Status: <span className="font-mono text-ink">NOT_PROMOTED</span> (Uninstrumented ambient temperature feed).
            </p>
            <p>
              <strong className="text-ink font-semibold">Overall Health Index (OTHI):</strong> Computed multi-domain engineering index using a Max-Plus penalty formulation across tiers C0–C4.
              Missing signals degrade capability tiers rather than fabricating ungrounded estimates.
            </p>
            <div className="pt-1 flex flex-wrap items-center gap-3">
              <button onClick={() => onNavigateTab('twin-analysis')} className="link">
                Inspect Thermal What-If Simulation →
              </button>
              <span className="text-faint">·</span>
              <button onClick={() => onNavigateTab('model-card')} className="link">
                View Model Card & Calibration Audit →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Popover Disclosure 1: Capability Tier */}
      {isCapabilityModalOpen && (
        <div className="modal-backdrop">
          <div className="modal max-w-md w-full p-6 space-y-5">
            <div className="flex items-start justify-between pb-3 border-b border-line">
              <div>
                <span className="chip chip-neutral font-mono mb-2">{highestTier}</span>
                <h3 className="text-lg font-medium tracking-tight">Current Operating Capability</h3>
              </div>
              <button
                onClick={() => setIsCapabilityModalOpen(false)}
                className="icon-btn border-transparent"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs text-muted space-y-4 leading-relaxed">
              <div>
                <span className="eyebrow block mb-1.5">What this means</span>
                <p className="text-ink-2">
                  The digital twin has enough validated telemetry and model support for its currently enabled monitoring functions.
                </p>
              </div>

              <div>
                <span className="eyebrow block mb-2">Available Functions</span>
                <ul className="space-y-1.5 text-ink-2">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-ok flex-shrink-0" />
                    <span>Three-phase electrical telemetry & unbalance metrics (C0/C1)</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-ok flex-shrink-0" />
                    <span>Descriptive top-oil thermal condition tracking (C2)</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-ok flex-shrink-0" />
                    <span>Multi-domain anomaly detection & deterministic advisories</span>
                  </li>
                </ul>
              </div>

              <div>
                <span className="eyebrow block mb-2">Restricted Functions</span>
                <ul className="space-y-1.5">
                  <li className="flex items-center gap-2">
                    <ShieldAlert className="w-3.5 h-3.5 text-warn flex-shrink-0" />
                    <span>Autonomous predictive simulation (C3 requires promoted ODE model)</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <ShieldAlert className="w-3.5 h-3.5 text-warn flex-shrink-0" />
                    <span>Thermal ageing (C4 requires verified insulation class)</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <ShieldAlert className="w-3.5 h-3.5 text-warn flex-shrink-0" />
                    <span>Operational RUL (Unavailable: no validated initial degradation state &amp; life-outcome data)</span>
                  </li>
                </ul>
              </div>

              <div className="pt-3 border-t border-line text-[11px] text-muted">
                <span>Technical details: Capability Tier {highestTier} evaluated per IEC 60076-7 and IEEE C57.91 standards.</span>
              </div>
            </div>

            <div className="flex justify-end">
              <button onClick={() => setIsCapabilityModalOpen(false)} className="btn btn-primary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Popover Disclosure 2: Evidence Grade */}
      {isEvidenceModalOpen && (
        <div className="modal-backdrop">
          <div className="modal max-w-md w-full p-6 space-y-5">
            <div className="flex items-start justify-between pb-3 border-b border-line">
              <div>
                <span className="chip chip-neutral font-mono mb-2">Grade {evidenceGrade}</span>
                <h3 className="text-lg font-medium tracking-tight">Evidence Grade Explanation</h3>
              </div>
              <button
                onClick={() => setIsEvidenceModalOpen(false)}
                className="icon-btn border-transparent"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs text-ink-2 space-y-4 leading-relaxed">
              {evidenceGrade === 'U' ? (
                <>
                  <div>
                    <span className="eyebrow block mb-1.5">Meaning</span>
                    <p>
                      There is not enough current independent evidence to assign a stronger evidence grade.
                    </p>
                  </div>
                  <div>
                    <span className="eyebrow block mb-1.5">Why</span>
                    <p>
                      Current evidence does not meet the minimum corroboration requirements (requires at least 2 distinct physical domains or a decisive protection trip).
                    </p>
                  </div>
                  <div>
                    <span className="eyebrow block mb-1.5">Effect</span>
                    <p className="text-warn font-medium">
                      Health index is gated and not treated as a confirmed score, protecting against false alarms.
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <span className="eyebrow block mb-1.5">Meaning</span>
                    <p>
                      Active observations meet {evidenceGrade === 'A' ? 'high' : 'moderate'} multi-domain corroboration criteria.
                    </p>
                  </div>
                  <div>
                    <span className="eyebrow block mb-1.5">Why</span>
                    <p>
                      Independent physical vectors (e.g. electrical loading and top-oil thermal excursion) corroborate the state.
                    </p>
                  </div>
                  <div>
                    <span className="eyebrow block mb-1.5">Effect</span>
                    <p className="text-ok font-medium">
                      Health index is evaluated and emitted as a verified numerical score.
                    </p>
                  </div>
                </>
              )}

              <div className="pt-3 border-t border-line text-[11px] text-muted">
                <span>Grading Hierarchy: Grade A (≥3 domains) · Grade B (2 domains) · Grade C (single domain) · Grade U (uncorroborated / gated).</span>
              </div>
            </div>

            <div className="flex justify-end">
              <button onClick={() => setIsEvidenceModalOpen(false)} className="btn btn-primary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Popover Disclosure 3: Health Index (OTHI) */}
      {isHealthModalOpen && (
        <div className="modal-backdrop">
          <div className="modal max-w-md w-full p-6 space-y-5">
            <div className="flex items-start justify-between pb-3 border-b border-line">
              <h3 className="text-lg font-medium tracking-tight">Overall Transformer Health Index (OTHI)</h3>
              <button
                onClick={() => setIsHealthModalOpen(false)}
                className="icon-btn border-transparent"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs text-ink-2 space-y-4 leading-relaxed">
              <div>
                <span className="eyebrow block mb-1.5">Algorithm & Formulation</span>
                <p>
                  OTHI is a physics-grounded composite condition score (0–100) using a deterministic Max-Plus secondary formulation:
                </p>
                <code className="block bg-surface-2 border border-line p-2.5 rounded text-[11px] font-mono text-ink mt-2">
                  OTHI = 100 × (1 - [Pen_primary + 0.20 × Pen_secondary])
                </code>
              </div>

              <div>
                <span className="eyebrow block mb-1.5">Safety Gating Invariant</span>
                <p>
                  To eliminate false precision, OTHI is strictly suppressed (displays &ldquo;—&rdquo;) when telemetry does not satisfy multi-domain corroboration or when uninstrumented ambient feeds cause anti-uplift violations.
                </p>
              </div>

              <div className="pt-3 border-t border-line text-[11px] text-muted">
                <span>Non-Learning Contract: Evaluation is deterministic and executes without modifying model parameters.</span>
              </div>
            </div>

            <div className="flex justify-end">
              <button onClick={() => setIsHealthModalOpen(false)} className="btn btn-primary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
