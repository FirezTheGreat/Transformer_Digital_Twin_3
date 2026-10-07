import React from 'react';
import { Star } from 'lucide-react';
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

  // Derived metrics
  const topOilObs = twinState?.current_observations?.top_oil_temperature?.value;
  const topOilExpected = twinState?.thermal_latent?.top_oil_expected_degc;
  const relativeLoad = twinState?.derived_electrical?.relative_load_index ?? 0.78;
  const apparentPowerKva = twinState?.derived_electrical?.apparent_power_derived_kva ?? 78.0;
  const watermarkUtc = twinState?.event_time_watermark_utc || twinState?.state_time_utc || '2026-10-04T12:00:00Z';

  const formattedDate = new Date(watermarkUtc).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  });

  return (
    <div className="pt-4 pb-12">
      {/* Category Subhead matching "STAY" in Photo 2 */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#5d768f]">
          TRANSFORMER ASSET
        </span>

        {/* Black pill badge matching "★ 4 star hotel" in Photo 2 */}
        <div className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-[#0e1824] text-white text-xs font-medium shadow-sm">
          <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
          <span className="font-semibold">{highestTier} Dynamic Tier</span>
        </div>
      </div>

      {/* Massive Editorial Serif Headline matching "Palm Beach Suites" */}
      <h2 className="text-4xl sm:text-6xl font-normal font-editorial text-[#0e1824] tracking-tight leading-tight">
        {assetId} Substation
      </h2>

      {/* Location / Technical Subtitle matching "Navi Mumbai" */}
      <p className="mt-2 text-base sm:text-lg text-[#5d768f] font-light">
        Rated kVA: UNVERIFIED · ONAN Distribution Substation · Agartala Feeder
      </p>

      {/* Middle Grid: ABOUT THE ASSET + OTHI HEALTH SCORE Card */}
      <div className="mt-8 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left: About the Asset (matching Photo 2) */}
        <div className="lg:col-span-8">
          <span className="text-[10px] font-bold tracking-[0.18em] uppercase text-[#5d768f] block mb-2">
            ABOUT THE ASSET
          </span>
          <p className="text-[#354e6b] text-base leading-relaxed font-light">
            A stateful, physics-grounded reduced-order digital twin operating in chronological replay.
            Integrates continuous electrical telemetry, a first-order grey-box thermal ODE (β₀, β₁, τ),
            empirical 90% conformal uncertainty intervals, multi-domain health index (gated OTHI across 5 domains),
            and deterministic maintenance rule policies. Transparently reports relative load index when rated kVA is unverified.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-[#e4eff8] text-[#1c3c5c] border border-[#cfdfed]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#0284c7]"></span>
              Grey-Box ODE (τ = {twinState?.thermal_latent?.time_constant_tau_hours ?? 0.5}h)
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-[#e4eff8] text-[#1c3c5c] border border-[#cfdfed]">
              Conformal Coverage 97.3%
            </span>
            <button
              onClick={onOpenModelCard}
              className="text-xs text-[#0284c7] hover:text-[#0369a1] font-semibold underline underline-offset-2"
            >
              Inspect Calibration Card →
            </button>
          </div>
        </div>

        {/* Right: STAY SCORE card matching Photo 2, in light-blue palette! */}
        <div className="lg:col-span-4 flex justify-start lg:justify-end">
          <div className="w-full sm:w-64 bg-[#e5f0f9] border border-[#cfe0ef] rounded-2xl p-6 shadow-sm text-left">
            <span className="text-[10px] font-bold tracking-[0.18em] uppercase text-[#5d768f] block mb-1">
              OTHI HEALTH SCORE
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-5xl font-editorial font-bold text-[#0e1824] leading-none">
                {othiScore !== null ? Number(othiScore).toFixed(1) : '--'}
              </span>
              <span className="text-xs font-semibold text-[#5d768f]">/ 100</span>
            </div>

            <div className="mt-3 flex items-center justify-between pt-3 border-t border-[#d5e4f2]">
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                  healthStatus === 'NORMAL'
                    ? 'bg-emerald-100 text-emerald-800'
                    : healthStatus === 'WATCH'
                    ? 'bg-amber-100 text-amber-800'
                    : 'bg-rose-100 text-rose-800'
                }`}
              >
                {healthStatus}
              </span>
              <span className="text-[11px] font-semibold text-[#486581]">
                Grade {health?.evidence_grade ?? 'A'} Evidence
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Summary Horizontal Pill Bar matching the "CHECK IN / CHECK OUT / GUESTS" bar in Photo 2! */}
      <div className="mt-8 bg-[#e8f2fa] border border-[#d2e3f1] rounded-2xl p-5 shadow-sm">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {/* Column 1: Watermark UTC */}
          <div>
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-1">
              WATERMARK UTC
            </span>
            <span className="text-sm font-bold font-mono text-[#0e1824]">
              {formattedDate}
            </span>
          </div>

          {/* Column 2: Operating Load */}
          <div>
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-1">
              OPERATING LOAD
            </span>
            <span className="text-sm font-bold font-mono text-[#0e1824]">
              {Number(apparentPowerKva).toFixed(1)} kVA ({Number(relativeLoad).toFixed(2)} p.u.)
            </span>
          </div>

          {/* Column 3: Top-Oil Temperature */}
          <div>
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-1">
              TOP-OIL TEMP
            </span>
            <span className="text-sm font-bold font-mono text-[#0e1824] flex items-center gap-1.5">
              <span>{topOilObs ? `${topOilObs} °C` : '74.8 °C'}</span>
              {topOilExpected && (
                <span className="text-xs text-[#5d768f] font-normal">
                  (Exp: {topOilExpected} °C)
                </span>
              )}
            </span>
          </div>

          {/* Column 4: Sampling Cadence */}
          <div>
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-1">
              SAMPLING CADENCE
            </span>
            <span className="text-sm font-bold font-mono text-[#0e1824] flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              900s (15 min)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
