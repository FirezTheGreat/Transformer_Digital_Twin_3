import React, { useState } from 'react';
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
  ReferenceLine,
} from 'recharts';
import { Play, TrendingUp, Sliders, AlertTriangle } from 'lucide-react';

import { api, ScenarioProjectionResultData } from '../services/api';

interface ScenarioSimulatorProps {
  assetId: string;
}

export const ScenarioSimulator: React.FC<ScenarioSimulatorProps> = ({ assetId }) => {
  const [loadMultiplier, setLoadMultiplier] = useState<number>(1.25);
  const [ambientDelta, setAmbientDelta] = useState<number>(3.0);
  const [warningThreshold, setWarningThreshold] = useState<number>(85.0);
  const [criticalThreshold, setCriticalThreshold] = useState<number>(95.0);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [result, setResult] = useState<ScenarioProjectionResultData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRunSimulation = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.runScenario(assetId, {
        load_multiplier: loadMultiplier,
        ambient_delta_degc: ambientDelta,
        warning_threshold_degc: warningThreshold,
        critical_threshold_degc: criticalThreshold,
      });
      setResult(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Simulation failed';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  // Build chart dataset
  const chartData = (result?.trajectory || []).map((step) => ({
    time: `+${step.horizon_minutes}m`,
    projected: Number(step.projected_top_oil_degc.toFixed(2)),
    baseline: step.baseline_top_oil_degc ? Number(step.baseline_top_oil_degc.toFixed(2)) : null,
    lower: Number(step.conformal_lower_degc.toFixed(2)),
    upper: Number(step.conformal_upper_degc.toFixed(2)),
    conformalRange: [
      Number(step.conformal_lower_degc.toFixed(2)),
      Number(step.conformal_upper_degc.toFixed(2)),
    ],
  }));

  return (
    <section className="mt-14 pb-14">
      {/* Editorial Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-8 pb-4 border-b border-[#d8e6f2]">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#5d768f]">
              SHADOW TWIN · WHAT-IF SCENARIO SIMULATOR
            </span>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-900 border border-amber-200">
              Descriptive / Step Response
            </span>
          </div>
          <p className="text-sm text-[#5d768f]">
            Conditional 2-hour forward ODE step projection with empirical 90% conformal uncertainty bounds (Not a failure or RUL forecast).
          </p>
        </div>
        <h3 className="mt-3 sm:mt-0 text-3xl sm:text-5xl font-normal font-editorial text-[#0e1824] tracking-tight">
          What-if simulation.
        </h3>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Controls Card */}
        <div className="lg:col-span-4 bg-white rounded-3xl p-6 sm:p-7 shadow-card border border-[#d8e6f2]">
          <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[#edf4fa]">
            <Sliders className="w-4 h-4 text-[#0284c7]" />
            <h4 className="font-editorial text-xl font-bold text-[#0e1824]">
              Projection Parameters
            </h4>
          </div>

          <div className="space-y-5">
            {/* Load Step Multiplier */}
            <div>
              <div className="flex justify-between text-xs mb-1.5 font-medium">
                <span className="text-[#354e6b]">Load Step Multiplier</span>
                <span className="font-mono font-bold text-[#0e1824]">
                  {loadMultiplier.toFixed(2)}x ({((loadMultiplier - 1) * 100).toFixed(0)}% step)
                </span>
              </div>
              <input
                type="range"
                min="0.5"
                max="1.6"
                step="0.05"
                value={loadMultiplier}
                onChange={(e) => setLoadMultiplier(parseFloat(e.target.value))}
                className="w-full accent-[#0e1824] cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-[#829ab1] mt-1 font-mono">
                <span>0.50x (50%)</span>
                <span>1.00x (Nominal)</span>
                <span>1.60x (160%)</span>
              </div>
            </div>

            {/* Ambient Delta */}
            <div>
              <div className="flex justify-between text-xs mb-1.5 font-medium">
                <span className="text-[#354e6b]">Ambient Heatwave Delta</span>
                <span className="font-mono font-bold text-[#0e1824]">
                  +{ambientDelta.toFixed(1)} °C
                </span>
              </div>
              <input
                type="range"
                min="-10"
                max="15"
                step="0.5"
                value={ambientDelta}
                onChange={(e) => setAmbientDelta(parseFloat(e.target.value))}
                className="w-full accent-[#0e1824] cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-[#829ab1] mt-1 font-mono">
                <span>-10.0°C</span>
                <span>0.0°C</span>
                <span>+15.0°C</span>
              </div>
            </div>

            {/* Threshold Limits */}
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div>
                <label className="text-[10px] uppercase font-bold tracking-wider text-[#5d768f] block mb-1">
                  WARNING LIMIT
                </label>
                <div className="relative">
                  <input
                    type="number"
                    value={warningThreshold}
                    onChange={(e) => setWarningThreshold(parseFloat(e.target.value) || 85)}
                    className="w-full bg-[#f8fbfe] border border-[#d2e2ef] rounded-xl px-3 py-2 text-xs font-mono font-semibold text-[#0e1824]"
                  />
                  <span className="absolute right-3 top-2 text-xs text-[#829ab1]">°C</span>
                </div>
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold tracking-wider text-[#5d768f] block mb-1">
                  CRITICAL LIMIT
                </label>
                <div className="relative">
                  <input
                    type="number"
                    value={criticalThreshold}
                    onChange={(e) => setCriticalThreshold(parseFloat(e.target.value) || 95)}
                    className="w-full bg-[#f8fbfe] border border-[#d2e2ef] rounded-xl px-3 py-2 text-xs font-mono font-semibold text-[#0e1824]"
                  />
                  <span className="absolute right-3 top-2 text-xs text-[#829ab1]">°C</span>
                </div>
              </div>
            </div>

            {/* Run Button matching Photo 2 black pill button */}
            <button
              onClick={handleRunSimulation}
              disabled={isLoading}
              className="w-full mt-2 inline-flex items-center justify-center gap-2 py-3 px-6 rounded-full bg-[#0e1824] hover:bg-[#1a2c3f] text-white text-xs font-semibold shadow-pill hover:shadow-md transition-all active:scale-95"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{isLoading ? 'Simulating Trajectory...' : 'Execute Projection →'}</span>
            </button>

            {error && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
                {error}
              </div>
            )}
          </div>
        </div>

        {/* Results & Chart Card */}
        <div className="lg:col-span-8 bg-white rounded-3xl p-6 sm:p-8 shadow-card border border-[#d8e6f2]">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#edf4fa] gap-3">
            <div>
              <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block">
                THERMAL CONFORMAL TRAJECTORY (8 STEPS · 2 HOURS)
              </span>
              <h4 className="font-editorial text-2xl font-bold text-[#0e1824]">
                Forward Top-Oil Forecast
              </h4>
            </div>

            {result && (
              result.is_enabled ? (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs bg-[#eff5fb] border border-[#d2e2ef] px-3 py-1 rounded-full text-[#1c3c5c] font-medium">
                    Peak: <strong className="font-mono">{result.peak_projected_top_oil_degc?.toFixed(1)}°C</strong>
                  </span>
                  <span className="text-xs bg-[#eff5fb] border border-[#d2e2ef] px-3 py-1 rounded-full text-[#1c3c5c] font-medium">
                    Steady: <strong className="font-mono">{result.asymptotic_steady_state_degc?.toFixed(1)}°C</strong>
                  </span>
                  {result.is_extrapolated && (
                    <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-900 border border-amber-300 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3 text-amber-700" /> Extrapolated
                    </span>
                  )}
                </div>
              ) : (
                <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-900 border border-amber-300 px-3 py-1 rounded-full flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3 text-amber-700" /> GATED
                </span>
              )
            )}
          </div>

          {result && !result.is_enabled && (
            <div className="mt-4 p-3.5 rounded-2xl bg-amber-50/90 border border-amber-300 text-amber-900 text-xs flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-700 flex-shrink-0 mt-0.5" />
              <div>
                <strong className="font-semibold block text-[#0e1824]">Scenario Capability Gated</strong>
                <span className="text-[11px] text-amber-900 mt-0.5 block">{result.disabled_reason || 'Thermal scenario projection disabled for current model trust state.'}</span>
              </div>
            </div>
          )}

          {result?.is_enabled && result?.is_extrapolated && result?.extrapolation_warning && (
            <div className="mt-4 p-3 rounded-2xl bg-amber-50/80 border border-amber-200 text-amber-900 text-xs flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-700 flex-shrink-0 mt-0.5" />
              <div>
                <strong className="font-semibold block">Extrapolation Notice (Conformal Bounds Broadened)</strong>
                <span className="text-[11px] text-amber-800">{result.extrapolation_warning}</span>
              </div>
            </div>
          )}

          {/* Chart area */}
          <div className="h-72 mt-6">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e9f2fa" />
                  <XAxis dataKey="time" stroke="#829ab1" fontSize={11} tickLine={false} />
                  <YAxis
                    stroke="#829ab1"
                    fontSize={11}
                    domain={['auto', 'auto']}
                    unit="°C"
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#ffffff',
                      borderColor: '#d2e3f1',
                      borderRadius: '12px',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.06)',
                      fontSize: '12px',
                    }}
                  />

                  {/* Warning line */}
                  <ReferenceLine
                    y={warningThreshold}
                    stroke="#d97706"
                    strokeDasharray="4 4"
                    label={{ value: 'Warning Limit', fill: '#d97706', fontSize: 10, position: 'top' }}
                  />
                  {/* Critical line */}
                  <ReferenceLine
                    y={criticalThreshold}
                    stroke="#dc2626"
                    strokeDasharray="4 4"
                    label={{ value: 'Critical Limit', fill: '#dc2626', fontSize: 10, position: 'top' }}
                  />

                  {/* Baseline curve */}
                  <Line
                    type="monotone"
                    dataKey="baseline"
                    stroke="#94a3b8"
                    strokeWidth={2}
                    strokeDasharray="3 3"
                    dot={false}
                    name="Baseline (Unmodified)"
                  />

                  {/* Conformal Upper and Lower bounds */}
                  <Line
                    type="monotone"
                    dataKey="upper"
                    stroke="#38bdf8"
                    strokeWidth={1.5}
                    strokeDasharray="2 2"
                    dot={false}
                    name="90% Upper Bound"
                  />
                  <Line
                    type="monotone"
                    dataKey="lower"
                    stroke="#38bdf8"
                    strokeWidth={1.5}
                    strokeDasharray="2 2"
                    dot={false}
                    name="90% Lower Bound"
                  />

                  {/* Projected Top-Oil curve */}
                  <Line
                    type="monotone"
                    dataKey="projected"
                    stroke="#0e1824"
                    strokeWidth={3}
                    dot={{ r: 4, fill: '#0e1824', strokeWidth: 0 }}
                    name="Projected Top-Oil"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            ) : result && !result.is_enabled ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 border-2 border-dashed border-amber-300 rounded-2xl bg-amber-50/50">
                <AlertTriangle className="w-8 h-8 text-amber-600 mb-2" />
                <p className="text-sm font-editorial font-bold text-[#0e1824]">
                  Scenario Projection Gated
                </p>
                <p className="text-xs text-amber-900 mt-1 max-w-sm font-medium">
                  {result.disabled_reason || 'Thermal model is in shadow descriptive mode. Projection capability is disabled.'}
                </p>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 border-2 border-dashed border-[#e2edf6] rounded-2xl bg-[#f8fbfe]">
                <TrendingUp className="w-8 h-8 text-[#0284c7] mb-2" />
                <p className="text-sm font-editorial text-[#0e1824]">
                  Ready to simulate forward trajectory
                </p>
                <p className="text-xs text-[#5d768f] mt-1 max-w-sm">
                  Click "Execute Projection →" to solve the first-order ODE under chosen load and ambient conditions.
                </p>
              </div>
            )}
          </div>

          {/* Key Metric Pills */}
          {result && result.is_enabled && (
            <div className="mt-6 pt-4 border-t border-[#edf4fa] grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="bg-[#eff5fb] p-3 rounded-xl border border-[#dbe8f3]">
                <span className="text-[#5d768f] text-[10px] uppercase font-bold tracking-wider block">
                  ORIGIN TOP-OIL
                </span>
                <span className="text-sm font-bold font-mono text-[#0e1824]">
                  {result.origin_top_oil_degc.toFixed(1)} °C
                </span>
              </div>

              <div className="bg-[#eff5fb] p-3 rounded-xl border border-[#dbe8f3]">
                <span className="text-[#5d768f] text-[10px] uppercase font-bold tracking-wider block">
                  SCENARIO AMBIENT
                </span>
                <span className="text-sm font-bold font-mono text-[#0e1824]">
                  {result.scenario_ambient_degc.toFixed(1)} °C
                </span>
              </div>

              <div className="bg-[#eff5fb] p-3 rounded-xl border border-[#dbe8f3]">
                <span className="text-[#5d768f] text-[10px] uppercase font-bold tracking-wider block">
                  TIME ABOVE WARNING
                </span>
                <span className="text-sm font-bold font-mono text-amber-700">
                  {result.time_above_warning_minutes ?? 0} mins
                </span>
              </div>

              <div className="bg-[#eff5fb] p-3 rounded-xl border border-[#dbe8f3]">
                <span className="text-[#5d768f] text-[10px] uppercase font-bold tracking-wider block">
                  TIME ABOVE CRITICAL
                </span>
                <span className="text-sm font-bold font-mono text-rose-700">
                  {result.time_above_critical_minutes ?? 0} mins
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
