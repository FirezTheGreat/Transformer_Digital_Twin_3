import React from 'react';
import {
  Activity,
  Flame,
  Zap,
  Gauge,
  ShieldAlert,
  ArrowRight,
  TrendingUp,
  Layers,
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
  const othiScore = health?.othi_score ?? 67;
  const isGated = health?.is_gated ?? false;
  const healthStatus = health?.status ?? 'WATCH';
  const evidenceGrade = health?.evidence_grade ?? 'A';
  const highestTier = capabilities?.highest_tier ?? 'C2';

  const obs = twinState?.current_observations ?? {};
  const derived = twinState?.derived_electrical;

  const topOilObs = obs['top_oil_temperature']?.value ?? 74.8;
  const topOilExpected = twinState?.thermal_latent?.top_oil_expected_degc ?? 70.5;
  const apparentPowerKva = derived?.apparent_power_derived_kva ?? 78.01;
  const activePowerKw = obs['active_power_total']?.value ?? 74.2;
  const reactivePowerKvar = obs['reactive_power_total']?.value ?? 24.1;
  const powerFactor = derived?.power_factor_derived ?? 0.951;
  const relativeLoad = derived?.relative_load_index ?? 0.78;
  const tauHours = twinState?.thermal_latent?.time_constant_tau_hours ?? 0.5;

  const activeRecsCount = recommendations.length;
  const openEpisodesCount = episodes.length;

  return (
    <div className="space-y-6">
      {/* 1. Header Banner & Gating / Fallback Alerts */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-5 border-b border-[#d8e6f2] pb-6">
        <div>
          <div className="flex items-center gap-2.5 mb-2">
            <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-[#627d98]">
              DISTRIBUTION ASSET OVERVIEW
            </span>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[#0e1824] text-white text-[11px] font-semibold shadow-sm">
              Tier {highestTier} Active
            </span>
            {isGated && <UIHonestyBadge type="GATED_EVIDENCE" />}
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-[#0e1824] tracking-tight">
            {assetId} Substation
          </h2>
          <p className="text-xs sm:text-sm text-[#627d98] font-normal mt-1">
            Rated kVA: UNVERIFIED · ONAN Distribution Substation · Agartala Feeder
          </p>
        </div>

        {/* Quick actions aligned with headline baseline */}
        <div className="flex items-center gap-2.5 flex-shrink-0">
          <button
            onClick={() => onNavigateTab('twin-analysis')}
            className="h-10 inline-flex items-center gap-1.5 px-4 rounded-xl bg-white hover:bg-[#eff5fb] text-[#0e1824] text-xs font-semibold border border-[#d2e2ef] shadow-sm transition-all active:scale-95"
          >
            <TrendingUp className="w-3.5 h-3.5 text-[#0284c7]" />
            What-If Simulator →
          </button>
          <button
            onClick={() => onNavigateTab('maintenance')}
            className="h-10 inline-flex items-center gap-2 px-4 rounded-xl bg-[#0e1824] hover:bg-[#1a2c3f] text-white text-xs font-semibold shadow-sm transition-all active:scale-95"
          >
            <span>Advisories ({activeRecsCount})</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 2. Top Metric Cards Row: OTHI Health Card + Primary Operational Vectors */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        {/* Left: OTHI Health Card */}
        <div className="lg:col-span-5 bg-gradient-to-br from-[#eaf2fa] to-[#dceaf7] border border-[#cbe0f1] rounded-2xl p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-bold tracking-[0.18em] uppercase text-[#627d98]">
                OTHI HEALTH SCORE
              </span>
              <span
                className={`text-[10px] uppercase font-bold tracking-wider px-2.5 py-0.5 rounded-full ${
                  healthStatus === 'NORMAL'
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                    : healthStatus === 'WATCH'
                    ? 'bg-amber-100 text-amber-800 border border-amber-200'
                    : 'bg-rose-100 text-rose-800 border border-rose-200'
                }`}
              >
                {healthStatus}
              </span>
            </div>

            <div className="flex items-baseline gap-2.5 mt-1">
              <span className="text-5xl sm:text-6xl font-extrabold text-[#0e1824] leading-none font-sans">
                {isGated ? '--' : Number(othiScore).toFixed(1)}
              </span>
              <span className="text-sm font-bold text-[#627d98]">/ 100</span>
            </div>

            <p className="text-xs text-[#354e6b] mt-3 font-normal leading-relaxed">
              Multi-domain gated health index across 5 canonical domains with maximum penalty gating.
            </p>
          </div>

          <div className="mt-6 pt-3.5 border-t border-[#c6dcee] flex items-center justify-between text-xs text-[#486581]">
            <span className="font-semibold text-[#1c3c5c]">Grade {evidenceGrade} Evidence Quality</span>
            <button
              onClick={() => onNavigateTab('anomalies')}
              className="text-[#0284c7] hover:text-[#0369a1] hover:underline font-bold text-xs"
            >
              {openEpisodesCount} open episode(s) →
            </button>
          </div>
        </div>

        {/* Right: Primary Metrics Grid (P, Q, S, To, u) */}
        <div className="lg:col-span-7 grid grid-cols-2 sm:grid-cols-3 gap-4">
          {/* Card 1: Top-Oil Temperature */}
          <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm flex flex-col justify-between hover:border-[#b8d4eb] hover:shadow-md transition-all">
            <div>
              <div className="flex items-center justify-between text-[#627d98] mb-2.5">
                <span className="text-[10px] uppercase font-bold tracking-wider">TOP-OIL TEMP</span>
                <div className="w-7 h-7 rounded-lg bg-rose-50 border border-rose-100 flex items-center justify-center flex-shrink-0">
                  <Flame className="w-3.5 h-3.5 text-rose-500" />
                </div>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold font-sans text-[#0e1824] tracking-tight">
                {String(topOilObs)} °C
              </div>
            </div>
            <div className="text-[11px] text-[#627d98] mt-3.5 pt-2.5 border-t border-[#f1f6fb] font-mono">
              Expected: {topOilExpected} °C
            </div>
          </div>

          {/* Card 2: Apparent Power & Relative Load Index */}
          <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm flex flex-col justify-between hover:border-[#b8d4eb] hover:shadow-md transition-all">
            <div>
              <div className="flex items-center justify-between text-[#627d98] mb-2.5">
                <span className="text-[10px] uppercase font-bold tracking-wider">APPARENT POWER</span>
                <div className="w-7 h-7 rounded-lg bg-amber-50 border border-amber-100 flex items-center justify-center flex-shrink-0">
                  <Zap className="w-3.5 h-3.5 text-amber-500" />
                </div>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold font-sans text-[#0e1824] tracking-tight">
                {Number(apparentPowerKva).toFixed(1)} kVA
              </div>
            </div>
            <div className="flex items-center justify-between text-[11px] text-[#627d98] mt-3.5 pt-2.5 border-t border-[#f1f6fb] font-mono">
              <span>{Number(relativeLoad).toFixed(2)} p.u.</span>
              <UIHonestyBadge type="relative_load_index" customText="u" />
            </div>
          </div>

          {/* Card 3: Active Power */}
          <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm flex flex-col justify-between hover:border-[#b8d4eb] hover:shadow-md transition-all">
            <div>
              <div className="flex items-center justify-between text-[#627d98] mb-2.5">
                <span className="text-[10px] uppercase font-bold tracking-wider">ACTIVE POWER (P)</span>
                <div className="w-7 h-7 rounded-lg bg-emerald-50 border border-emerald-100 flex items-center justify-center flex-shrink-0">
                  <Activity className="w-3.5 h-3.5 text-emerald-600" />
                </div>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold font-sans text-[#0e1824] tracking-tight">
                {String(activePowerKw)} kW
              </div>
            </div>
            <div className="text-[11px] text-[#627d98] mt-3.5 pt-2.5 border-t border-[#f1f6fb] font-mono">
              Q: {String(reactivePowerKvar)} kvar
            </div>
          </div>

          {/* Card 4: Power Factor */}
          <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm flex flex-col justify-between hover:border-[#b8d4eb] hover:shadow-md transition-all">
            <div>
              <div className="flex items-center justify-between text-[#627d98] mb-2.5">
                <span className="text-[10px] uppercase font-bold tracking-wider">POWER FACTOR</span>
                <div className="w-7 h-7 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center flex-shrink-0">
                  <Gauge className="w-3.5 h-3.5 text-indigo-500" />
                </div>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold font-sans text-[#0e1824] tracking-tight">
                {Number(powerFactor).toFixed(3)}
              </div>
            </div>
            <div className="text-[11px] text-emerald-700 font-semibold mt-3.5 pt-2.5 border-t border-[#f1f6fb]">
              Lagging · Compliant
            </div>
          </div>

          {/* Card 5: Thermal ODE Time Constant */}
          <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm flex flex-col justify-between hover:border-[#b8d4eb] hover:shadow-md transition-all">
            <div>
              <div className="flex items-center justify-between text-[#627d98] mb-2.5">
                <span className="text-[10px] uppercase font-bold tracking-wider">THERMAL INERTIA (τ)</span>
                <div className="w-7 h-7 rounded-lg bg-sky-50 border border-sky-100 flex items-center justify-center flex-shrink-0">
                  <TrendingUp className="w-3.5 h-3.5 text-[#0284c7]" />
                </div>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold font-sans text-[#0e1824] tracking-tight">
                {Number(tauHours).toFixed(2)} hrs
              </div>
            </div>
            <div className="text-[11px] text-[#627d98] mt-3.5 pt-2.5 border-t border-[#f1f6fb] font-mono">
              β₀: 1.09°C · β₁: 2.90°C
            </div>
          </div>

          {/* Card 6: Dynamic Tier Confinement */}
          <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm flex flex-col justify-between hover:border-[#b8d4eb] hover:shadow-md transition-all">
            <div>
              <div className="flex items-center justify-between text-[#627d98] mb-2.5">
                <span className="text-[10px] uppercase font-bold tracking-wider">CAPABILITY TIER</span>
                <div className="w-7 h-7 rounded-lg bg-sky-50 border border-sky-100 flex items-center justify-center flex-shrink-0">
                  <Layers className="w-3.5 h-3.5 text-[#0284c7]" />
                </div>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold font-sans text-[#0e1824] tracking-tight">
                {highestTier}
              </div>
            </div>
            <div className="text-[11px] text-[#486581] font-mono mt-3.5 pt-2.5 border-t border-[#f1f6fb]">
              {highestTier === 'C2' ? 'C2 Top-Oil Monitoring (Predictive Gated)' : 'C3 Predictive Active'}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Five Health Domains Quick Status Bar */}
      <div className="bg-white rounded-3xl p-6 shadow-card border border-[#d8e6f2]">
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-[#edf4fa]">
          <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f]">
            5 CANONICAL HEALTH DOMAINS STATUS
          </span>
          <button
            onClick={() => onNavigateTab('telemetry')}
            className="text-xs text-[#0284c7] hover:underline font-semibold"
          >
            View Telemetry & Vectors →
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {[
            { key: 'thermal', name: 'Thermal', icon: <Flame className="w-3.5 h-3.5 text-rose-500" /> },
            { key: 'loading', name: 'Loading', icon: <Zap className="w-3.5 h-3.5 text-amber-500" /> },
            { key: 'phase_neutral', name: 'Phase & Neutral', icon: <Activity className="w-3.5 h-3.5 text-[#0284c7]" /> },
            { key: 'voltage_pf_freq', name: 'Voltage & PF', icon: <Gauge className="w-3.5 h-3.5 text-indigo-500" /> },
            { key: 'oil_protection', name: 'Protection/Oil', icon: <ShieldAlert className="w-3.5 h-3.5 text-emerald-600" /> },
          ].map((d) => {
            const domainData = health?.domains?.[d.key];
            const status = domainData?.status ?? 'NORMAL';
            const isWarn = status === 'WARNING';
            const isCrit = status === 'CRITICAL';
            const isWatch = status === 'WATCH';

            return (
              <div
                key={d.key}
                className="bg-[#f8fbfe] p-3 rounded-2xl border border-[#e2edf6] text-center flex flex-col items-center justify-between"
              >
                <div className="flex items-center gap-1.5 mb-1.5">
                  {d.icon}
                  <span className="text-xs font-semibold text-[#0e1824]">{d.name}</span>
                </div>
                <span
                  className={`text-[9px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full ${
                    isCrit
                      ? 'bg-rose-100 text-rose-800'
                      : isWarn
                      ? 'bg-amber-100 text-amber-800'
                      : isWatch
                      ? 'bg-sky-100 text-sky-800'
                      : 'bg-emerald-100 text-emerald-800'
                  }`}
                >
                  {status}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. Active Advisories Teaser (Photo 2 Room Card style) */}
      {recommendations.length > 0 && (
        <div className="bg-white rounded-3xl p-6 shadow-card border border-[#d8e6f2]">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-[#edf4fa]">
            <div>
              <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block">
                PRIORITIZED MAINTENANCE ADVISORY
              </span>
              <h4 className="font-editorial text-xl font-bold text-[#0e1824]">
                {recommendations[0].title}
              </h4>
            </div>
            <button
              onClick={() => onNavigateTab('maintenance')}
              className="text-xs text-[#0284c7] hover:underline font-semibold"
            >
              See all ({recommendations.length}) →
            </button>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <p className="text-xs text-[#486581] max-w-2xl font-light leading-relaxed">
              {recommendations[0].advisory_wording}
            </p>

            <button
              onClick={() => onOpenFeedback(recommendations[0])}
              className="inline-flex items-center gap-2 px-5 py-2 rounded-full bg-[#0e1824] hover:bg-[#1a2c3f] text-white text-xs font-semibold shadow-pill transition-all active:scale-95 flex-shrink-0"
            >
              <span>{recommendations[0].acknowledged ? 'View Record' : 'Acknowledge Advisory'}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
