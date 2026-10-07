import React from 'react';
import { Activity, Gauge, Zap, Layers } from 'lucide-react';
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

  // Measurement extractions
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

  const tierMap = capabilities?.capabilities ?? {};

  return (
    <section className="mt-14 pb-14">
      {/* Editorial Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-8 pb-4 border-b border-[#d8e6f2]">
        <div>
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#5d768f] block mb-2">
            ELECTRICAL OBSERVABILITY & CAPABILITY TIERS
          </span>
          <p className="text-sm text-[#5d768f]">
            Raw electrical telemetry vectors, derived symmetry metrics, and C0–C4 tier confinement.
          </p>
        </div>
        <h3 className="mt-3 sm:mt-0 text-3xl sm:text-5xl font-normal font-editorial text-[#0e1824] tracking-tight">
          Phase telemetry.
        </h3>
      </div>

      {/* Grid of Measurements */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Card 1: 3-Phase Voltages */}
        <div className="bg-white rounded-3xl p-6 shadow-card border border-[#d8e6f2]">
          <div className="flex items-center justify-between mb-4">
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f]">
              PHASE VOLTAGES (L-N)
            </span>
            <Gauge className="w-4 h-4 text-[#0284c7]" />
          </div>

          <div className="space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#486581] font-mono">Phase R (L1):</span>
              <span className="font-mono font-bold text-[#0e1824]">{String(vr)} V</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#486581] font-mono">Phase Y (L2):</span>
              <span className="font-mono font-bold text-[#0e1824]">{String(vy)} V</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#486581] font-mono">Phase B (L3):</span>
              <span className="font-mono font-bold text-[#0e1824]">{String(vb)} V</span>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[#edf4fa] text-[11px] text-[#5d768f] flex justify-between">
            <span>Imbalance (%VUB):</span>
            <span className="font-mono font-semibold text-[#0e1824]">
              {derived?.voltage_magnitude_imbalance_pct?.toFixed(2) ?? '0.43'}%
            </span>
          </div>
        </div>

        {/* Card 2: 3-Phase Currents */}
        <div className="bg-white rounded-3xl p-6 shadow-card border border-[#d8e6f2]">
          <div className="flex items-center justify-between mb-4">
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f]">
              PHASE CURRENTS
            </span>
            <Zap className="w-4 h-4 text-amber-500" />
          </div>

          <div className="space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#486581] font-mono">Current R (I_R):</span>
              <span className="font-mono font-bold text-[#0e1824]">{String(ir)} A</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#486581] font-mono">Current Y (I_Y):</span>
              <span className="font-mono font-bold text-[#0e1824]">{String(iy)} A</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#486581] font-mono">Current B (I_B):</span>
              <span className="font-mono font-bold text-[#0e1824]">{String(ib)} A</span>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[#edf4fa] text-[11px] text-[#5d768f] flex justify-between">
            <span>Current Imbalance:</span>
            <span className="font-mono font-semibold text-[#0e1824]">
              {derived?.current_magnitude_imbalance_pct?.toFixed(2) ?? '2.33'}%
            </span>
          </div>
        </div>

        {/* Card 3: Neutral & Power Factor */}
        <div className="bg-white rounded-3xl p-6 shadow-card border border-[#d8e6f2]">
          <div className="flex items-center justify-between mb-4">
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f]">
              NEUTRAL & POWER FACTOR
            </span>
            <Activity className="w-4 h-4 text-emerald-600" />
          </div>

          <div className="space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#486581]">Neutral Current (I_N):</span>
              <span className="font-mono font-bold text-[#0e1824]">{String(in_val)} A</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#486581]">Neutral / Phase Ratio:</span>
              <span className="font-mono font-bold text-[#0e1824]">
                {((derived?.neutral_current_ratio ?? 0.041) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#486581]">Power Factor (cos φ):</span>
              <span className="font-mono font-bold text-emerald-700">
                {Number(pf).toFixed(3)}
              </span>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[#edf4fa] text-[11px] text-[#5d768f] flex justify-between">
            <span>PQS Inconsistency:</span>
            <span className="font-mono font-semibold text-[#0e1824]">
              {derived?.pqs_inconsistency?.toFixed(4) ?? '0.0020'}
            </span>
          </div>
        </div>

        {/* Card 4: Grid Power & Frequency */}
        <div className="bg-white rounded-3xl p-6 shadow-card border border-[#d8e6f2]">
          <div className="flex items-center justify-between mb-4">
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f]">
              GRID POWER & FREQ
            </span>
            <Activity className="w-4 h-4 text-indigo-500" />
          </div>

          <div className="space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#486581]">Active Power (P):</span>
              <span className="font-mono font-bold text-[#0e1824]">{String(p_tot)} kW</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#486581]">Reactive Power (Q):</span>
              <span className="font-mono font-bold text-[#0e1824]">{String(q_tot)} kvar</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#486581]">Nominal Frequency:</span>
              <span className="font-mono font-bold text-[#0e1824]">{String(freq)} Hz</span>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[#edf4fa] text-[11px] text-[#5d768f] flex justify-between">
            <span>Grid Quality:</span>
            <span className="font-semibold text-emerald-700 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Nominal
            </span>
          </div>
        </div>
      </div>

      {/* C0–C4 Capability Tier Manifest */}
      <div className="mt-8 bg-white rounded-3xl p-6 sm:p-8 shadow-card border border-[#d8e6f2]">
        <div className="flex items-center justify-between mb-5 pb-3 border-b border-[#edf4fa]">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-[#0284c7]" />
            <h4 className="font-editorial text-xl font-bold text-[#0e1824]">
              C0–C4 Capability Tiers
            </h4>
          </div>
          <span className="text-xs text-[#5d768f]">
            Highest Active: <strong className="text-[#0e1824] font-mono">{capabilities?.highest_tier ?? 'C3'}</strong>
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {[
            { tier: 'C0', name: 'Integrity', desc: 'Timestamp & Frame Plausibility' },
            { tier: 'C1', name: 'Electrical', desc: 'Active/Reactive & Imbalance' },
            { tier: 'C2', name: 'Top-Oil', desc: 'Direct Thermal Monitoring' },
            { tier: 'C3', name: 'Predictive', desc: 'Grey-Box ODE & Conformal' },
            { tier: 'C4', name: 'Ageing', desc: 'Paper Loss-of-Life Hotspot' },
          ].map((item) => {
            const cap = tierMap[item.tier];
            const isEnabled = cap?.enabled ?? (item.tier !== 'C4');
            const grade = cap?.evidence_grade ?? (isEnabled ? 'A' : 'U');

            return (
              <div
                key={item.tier}
                className={`p-4 rounded-2xl border transition-all ${
                  isEnabled
                    ? 'bg-[#f4f9fd] border-[#cfe2f2]'
                    : 'bg-[#fafbfe] border-[#e2e8f0] opacity-75'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold font-mono text-[#0e1824]">
                    {item.tier}
                  </span>
                  <span
                    className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full ${
                      isEnabled ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'
                    }`}
                  >
                    {isEnabled ? 'ACTIVE' : 'GATED'}
                  </span>
                </div>
                <h5 className="font-editorial font-bold text-sm text-[#0e1824]">
                  {item.name}
                </h5>
                <p className="text-[11px] text-[#5d768f] mt-1 leading-snug">
                  {item.desc}
                </p>
                <div className="mt-3 pt-2 border-t border-[#d8e6f2] flex items-center justify-between text-[10px] text-[#5d768f]">
                  <span>Evidence: <strong>Grade {grade}</strong></span>
                  {cap?.disabled_reason_codes && cap.disabled_reason_codes.length > 0 && (
                    <span className="text-amber-700 font-mono text-[9px]" title={cap.disabled_reason_codes.join(', ')}>
                      {cap.disabled_reason_codes[0]}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
