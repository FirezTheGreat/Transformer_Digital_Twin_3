import React from 'react';
import { Gauge, Zap, Activity } from 'lucide-react';
import { TwinState, CapabilityManifest, CanonicalEvent } from '../types/contracts';
import { getAssetContext } from '../utils/assetContext';

interface TelemetryPhaseGridProps {
  twinState: TwinState | null;
  capabilities: CapabilityManifest | null;
  assetId?: string;
  latestEvent?: CanonicalEvent | null;
}

/** Robust signal value extractor: checks current_observations map first, then falls back to event measurements */
const extractSignal = (
  obs: Record<string, { value: unknown } | undefined>,
  signalKeys: string[],
  fallbackMeas?: Array<{ signal_id: string; value: unknown }>
): number | null => {
  for (const k of signalKeys) {
    const item = obs[k];
    if (item && item.value !== undefined && item.value !== null) {
      const num = typeof item.value === 'number' ? item.value : Number(item.value);
      if (!Number.isNaN(num)) return num;
    }
  }
  if (fallbackMeas && fallbackMeas.length > 0) {
    for (const k of signalKeys) {
      const m = fallbackMeas.find((x) => x.signal_id === k);
      if (m && m.value !== undefined && m.value !== null) {
        const num = typeof m.value === 'number' ? m.value : Number(m.value);
        if (!Number.isNaN(num)) return num;
      }
    }
  }
  return null;
};

/** Display-only number formatting: fixed decimals for numbers; '—' for missing/unavailable */
const fmt = (v: number | null | undefined, decimals: number): string =>
  typeof v === 'number' && !Number.isNaN(v) ? v.toFixed(decimals) : '—';

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
      <span className={`metric-compact text-[23px] ${value === '—' ? 'text-faint font-normal' : tone}`}>{value}</span>
      <span className="metric-unit text-[11.5px] w-9 text-left">{value === '—' ? '' : (unit ?? '')}</span>
    </span>
  </div>
);

export const TelemetryPhaseGrid: React.FC<TelemetryPhaseGridProps> = ({
  twinState,
  capabilities,
  assetId,
  latestEvent,
}) => {
  const currentAsset = assetId || twinState?.asset_id || '';
  const assetCtx = getAssetContext(currentAsset);
  const obs = twinState?.current_observations ?? {};
  const derived = twinState?.derived_electrical;
  const meas = latestEvent?.measurements;

  // Phase Voltages (L-N): standard keys + raw SCADA aliases
  const vr = extractSignal(obs, ['voltage_l1_n', 'voltage_v1', 'voltage_v1_L1', 'VL1'], meas);
  const vy = extractSignal(obs, ['voltage_l2_n', 'voltage_v2', 'voltage_v2_L2', 'VL2'], meas);
  const vb = extractSignal(obs, ['voltage_l3_n', 'voltage_v3', 'voltage_v3_L3', 'VL3'], meas);

  // Phase Currents: check canonical current_l1/l2/l3 AND current_i1/i2/i3, plus aliases
  const ir = extractSignal(obs, ['current_l1', 'current_i1', 'current_i1_L1', 'current_a', 'IL1'], meas);
  const iy = extractSignal(obs, ['current_l2', 'current_i2', 'current_i2_L2', 'current_b', 'IL2'], meas);
  const ib = extractSignal(obs, ['current_l3', 'current_i3', 'current_i3_L3', 'current_c', 'IL3'], meas);
  const in_val = extractSignal(obs, ['neutral_current', 'current_in', 'current_n', 'INUT'], meas);

  // Power & Grid Quality
  const p_tot = extractSignal(obs, ['active_power_total', 'active_power', 'KW'], meas);
  const q_tot = extractSignal(obs, ['reactive_power_total', 'reactive_power', 'KVAR'], meas);
  const freq = extractSignal(obs, ['frequency', 'FRQ'], meas);
  const pf = derived?.power_factor_derived ?? extractSignal(obs, ['power_factor_total', 'power_factor_avg', 'Avg_PF'], meas);

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
          {panelFooter(
            'Voltage Imbalance',
            derived?.voltage_magnitude_imbalance_pct !== undefined && derived?.voltage_magnitude_imbalance_pct !== null
              ? `${derived.voltage_magnitude_imbalance_pct.toFixed(2)}%`
              : '—'
          )}
        </div>

        {/* Panel 2: Phase Currents */}
        <div className="bg-surface p-5 flex flex-col">
          {panelHeader('Phase Currents', <Zap className="w-3.5 h-3.5" strokeWidth={1.75} />)}
          <div className="py-2">
            <ReadingRow tag="I_R" label="Current R" value={fmt(ir, 1)} unit="A" />
            <ReadingRow tag="I_Y" label="Current Y" value={fmt(iy, 1)} unit="A" />
            <ReadingRow tag="I_B" label="Current B" value={fmt(ib, 1)} unit="A" />
          </div>
          {panelFooter(
            'Current Imbalance',
            derived?.current_magnitude_imbalance_pct !== undefined && derived?.current_magnitude_imbalance_pct !== null
              ? `${derived.current_magnitude_imbalance_pct.toFixed(2)}%`
              : '—'
          )}
        </div>

        {/* Panel 3: Neutral & Power Factor */}
        <div className="bg-surface p-5 flex flex-col">
          {panelHeader('Neutral & Grid Quality', <Activity className="w-3.5 h-3.5" strokeWidth={1.75} />)}
          <div className="py-2">
            <ReadingRow tag="I_N" label="Neutral Current" value={fmt(in_val, 1)} unit="A" />
            <ReadingRow tag="PF" label="Power Factor" value={typeof pf === 'number' ? pf.toFixed(3) : '—'} />
            <ReadingRow tag="f" label="Frequency" value={fmt(freq, 2)} unit="Hz" />
          </div>
          {panelFooter(
            'Neutral Ratio',
            derived?.neutral_current_ratio !== undefined && derived?.neutral_current_ratio !== null
              ? `${(derived.neutral_current_ratio * 100).toFixed(1)}%`
              : '—'
          )}
        </div>

        {/* Panel 4: Power Summary */}
        <div className="bg-surface p-5 flex flex-col">
          {panelHeader('Power Summary', <Activity className="w-3.5 h-3.5" strokeWidth={1.75} />)}
          <div className="py-2">
            <ReadingRow tag="P" label="Active Power" value={fmt(p_tot, 1)} unit="kW" />
            <ReadingRow tag="Q" label="Reactive Power" value={fmt(q_tot, 1)} unit="kvar" />
            <ReadingRow
              tag="u"
              label="Relative Load"
              value={
                typeof derived?.relative_load_index === 'number'
                  ? derived.relative_load_index.toFixed(2)
                  : '—'
              }
              unit="rel. u"
            />
          </div>
          {panelFooter('Sampling', `${assetCtx.cadenceSeconds}s (${assetCtx.cadenceLabel})`)}
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
