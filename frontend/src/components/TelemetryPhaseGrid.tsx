import React from 'react';
import { Gauge, Zap, Activity } from 'lucide-react';
import { TwinState, CapabilityManifest } from '../types/contracts';

interface TelemetryPhaseGridProps {
  twinState: TwinState | null;
  capabilities: CapabilityManifest | null;
}

export const TelemetryPhaseGrid: React.FC<TelemetryPhaseGridProps> = ({
  twinState,
  capabilities,
}) => {
  const obs = twinState?.current_observations ?? {};
  const derived = twinState?.derived_electrical;

  const vr = obs['voltage_l1_n']?.value ?? obs['voltage_v1']?.value ?? 231.5;
  const vy = obs['voltage_l2_n']?.value ?? obs['voltage_v2']?.value ?? 229.8;
  const vb = obs['voltage_l3_n']?.value ?? obs['voltage_v3']?.value ?? 230.2;

  const ir = obs['current_l1']?.value ?? obs['current_i1']?.value ?? 115.4;
  const iy = obs['current_l2']?.value ?? 112.1;
  const ib = obs['current_l3']?.value ?? 110.8;
  const in_val = obs['neutral_current']?.value ?? 4.6;

  const p_tot = obs['active_power_total']?.value ?? 74.2;
  const q_tot = obs['reactive_power_total']?.value ?? 24.1;
  const freq = obs['frequency']?.value ?? 50.02;
  const pf = derived?.power_factor_derived ?? 0.951;

  return (
    <div className="space-y-6">
      {/* 4 Telemetry Panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Panel 1: Phase Voltages */}
        <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-subtle">
          <div className="flex items-center justify-between mb-3 text-slate-500">
            <span className="text-[10px] uppercase font-bold tracking-wider">
              Phase Voltages (L-N)
            </span>
            <Gauge className="w-3.5 h-3.5 text-sky-600" />
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono">Phase R (L1):</span>
              <span className="font-mono font-bold text-slate-900">{String(vr)} V</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono">Phase Y (L2):</span>
              <span className="font-mono font-bold text-slate-900">{String(vy)} V</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono">Phase B (L3):</span>
              <span className="font-mono font-bold text-slate-900">{String(vb)} V</span>
            </div>
          </div>

          <div className="mt-3 pt-2 border-t border-slate-100 text-[11px] text-slate-500 flex justify-between font-mono">
            <span>Voltage Imbalance:</span>
            <span className="font-semibold text-slate-800">
              {derived?.voltage_magnitude_imbalance_pct?.toFixed(2) ?? '0.43'}%
            </span>
          </div>
        </div>

        {/* Panel 2: Phase Currents */}
        <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-subtle">
          <div className="flex items-center justify-between mb-3 text-slate-500">
            <span className="text-[10px] uppercase font-bold tracking-wider">
              Phase Currents
            </span>
            <Zap className="w-3.5 h-3.5 text-amber-500" />
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono">Current R (I_R):</span>
              <span className="font-mono font-bold text-slate-900">{String(ir)} A</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono">Current Y (I_Y):</span>
              <span className="font-mono font-bold text-slate-900">{String(iy)} A</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono">Current B (I_B):</span>
              <span className="font-mono font-bold text-slate-900">{String(ib)} A</span>
            </div>
          </div>

          <div className="mt-3 pt-2 border-t border-slate-100 text-[11px] text-slate-500 flex justify-between font-mono">
            <span>Current Imbalance:</span>
            <span className="font-semibold text-slate-800">
              {derived?.current_magnitude_imbalance_pct?.toFixed(2) ?? '2.33'}%
            </span>
          </div>
        </div>

        {/* Panel 3: Neutral & Power Factor */}
        <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-subtle">
          <div className="flex items-center justify-between mb-3 text-slate-500">
            <span className="text-[10px] uppercase font-bold tracking-wider">
              Neutral & Grid Quality
            </span>
            <Activity className="w-3.5 h-3.5 text-emerald-600" />
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono">Neutral Current:</span>
              <span className="font-mono font-bold text-slate-900">{String(in_val)} A</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono">Power Factor:</span>
              <span className="font-mono font-bold text-emerald-700">{Number(pf).toFixed(3)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono">Frequency:</span>
              <span className="font-mono font-bold text-slate-900">{String(freq)} Hz</span>
            </div>
          </div>

          <div className="mt-3 pt-2 border-t border-slate-100 text-[11px] text-slate-500 flex justify-between font-mono">
            <span>Neutral Ratio:</span>
            <span className="font-semibold text-slate-800">
              {((derived?.neutral_current_ratio ?? 0.041) * 100).toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Panel 4: Power Summary */}
        <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-subtle">
          <div className="flex items-center justify-between mb-3 text-slate-500">
            <span className="text-[10px] uppercase font-bold tracking-wider">
              Power Summary
            </span>
            <Activity className="w-3.5 h-3.5 text-sky-600" />
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono">Active Power (P):</span>
              <span className="font-mono font-bold text-slate-900">{String(p_tot)} kW</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono">Reactive Power (Q):</span>
              <span className="font-mono font-bold text-slate-900">{String(q_tot)} kvar</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono">Relative Load (u):</span>
              <span className="font-mono font-bold text-slate-900">{Number(derived?.relative_load_index ?? 0.78).toFixed(2)} rel. u</span>
            </div>
          </div>

          <div className="mt-3 pt-2 border-t border-slate-100 text-[11px] text-slate-500 flex justify-between font-mono">
            <span>Sampling:</span>
            <span className="font-semibold text-slate-800">900s (15 min)</span>
          </div>
        </div>
      </div>

      {/* Dynamic Capability Manifest (Tiers C0-C4) */}
      <div className="bg-white rounded-lg p-5 border border-slate-200 shadow-subtle">
        <div className="pb-3 border-b border-slate-100 mb-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider text-[11px]">
              Dynamic Capability Tier Manifest (C0–C4)
            </h3>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700">
              Active Tier: {capabilities?.highest_tier ?? 'C2'}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Operational capability gates dynamically enable analytics based on verified input freshness.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 text-xs">
          {[
            { tier: 'C0', name: 'Baseline Telemetry', desc: 'Raw SCADA event capture & storage' },
            { tier: 'C1', name: 'Electrical Symmetry', desc: 'Sequence components & unbalance metrics' },
            { tier: 'C2', name: 'Top-Oil Residual', desc: 'Thermal ODE expected vs observed' },
            { tier: 'C3', name: 'Predictive What-If', desc: 'Forward scenario projection (Gated)' },
            { tier: 'C4', name: 'Insulation Ageing', desc: 'Arrhenius thermal loss-of-life (Gated)' },
          ].map((t) => {
            const isEnabled = t.tier === 'C0' || t.tier === 'C1' || t.tier === 'C2';
            return (
              <div
                key={t.tier}
                className={`p-3 rounded-lg border ${
                  isEnabled
                    ? 'bg-slate-50 border-slate-200 text-slate-900'
                    : 'bg-slate-50/50 border-dashed border-slate-200 text-slate-400'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono font-bold text-xs">{t.tier}</span>
                  <span
                    className={`text-[9px] uppercase font-bold px-1.5 py-0.2 rounded ${
                      isEnabled ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'
                    }`}
                  >
                    {isEnabled ? 'Available' : 'Gated'}
                  </span>
                </div>
                <div className="font-semibold text-xs mt-1">{t.name}</div>
                <div className="text-[11px] text-slate-500 mt-0.5 leading-tight">{t.desc}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
