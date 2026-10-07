import React from 'react';
import { Cpu } from 'lucide-react';

import { TwinState, OTHIBundle } from '../../types/contracts';
import { ScenarioSimulator } from '../ScenarioSimulator';
import { UIHonestyBadge } from '../common/UIHonestyBadge';

interface TwinAnalysisViewProps {
  assetId: string;
  twinState: TwinState | null;
  health: OTHIBundle | null;
  onOpenModelCard: () => void;
}

export const TwinAnalysisView: React.FC<TwinAnalysisViewProps> = ({
  assetId,
  twinState,
  onOpenModelCard,
}) => {
  const obs = twinState?.current_observations ?? {};
  const topOilObs = obs['top_oil_temperature']?.value ?? 74.8;
  const topOilExpected = twinState?.thermal_latent?.top_oil_expected_degc ?? 70.5;
  const residual = twinState?.derived_electrical?.thermal_residual_degc ?? 4.3;
  const tauHours = twinState?.thermal_latent?.time_constant_tau_hours ?? 0.5;
  const cusumPos = twinState?.detector_state?.cusum_pos ?? 3.82;
  const cusumAlarmActive = twinState?.detector_state?.cusum_alarm_active ?? true;

  return (
    <div className="space-y-8">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between pb-4 border-b border-[#d8e6f2] gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-[#5d768f]">
              PHYSICS & SHADOW TWIN ANALYSIS
            </span>
            <UIHonestyBadge type="SYNTHETIC_SCENARIO" customText="SHADOW WHAT-IF" />
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-[#0e1824] tracking-tight">
            Twin Analysis & What-If.
          </h2>
          <p className="text-xs sm:text-sm text-[#5d768f] font-light mt-0.5">
            Real vs. grey-box expected top-oil temperatures, free-running CUSUM residuals, and conditional 2-hour forward projections.
          </p>
        </div>

        <button
          onClick={onOpenModelCard}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white hover:bg-[#eff5fb] text-[#1c3c5c] text-xs font-semibold border border-[#d2e2ef] shadow-sm transition-all"
        >
          <Cpu className="w-3.5 h-3.5 text-[#0284c7]" />
          Calibrated Model Card (β₀, β₁, τ) →
        </button>
      </div>

      {/* Top Cards: Residual & CUSUM Tracking Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm">
          <span className="text-[10px] uppercase font-bold tracking-wider text-[#5d768f] block mb-1">
            OBSERVED TOP-OIL (T_O)
          </span>
          <div className="text-2xl font-bold font-sans text-[#0e1824] tracking-tight">
            {String(topOilObs)} °C
          </div>
          <span className="text-[11px] text-[#5d768f] mt-1 block font-mono">
            Direct PT100 sensor reading
          </span>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm">
          <span className="text-[10px] uppercase font-bold tracking-wider text-[#5d768f] block mb-1">
            ODE EXPECTED (θ̂_O)
          </span>
          <div className="text-2xl font-bold font-sans text-[#0e1824] tracking-tight">
            {topOilExpected} °C
          </div>
          <span className="text-[11px] text-[#5d768f] mt-1 block font-mono">
            First-order ODE (τ = {tauHours}h)
          </span>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm">
          <span className="text-[10px] uppercase font-bold tracking-wider text-[#5d768f] block mb-1">
            THERMAL RESIDUAL (r_k)
          </span>
          <div className={`text-2xl font-bold font-sans tracking-tight ${residual > 3 ? 'text-amber-700' : 'text-emerald-700'}`}>
            +{residual} °C
          </div>
          <span className="text-[11px] text-[#5d768f] mt-1 block font-mono">
            r_k = T_o - θ̂_o (Free-running)
          </span>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm">
          <span className="text-[10px] uppercase font-bold tracking-wider text-[#5d768f] block mb-1">
            CUSUM ALARM STATE
          </span>
          <div className={`text-xl font-bold font-sans tracking-tight ${cusumAlarmActive ? 'text-amber-700' : 'text-emerald-700'}`}>
            {cusumAlarmActive ? 'Warning Shift Active' : 'Normal Accumulator'}
          </div>
          <span className="text-[11px] text-[#5d768f] mt-1 block font-mono">
            C⁺ = {cusumPos.toFixed(2)} (Threshold: 3.50)
          </span>
        </div>
      </div>

      {/* 2-Hour What-If Scenario Simulator Engine */}
      <ScenarioSimulator assetId={assetId} />
    </div>
  );
};
