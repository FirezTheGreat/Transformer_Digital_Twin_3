import React from 'react';
import { TwinState, OTHIBundle, CapabilityManifest } from '../types/contracts';

interface AssetProfileHeaderProps {
  assetId: string;
  twinState: TwinState | null;
  health: OTHIBundle | null;
  capabilities: CapabilityManifest | null;
  onOpenModelCard: () => void;
}

export const AssetProfileHeader: React.FC<AssetProfileHeaderProps> = ({
  assetId,
  twinState,
  health,
  capabilities,
  onOpenModelCard,
}) => {
  const othiScore = health?.othi_score ?? null;
  const healthStatus = health?.status ?? 'WATCH';
  const highestTier = capabilities?.highest_tier ?? 'C2';

  const topOilObs = twinState?.current_observations?.top_oil_temperature?.value;
  const topOilExpected = twinState?.thermal_latent?.top_oil_expected_degc;
  const relativeLoad = twinState?.derived_electrical?.relative_load_index ?? 0.78;
  const apparentPowerKva = twinState?.derived_electrical?.apparent_power_derived_kva ?? 78.0;
  const watermarkUtc = twinState?.event_time_watermark_utc || twinState?.state_time_utc || '2026-10-04T12:00:00Z';

  const formattedDate = new Date(watermarkUtc).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';

  return (
    <div className="pb-6 border-b border-slate-200 mb-6">
      {/* Top Meta Line */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-2">
        <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
          <span className="font-semibold text-slate-900 uppercase tracking-wider text-[11px]">
            Distribution Substation Asset
          </span>
          <span>·</span>
          <span>Tripura Grid</span>
          <span>·</span>
          <span className="font-mono text-[11px] text-slate-600">Agartala Feeder</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
            Capability: {highestTier}
          </span>
        </div>
      </div>

      {/* Main Title & Subtitle */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
            {assetId}
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
            ONAN Distribution Transformer · Rated kVA: Unverified (95th percentile reference applied)
          </p>
        </div>

        {/* Health Score Summary Badge */}
        <div className="flex items-center gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-subtle self-start md:self-auto">
          <div>
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
              Overall Health
            </span>
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-bold font-sans text-slate-900 leading-none">
                {othiScore !== null ? Number(othiScore).toFixed(1) : '--'}
              </span>
              <span className="text-xs text-slate-400">/100</span>
            </div>
          </div>
          <div className="pl-3 border-l border-slate-200">
            <span
              className={`inline-block px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider ${
                healthStatus === 'NORMAL'
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                  : healthStatus === 'WATCH'
                  ? 'bg-amber-50 text-amber-800 border border-amber-200'
                  : 'bg-rose-50 text-rose-800 border border-rose-200'
              }`}
            >
              {healthStatus}
            </span>
            <span className="text-[10px] text-slate-500 block mt-0.5">
              Grade {health?.evidence_grade ?? 'A'} Evidence
            </span>
          </div>
        </div>
      </div>

      {/* 4-Item Telemetry Strip */}
      <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs">
        <div>
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
            Watermark Time
          </span>
          <span className="font-mono font-medium text-slate-800 text-[11px] mt-0.5 block">
            {formattedDate}
          </span>
        </div>

        <div>
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
            Operating Load
          </span>
          <span className="font-mono font-medium text-slate-800 text-[11px] mt-0.5 block">
            {Number(apparentPowerKva).toFixed(1)} kVA ({Number(relativeLoad).toFixed(2)} rel. u)
          </span>
        </div>

        <div>
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
            Top-Oil Temperature
          </span>
          <span className="font-mono font-medium text-slate-800 text-[11px] mt-0.5 block">
            {topOilObs ? `${topOilObs} °C` : '—'}
            {topOilExpected && <span className="text-slate-500 font-normal"> (Exp: {topOilExpected} °C)</span>}
          </span>
        </div>

        <div>
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
            Thermal Model
          </span>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="font-mono text-[11px] text-slate-700">
              ODE (τ = {twinState?.thermal_latent?.time_constant_tau_hours ?? 0.5}h)
            </span>
            <button
              onClick={onOpenModelCard}
              className="text-[11px] text-sky-600 hover:text-sky-800 hover:underline font-medium"
            >
              Specs →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
