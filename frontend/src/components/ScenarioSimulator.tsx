import React, { useState, useRef } from 'react';
import {
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
  ReferenceLine,
} from 'recharts';
import { Play, Sliders, AlertTriangle, Info, ZoomIn, Maximize2 } from 'lucide-react';

import { api, ScenarioProjectionResultData } from '../services/api';
import { useChartTheme, LegendItem } from './common/TrendChart';

interface ScenarioSimulatorProps {
  assetId: string;
  resetKey?: number;
}

export const ScenarioSimulator: React.FC<ScenarioSimulatorProps> = ({ assetId, resetKey }) => {
  const [loadMultiplier, setLoadMultiplier] = useState<number>(1.25);
  const [ambientDelta, setAmbientDelta] = useState<number>(3.0);
  const [warningThreshold, setWarningThreshold] = useState<number>(85.0);
  const [criticalThreshold, setCriticalThreshold] = useState<number>(95.0);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [result, setResult] = useState<ScenarioProjectionResultData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Focus view on trajectory data vs full scale including high safety limits
  const [focusTrajectory, setFocusTrajectory] = useState<boolean>(true);

  // Request counter to prevent race conditions from out-of-order async responses
  const requestSeqRef = useRef<number>(0);

  React.useEffect(() => {
    setResult(null);
    setError(null);
  }, [resetKey]);

  const chartTheme = useChartTheme();

  const handleRunSimulation = async () => {
    const currentSeq = ++requestSeqRef.current;
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.runScenario(assetId, {
        load_multiplier: loadMultiplier,
        ambient_delta_degc: ambientDelta,
        warning_threshold_degc: warningThreshold,
        critical_threshold_degc: criticalThreshold,
      });
      // Only commit if this is still the latest requested simulation
      if (currentSeq === requestSeqRef.current) {
        setResult(data);
      }
    } catch (err: unknown) {
      if (currentSeq === requestSeqRef.current) {
        const message = err instanceof Error ? err.message : 'Simulation failed';
        setError(message);
      }
    } finally {
      if (currentSeq === requestSeqRef.current) {
        setIsLoading(false);
      }
    }
  };

  // Build chart dataset
  const chartData = (result?.trajectory || []).map((step) => {
    const lower = Number(step.conformal_lower_degc.toFixed(2));
    const upper = Number(step.conformal_upper_degc.toFixed(2));
    return {
      time: `+${step.horizon_minutes}m`,
      projected: Number(step.projected_top_oil_degc.toFixed(2)),
      baseline: step.baseline_top_oil_degc != null ? Number(step.baseline_top_oil_degc.toFixed(2)) : null,
      lower,
      upper,
      bandWidth: Number(Math.max(0, upper - lower).toFixed(2)),
    };
  });
  const hasBaseline = chartData.some((d) => d.baseline !== null);

  // Baseline peak for delta comparison
  const baselinePeak = React.useMemo(() => {
    const baselineVals = chartData.map((d) => d.baseline).filter((v): v is number => v !== null);
    return baselineVals.length > 0 ? Math.max(...baselineVals) : null;
  }, [chartData]);

  // Dynamic Y-axis domain: focused on trajectory & bounds for legibility, with option to expand
  const yDomain = React.useMemo(() => {
    if (!chartData.length) return ['auto', 'auto'];
    const minVal = Math.min(...chartData.map((d) => d.lower));
    const maxDataVal = Math.max(...chartData.map((d) => d.upper));

    if (focusTrajectory) {
      // Focus directly on empirical trajectory and uncertainty band with clear 3°C padding
      const bottom = Math.floor(Math.max(0, minVal - 3));
      const top = Math.ceil(maxDataVal + 3);
      return [bottom, top];
    } else {
      // Expanded view including warning and critical thresholds
      const maxVal = Math.max(maxDataVal, warningThreshold, criticalThreshold);
      return [Math.floor(Math.max(0, minVal - 5)), Math.ceil(maxVal + 5)];
    }
  }, [chartData, warningThreshold, criticalThreshold, focusTrajectory]);

  return (
    <div>
      {/* Section Header & Transparency Notice */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 mb-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className="eyebrow">Forward Scenario Simulation</span>
            <span className="chip chip-neutral">2-Hour Thermal Projection</span>
          </div>
          <h2 className="section-title">Top-Oil Thermal Response under Changed Conditions</h2>
          <p className="text-xs text-muted mt-1.5 max-w-2xl">
            Simulate top-oil heating trajectory over a 2-hour horizon with empirical 90% conformal uncertainty intervals.
          </p>
        </div>

        <div className="flex items-start gap-2.5 px-3.5 py-3 rounded-card border border-line bg-surface max-w-md text-[11px] text-muted">
          <Info className="w-3.5 h-3.5 text-muted flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-ink block">Safety &amp; Governance Gate</span>
            <p className="mt-0.5 leading-snug">
              What-if projections run only for a <strong className="text-ink-2">PROMOTED</strong> thermal model. This asset&apos;s promotion decision and reasons are on the Data &amp; Model Card.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        {/* Controls Column */}
        <div className="lg:col-span-4 card p-5 flex flex-col">
          <div className="flex items-center gap-2 pb-3 border-b border-line">
            <Sliders className="w-4 h-4 text-muted" strokeWidth={1.75} />
            <h4 className="eyebrow text-ink-2">Simulation Inputs</h4>
          </div>

          <div className="space-y-6 py-5 flex-1">
            {/* Load Step Multiplier (extended up to 2.0x for testing higher overload regimes) */}
            <div>
              <div className="flex items-baseline justify-between mb-2">
                <span className="text-xs text-ink-2">Load Factor Multiplier</span>
                <span className="font-mono text-xs font-semibold text-ink num">
                  {loadMultiplier.toFixed(2)}x ({loadMultiplier >= 1 ? `+${((loadMultiplier - 1) * 100).toFixed(0)}%` : `${((loadMultiplier - 1) * 100).toFixed(0)}%`})
                </span>
              </div>
              <input
                type="range"
                min="0.5"
                max="2.0"
                step="0.05"
                value={loadMultiplier}
                onChange={(e) => setLoadMultiplier(parseFloat(e.target.value))}
                className="w-full cursor-pointer"
              />
              <div className="flex justify-between text-[11px] text-muted mt-1 font-mono">
                <span>0.50x</span>
                <span>1.00x (Nominal)</span>
                <span>1.50x</span>
                <span>2.00x</span>
              </div>
            </div>

            {/* Ambient Heatwave Delta */}
            <div>
              <div className="flex items-baseline justify-between mb-2">
                <span className="text-xs text-ink-2">Ambient Temperature Shift</span>
                <span className="font-mono text-xs font-semibold text-ink num">
                  {ambientDelta >= 0 ? `+${ambientDelta.toFixed(1)}` : ambientDelta.toFixed(1)} °C
                </span>
              </div>
              <input
                type="range"
                min="-10"
                max="15"
                step="0.5"
                value={ambientDelta}
                onChange={(e) => setAmbientDelta(parseFloat(e.target.value))}
                className="w-full cursor-pointer"
              />
              <div className="flex justify-between text-[11px] text-muted mt-1 font-mono">
                <span>-10.0°C</span>
                <span>0.0°C</span>
                <span>+15.0°C</span>
              </div>
            </div>

            {/* Warning & Critical Threshold Limits */}
            <div className="grid grid-cols-2 gap-3 pt-5 border-t border-line">
              <div>
                <label htmlFor="sim-warning-threshold" className="eyebrow text-[11px] flex items-center gap-1.5 mb-2">
                  <span className="dot bg-warn" /> Warning Limit
                </label>
                <input
                  id="sim-warning-threshold"
                  type="number"
                  value={warningThreshold}
                  onChange={(e) => setWarningThreshold(parseFloat(e.target.value))}
                  className="input font-mono"
                />
              </div>
              <div>
                <label htmlFor="sim-critical-threshold" className="eyebrow text-[11px] flex items-center gap-1.5 mb-2">
                  <span className="dot bg-crit" /> Critical Limit
                </label>
                <input
                  id="sim-critical-threshold"
                  type="number"
                  value={criticalThreshold}
                  onChange={(e) => setCriticalThreshold(parseFloat(e.target.value))}
                  className="input font-mono"
                />
              </div>
            </div>
          </div>

          <button
            onClick={handleRunSimulation}
            disabled={isLoading}
            className="btn btn-primary w-full py-2.5"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{isLoading ? 'Computing Trajectory...' : 'Run Scenario Simulation'}</span>
          </button>
        </div>

        {/* Output & Chart Column */}
        <div className="lg:col-span-8 flex flex-col gap-4">
          {(error || (result && !result.is_enabled && result.disabled_reason)) && (
            <div className="p-4 rounded-card bg-warn/5 border border-warn/25 text-xs flex items-start gap-3">
              <AlertTriangle className="w-4 h-4 text-warn flex-shrink-0 mt-0.5" />
              <div className="text-ink-2">
                <span className="font-semibold text-warn">Scenario Qualified Notice</span>
                <p className="mt-1">{error || result?.disabled_reason}</p>
                <p className="mt-1.5 text-[11px] text-muted">
                  Forward projections are withheld under capability gates until the thermal grey-box model is promoted, to prevent ungrounded operational advice.
                </p>
              </div>
            </div>
          )}

          {result ? (
            <>
              {/* Scenario Summary */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-line border border-line rounded-card overflow-hidden">
                <div className="bg-inverse text-on-inverse p-4">
                  <span className="text-[11px] font-semibold uppercase tracking-eyebrow text-on-inverse/70 block">
                    Max Projected Temp
                  </span>
                  <div className="mt-3 flex items-baseline gap-1">
                    <span className="metric-value text-[28px] text-on-inverse">
                      {result.peak_projected_top_oil_degc?.toFixed(1) ?? '--'}
                    </span>
                    <span className="text-sm text-on-inverse/60">°C</span>
                  </div>
                  {baselinePeak !== null && result.peak_projected_top_oil_degc != null && (
                    <span className="text-[10px] text-on-inverse/70 block mt-1">
                      Δ {result.peak_projected_top_oil_degc - baselinePeak >= 0 ? '+' : ''}
                      {(result.peak_projected_top_oil_degc - baselinePeak).toFixed(1)}°C vs Baseline
                    </span>
                  )}
                </div>

                <div className="bg-surface p-4">
                  <span className="eyebrow text-[11px] block">Steady State Temp</span>
                  <span className="metric-value text-[28px] mt-3 block">
                    {result.asymptotic_steady_state_degc?.toFixed(1) ??
                      (result.trajectory[result.trajectory.length - 1]?.projected_top_oil_degc?.toFixed(1) ?? '--')}
                    <span className="metric-unit ml-1">°C</span>
                  </span>
                  <span className="text-[10px] text-muted block mt-1">
                    θ* asymptotic limit
                  </span>
                </div>

                <div className="bg-surface p-4">
                  <span className="eyebrow text-[11px] flex items-center gap-1.5">
                    <span className="dot bg-warn" /> Warning Crossing
                  </span>
                  <span className={`text-lg font-mono mt-3 block ${result.earliest_warning_crossing_minutes != null ? 'text-warn font-semibold' : 'text-ink-2'}`}>
                    {result.earliest_warning_crossing_minutes != null
                      ? `+${result.earliest_warning_crossing_minutes} min`
                      : 'None'}
                  </span>
                  <span className="text-[10px] text-muted block mt-1">
                    Threshold: {warningThreshold}°C
                  </span>
                </div>

                <div className="bg-surface p-4">
                  <span className="eyebrow text-[11px] flex items-center gap-1.5">
                    <span className="dot bg-crit" /> Critical Crossing
                  </span>
                  <span className={`text-lg font-mono mt-3 block ${result.earliest_critical_crossing_minutes != null ? 'text-crit font-semibold' : 'text-ink-2'}`}>
                    {result.earliest_critical_crossing_minutes != null
                      ? `+${result.earliest_critical_crossing_minutes} min`
                      : 'None'}
                  </span>
                  <span className="text-[10px] text-muted block mt-1">
                    Threshold: {criticalThreshold}°C
                  </span>
                </div>
              </div>

              {/* Parameter Confirmation Strip */}
              <div className="px-4 py-2.5 rounded bg-surface border border-line text-[11px] text-muted flex flex-wrap items-center justify-between gap-2">
                <span>
                  <strong>Applied Scenario:</strong> Load {loadMultiplier.toFixed(2)}x (u={result.scenario_load_u.toFixed(2)} vs origin {result.origin_load_u.toFixed(2)}) · Ambient {ambientDelta >= 0 ? `+${ambientDelta.toFixed(1)}` : ambientDelta.toFixed(1)}°C ({result.scenario_ambient_degc.toFixed(1)}°C)
                </span>
                <span className="font-mono text-[10px] text-ink-2">
                  Trust: {result.trust_state}
                </span>
              </div>

              {chartData.length === 0 && (
                <div className="flex-1 min-h-[220px] border border-dashed border-line-strong rounded-card flex flex-col items-center justify-center text-center p-6">
                  <span className="chip chip-outline mb-3">Trajectory unavailable</span>
                  <p className="card-title">No projection trajectory was returned</p>
                  <p className="text-[11px] text-muted max-w-sm mt-1">
                    The scenario endpoint responded without trajectory points, so no chart is drawn.
                  </p>
                </div>
              )}

              {/* Trajectory Chart with Smooth Animated Transitions */}
              {chartData.length > 0 && (
                <div className="card-muted p-5 flex-1">
                  <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                    <span className="eyebrow text-ink-2">2-Hour Top-Oil Projection Trajectory</span>
                    <div className="flex flex-wrap items-center gap-3">
                      <div className="flex items-center gap-1.5 segmented text-[10.5px]">
                        <button
                          type="button"
                          onClick={() => setFocusTrajectory(true)}
                          data-active={focusTrajectory}
                          className="py-0.5 px-2 flex items-center gap-1"
                          title="Focus view closely on trajectory and uncertainty bands"
                        >
                          <ZoomIn className="w-3 h-3" />
                          <span>Focused View</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => setFocusTrajectory(false)}
                          data-active={!focusTrajectory}
                          className="py-0.5 px-2 flex items-center gap-1"
                          title="Expand view to include warning and critical thresholds"
                        >
                          <Maximize2 className="w-3 h-3" />
                          <span>Full Scale</span>
                        </button>
                      </div>

                      <div className="flex flex-wrap items-center gap-4">
                        <LegendItem label="Projected" />
                        {hasBaseline && <LegendItem label="Baseline" color={chartTheme.muted} dashed />}
                        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-2">
                          <span
                            className="inline-block w-3 h-2 rounded-[2px]"
                            style={{ background: chartTheme.series[0], opacity: 0.18 }}
                          />
                          90% Conformal Band
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart
                        key={`chart-${focusTrajectory}`}
                        data={chartData}
                        margin={{ top: 8, right: 12, bottom: 0, left: -8 }}
                      >
                        <CartesianGrid vertical={false} stroke={chartTheme.grid} />
                        <XAxis
                          dataKey="time"
                          tick={{ fill: chartTheme.axis, fontSize: 10.5 }}
                          tickLine={false}
                          axisLine={false}
                          tickMargin={10}
                        />
                        <YAxis
                          domain={yDomain}
                          tick={{ fill: chartTheme.axis, fontSize: 10.5 }}
                          tickLine={false}
                          axisLine={false}
                          unit="°C"
                          width={56}
                          tickFormatter={(v: number) => String(Math.round(v))}
                        />
                        <Tooltip
                          cursor={{ stroke: chartTheme.axis, strokeWidth: 1, strokeDasharray: '3 3' }}
                          formatter={(value: unknown, name: string) => [
                            typeof value === 'number' ? `${value.toFixed(1)} °C` : '—',
                            name,
                          ]}
                          labelStyle={{ color: 'rgb(var(--muted))', fontSize: 11, marginBottom: 4 }}
                          itemStyle={{ color: 'rgb(var(--ink))', fontSize: 11, padding: 0 }}
                        />
                        {/* Threshold reference lines rendered when within viewport */}
                        <ReferenceLine
                          y={warningThreshold}
                          stroke={chartTheme.warn}
                          strokeDasharray="4 4"
                          strokeWidth={1}
                          label={{
                            value: `Warn (${warningThreshold}°C)`,
                            fill: chartTheme.warn,
                            fontSize: 10,
                            position: 'insideTopRight',
                          }}
                        />
                        <ReferenceLine
                          y={criticalThreshold}
                          stroke={chartTheme.crit}
                          strokeDasharray="4 4"
                          strokeWidth={1}
                          label={{
                            value: `Crit (${criticalThreshold}°C)`,
                            fill: chartTheme.crit,
                            fontSize: 10,
                            position: 'insideTopRight',
                          }}
                        />

                        {/* Smooth animated areas and lines */}
                        <Area
                          type="monotone"
                          dataKey="lower"
                          stackId="conformal"
                          stroke="none"
                          fill="transparent"
                          isAnimationActive={true}
                          animationDuration={500}
                          animationEasing="ease-in-out"
                          legendType="none"
                          tooltipType="none"
                        />
                        <Area
                          type="monotone"
                          dataKey="bandWidth"
                          stackId="conformal"
                          stroke="none"
                          fill={chartTheme.series[0]}
                          fillOpacity={0.16}
                          name="90% Conformal Band"
                          isAnimationActive={true}
                          animationDuration={500}
                          animationEasing="ease-in-out"
                          tooltipType="none"
                        />
                        <Line
                          type="monotone"
                          dataKey="upper"
                          stroke={chartTheme.series[0]}
                          strokeOpacity={0.4}
                          strokeDasharray="3 3"
                          strokeWidth={1}
                          dot={false}
                          name="90% Upper Bound"
                          isAnimationActive={true}
                          animationDuration={500}
                          animationEasing="ease-in-out"
                        />
                        <Line
                          type="monotone"
                          dataKey="lower"
                          stroke={chartTheme.series[0]}
                          strokeOpacity={0.4}
                          strokeDasharray="3 3"
                          strokeWidth={1}
                          dot={false}
                          name="90% Lower Bound"
                          isAnimationActive={true}
                          animationDuration={500}
                          animationEasing="ease-in-out"
                        />
                        {hasBaseline && (
                          <Line
                            type="monotone"
                            dataKey="baseline"
                            stroke={chartTheme.muted}
                            strokeDasharray="5 4"
                            strokeWidth={1.5}
                            dot={false}
                            name="Baseline θ_o"
                            isAnimationActive={true}
                            animationDuration={500}
                            animationEasing="ease-in-out"
                            connectNulls
                          />
                        )}
                        <Line
                          type="monotone"
                          dataKey="projected"
                          stroke={chartTheme.series[0]}
                          strokeWidth={2}
                          dot={{ r: 2.5, fill: chartTheme.series[0], strokeWidth: 0 }}
                          activeDot={{ r: 4.5, strokeWidth: 2, stroke: chartTheme.surface }}
                          name="Projected θ_o"
                          isAnimationActive={true}
                          animationDuration={500}
                          animationEasing="ease-in-out"
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex-1 min-h-[280px] border border-dashed border-line-strong rounded-card flex flex-col items-center justify-center text-center p-6">
              <Sliders className="w-7 h-7 text-faint mb-3" strokeWidth={1.5} />
              <p className="card-title">Ready to simulate forward scenario</p>
              <p className="text-[11px] text-muted max-w-sm mt-1">
                Adjust the load factor and ambient delta sliders on the left, then click &quot;Run Scenario Simulation&quot;.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
