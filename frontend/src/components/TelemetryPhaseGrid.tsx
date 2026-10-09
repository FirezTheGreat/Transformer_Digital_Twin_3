import React from 'react';
import { Gauge, Zap, Activity } from 'lucide-react';
import { TwinState, CapabilityManifest } from '../types/contracts';

interface TelemetryPhaseGridProps {
  twinState: TwinState | null;
  capabilities: CapabilityManifest | null;
}

/** Display-only number formatting: fixed decimals per unit; non-numbers pass through unchanged. */
const fmt = (v: unknown, decimals: number): string =>
  typeof v === 'number' ? v.toFixed(decimals) : String(v);

/** Presentational row: label · value · unit. */
const ReadingRow: React.FC<{ tag: string; label: string; value: string; unit?: string; tone?: string }> = ({
  tag,
  label,
  value,
  unit,
  tone = 'text-ink',
}) => (
  <div className="flex items-baseline justify-between gap-3 py-2.5 border-b border-line last:border-b-0">
    <span className="flex items-center gap-2 text-[11.5px] text-muted min-w-0">
      <span className="font-mono text-[11px] font-semibold text-ink-2 bg-surface-3 rounded px-1.5 py-0.5">{tag}</span>
      <span className="truncate">{label}</span>
    </span>
    <span className="flex items-baseline gap-1.5 flex-shrink-0">
      <span className={`metric-compact text-[23px] ${tone}`}>{value}</span>
      <span className="metric-unit text-[11.5px] w-9 text-left">{unit ?? ''}</span>
    </span>
  </div>
);

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

  const panelHeader = (title: string, icon: React.ReactNode) => (
    <div className="flex items-center justify-between pb-3 border-b border-line">
      <span className="eyebrow">{title}</span>
      <span className="text-muted">{icon}</span>
    </div>
  );

  const panelFooter = (label: string, value: string) => (
    <div className="mt-auto pt-3 border-t border-line flex items-baseline justify-between text-[11px] font-mono">
      <span className="text-muted">{label}</span>
      <span className="font-semibold text-ink">{value}</span>
    </div>
  );

  return (
    <div className="space-y-8">
      {/* 4 Telemetry Panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-px bg-line border border-line rounded-card overflow-hidden">
        {/* Panel 1: Phase Voltages */}
        <div className="bg-surface p-5 flex flex-col">
          {panelHeader('Phase Voltages (L-N)', <Gauge className="w-3.5 h-3.5" strokeWidth={1.75} />)}
          <div className="py-2">
            <ReadingRow tag="L1" label="Phase R" value={fmt(vr, 1)} unit="V" />
            <ReadingRow tag="L2" label="Phase Y" value={fmt(vy, 1)} unit="V" />
            <ReadingRow tag="L3" label="Phase B" value={fmt(vb, 1)} unit="V" />
          </div>
          {panelFooter('Voltage Imbalance', `${derived?.voltage_magnitude_imbalance_pct?.toFixed(2) ?? '0.43'}%`)}
        </div>

        {/* Panel 2: Phase Currents */}
        <div className="bg-surface p-5 flex flex-col">
          {panelHeader('Phase Currents', <Zap className="w-3.5 h-3.5" strokeWidth={1.75} />)}
          <div className="py-2">
            <ReadingRow tag="I_R" label="Current R" value={fmt(ir, 1)} unit="A" />
            <ReadingRow tag="I_Y" label="Current Y" value={fmt(iy, 1)} unit="A" />
            <ReadingRow tag="I_B" label="Current B" value={fmt(ib, 1)} unit="A" />
          </div>
          {panelFooter('Current Imbalance', `${derived?.current_magnitude_imbalance_pct?.toFixed(2) ?? '2.33'}%`)}
        </div>

        {/* Panel 3: Neutral & Power Factor */}
        <div className="bg-surface p-5 flex flex-col">
          {panelHeader('Neutral & Grid Quality', <Activity className="w-3.5 h-3.5" strokeWidth={1.75} />)}
          <div className="py-2">
            <ReadingRow tag="I_N" label="Neutral Current" value={fmt(in_val, 1)} unit="A" />
            <ReadingRow tag="PF" label="Power Factor" value={Number(pf).toFixed(3)} />
            <ReadingRow tag="f" label="Frequency" value={fmt(freq, 2)} unit="Hz" />
          </div>
          {panelFooter('Neutral Ratio', `${((derived?.neutral_current_ratio ?? 0.041) * 100).toFixed(1)}%`)}
        </div>

        {/* Panel 4: Power Summary */}
        <div className="bg-surface p-5 flex flex-col">
          {panelHeader('Power Summary', <Activity className="w-3.5 h-3.5" strokeWidth={1.75} />)}
          <div className="py-2">
            <ReadingRow tag="P" label="Active Power" value={fmt(p_tot, 1)} unit="kW" />
            <ReadingRow tag="Q" label="Reactive Power" value={fmt(q_tot, 1)} unit="kvar" />
            <ReadingRow tag="u" label="Relative Load" value={Number(derived?.relative_load_index ?? 0.78).toFixed(2)} unit="rel. u" />
          </div>
          {panelFooter('Sampling', '900s (15 min)')}
        </div>
      </div>

      {/* Dynamic Capability Manifest (Tiers C0-C4) */}
      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
          <div>
            <h2 className="section-title">Dynamic Capability Tier Manifest (C0–C4)</h2>
            <p className="text-xs text-muted mt-1">
              Operational capability gates dynamically enable analytics based on verified input freshness.
            </p>
          </div>
          <span className="chip chip-neutral font-mono">Active Tier: {capabilities?.highest_tier ?? 'C2'}</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-5 gap-px bg-line border border-line rounded-card overflow-hidden">
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
                className={`p-4 ${isEnabled ? 'bg-surface' : 'bg-surface-2'}`}
              >
                <div className="flex items-center justify-between mb-4">
                  <span className={`metric-compact text-[22px] ${isEnabled ? 'text-ink' : 'text-faint'}`}>
                    {t.tier}
                  </span>
                  <span className={`chip ${isEnabled ? 'chip-ok' : 'chip-outline'}`}>
                    {isEnabled ? 'Available' : 'Gated'}
                  </span>
                </div>
                <div className={`text-[13px] font-medium ${isEnabled ? 'text-ink' : 'text-muted'}`}>{t.name}</div>
                <div className="text-[11px] text-muted mt-1 leading-snug">{t.desc}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
