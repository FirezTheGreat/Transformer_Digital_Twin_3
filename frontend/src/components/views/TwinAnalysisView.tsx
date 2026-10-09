import React, { useState } from 'react';
import { Cpu, ChevronDown, ChevronUp } from 'lucide-react';

import { TwinState, OTHIBundle } from '../../types/contracts';
import { ScenarioSimulator } from '../ScenarioSimulator';
import { UIHonestyBadge } from '../common/UIHonestyBadge';

interface TwinAnalysisViewProps {
  assetId: string;
  twinState: TwinState | null;
  health: OTHIBundle | null;
  resetKey?: number;
  onOpenModelCard: () => void;
}

export const TwinAnalysisView: React.FC<TwinAnalysisViewProps> = ({
  assetId,
  twinState,
  resetKey,
  onOpenModelCard,
}) => {
  const [showMathDetails, setShowMathDetails] = useState<boolean>(false);

  const obs = twinState?.current_observations ?? {};
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
  const isAbove = residualNum !== null && residualNum > 3;
  const tauHours = twinState?.thermal_latent?.time_constant_tau_hours
    ? twinState.thermal_latent.time_constant_tau_hours.toFixed(2)
    : '0.50';

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="eyebrow">Thermal Condition</span>
            <UIHonestyBadge type="SYNTHETIC_SCENARIO" customText="Forward Scenario Gated" />
          </div>
          <h1 className="page-title">Thermal &amp; What-If</h1>
          <p className="text-[13px] text-muted mt-2.5 max-w-2xl">
            Real-time top-oil monitoring compared against calibrated grey-box thermal ODE expectations.
          </p>
        </div>

        <button onClick={onOpenModelCard} className="btn btn-ghost self-start lg:self-auto">
          <Cpu className="w-3.5 h-3.5 text-muted" />
          <span>Model Calibration Card →</span>
        </button>
      </div>

      {/* Primary Thermal Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-px bg-line border border-line rounded-card overflow-hidden">
        <div className="bg-inverse text-on-inverse p-5">
          <div className="pb-3 border-b border-on-inverse/15 flex items-center">
            <span className="text-[11px] font-semibold uppercase tracking-eyebrow text-on-inverse/80 leading-none">
              Observed Temperature
            </span>
          </div>
          <div className="mt-4 flex items-baseline gap-1.5">
            <span className={`metric-value text-[40px] text-on-inverse ${topOilObs === null ? 'font-normal text-on-inverse/50' : ''}`}>
              {topOilObs !== null ? topOilObs : '—'}
            </span>
            {topOilObs !== null && <span className="text-sm text-on-inverse/72">°C</span>}
          </div>
          <span className="text-[11px] text-on-inverse/72 mt-3 block">
            Direct PT100 probe reading
          </span>
        </div>

        <div className="bg-surface p-5">
          <div className="pb-3 border-b border-line flex items-center">
            <span className="eyebrow">Model Expected Temperature</span>
          </div>
          <div className="mt-4 flex items-baseline gap-1.5">
            <span className={`metric-value text-[40px] ${topOilExpected === null ? 'text-faint font-normal' : ''}`}>
              {topOilExpected !== null ? topOilExpected : '—'}
            </span>
            {topOilExpected !== null && <span className="metric-unit">°C</span>}
          </div>
          <span className="text-[11px] text-muted mt-3 block">
            {isThermalWarmup ? 'Shadow model warming up' : 'First-order ODE baseline'}
          </span>
        </div>

        <div className="bg-surface p-5">
          <div className="pb-3 border-b border-line flex items-center justify-between">
            <span className="eyebrow">Temperature Difference</span>
            <span className={`dot w-2 h-2 ${isAbove ? 'bg-warn' : residualNum !== null ? 'bg-ok' : 'bg-line-strong'}`} />
          </div>
          <div className="mt-4 flex items-baseline gap-1.5">
            <span className={`metric-value text-[40px] ${isAbove ? 'text-warn' : residual === null ? 'text-faint font-normal' : ''}`}>
              {residual !== null ? (Number(residual) >= 0 ? `+${residual}` : residual) : '—'}
            </span>
            {residual !== null && <span className="metric-unit">°C</span>}
          </div>
          <span className="text-[11px] text-muted mt-3 block">
            {residualNum !== null ? (isAbove ? 'Running above expected model' : 'Within normal tolerance') : 'Awaiting telemetry'}
          </span>
        </div>

        <div className="bg-surface p-5">
          <div className="pb-3 border-b border-line flex items-center">
            <span className="eyebrow">Thermal Anomaly Detector</span>
          </div>
          <div className="mt-4">
            <span className="chip chip-neutral font-mono">Disabled — Not Qualified</span>
          </div>
          <span className="text-[11px] text-muted mt-4 block">
            Descriptive shadow mode only (CUSUM frozen)
          </span>
        </div>
      </div>

      {/* 2-Hour What-If Scenario Simulator Engine */}
      <ScenarioSimulator assetId={assetId} resetKey={resetKey} />

      {/* Progressive Disclosure: Mathematical Formulation & CUSUM Statistics */}
      <div className="card-muted px-5 py-4 text-xs">
        <button
          onClick={() => setShowMathDetails(!showMathDetails)}
          className="w-full flex items-center justify-between gap-3 text-ink-2 font-medium hover:text-ink text-left"
        >
          <span className="flex items-center gap-3">
            <span className="eyebrow hidden sm:inline">Formulation</span>
            <span>Mathematical Formulation & Detection Details</span>
          </span>
          {showMathDetails ? <ChevronUp className="w-4 h-4 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 flex-shrink-0" />}
        </button>

        {showMathDetails && (
          <div className="mt-4 pt-4 border-t border-line text-muted">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="eyebrow mb-2.5">Thermal Differential Equation (ODE)</h4>
                <p className="font-mono text-[12px] bg-surface p-3 rounded border border-line text-ink">
                  dθ_o / dt = (1 / τ) · (β₀ + β₁ · u² - θ_o)
                </p>
                <ul className="mt-3 space-y-1 text-[11.5px]">
                  <li>Thermal time constant: <strong className="text-ink font-semibold">τ = {tauHours} hours</strong></li>
                  <li>Ambient baseline offset: <strong className="text-ink font-semibold">β₀ = 1.09 °C</strong></li>
                  <li>Load heating coefficient: <strong className="text-ink font-semibold">β₁ = 2.90 °C</strong></li>
                </ul>
              </div>

              <div>
                <h4 className="eyebrow mb-2.5">Thermal Anomaly Qualification State</h4>
                <ul className="space-y-1.5 text-[11.5px] leading-relaxed">
                  <li>CUSUM Anomaly Status: <span className="font-mono font-semibold text-ink">DISABLED — NOT QUALIFIED</span></li>
                  <li>Accumulators: <span className="font-mono text-ink-2">C⁺ = —, C⁻ = —</span> (Frozen / inactive)</li>
                  <li>Residual definition: <span className="font-mono text-ink-2">r_k = T_observed - θ̂_expected</span></li>
                  <li>Qualification reason: Parameters sit on lower boundary (tau=0.50h). Model qualified as descriptive shadow twin only.</li>
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
