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
import { Play, Sliders, AlertTriangle, Info } from 'lucide-react';

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
    <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-subtle">
      {/* Header & Transparency Notice */}
      <div className="pb-4 border-b border-slate-200 mb-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 font-mono">
                Forward Scenario Simulation
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-50 text-amber-900 border border-amber-200 font-medium">
                2-Hour Thermal Projection
              </span>
            </div>
            <h3 className="text-lg font-bold text-slate-900">
              Top-Oil Thermal Response under Changed Conditions
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Simulate top-oil heating trajectory over a 2-hour horizon with empirical 90% conformal uncertainty intervals.
            </p>
          </div>

          <div className="p-2.5 rounded bg-slate-50 border border-slate-200 text-[11px] text-slate-600 max-w-sm">
            <div className="flex items-center gap-1.5 font-semibold text-slate-800">
              <Info className="w-3.5 h-3.5 text-sky-600 flex-shrink-0" />
              <span>Safety & Governance Gate</span>
            </div>
            <p className="mt-1 text-[10px] leading-tight text-slate-500">
              Tripura thermal model status is <strong>NOT_PROMOTED</strong> due to uninstrumented ambient sensors. Projections operate under descriptive qualification boundaries.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Controls Column */}
        <div className="lg:col-span-4 space-y-4 bg-slate-50 p-4 rounded-lg border border-slate-200">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-200">
            <Sliders className="w-4 h-4 text-slate-600" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
              Simulation Inputs
            </h4>
          </div>

          {/* Load Step Multiplier */}
          <div>
            <div className="flex justify-between text-xs mb-1 font-medium">
              <span className="text-slate-700">Load Factor Multiplier</span>
              <span className="font-mono font-bold text-slate-900">
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
              className="w-full accent-slate-900 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400 mt-0.5 font-mono">
              <span>0.50x (50%)</span>
              <span>1.00x (Nominal)</span>
              <span>1.60x (160%)</span>
            </div>
          </div>

          {/* Ambient Heatwave Delta */}
          <div>
            <div className="flex justify-between text-xs mb-1 font-medium">
              <span className="text-slate-700">Ambient Temperature Shift</span>
              <span className="font-mono font-bold text-slate-900">
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
              className="w-full accent-slate-900 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400 mt-0.5 font-mono">
              <span>-10.0°C</span>
              <span>0.0°C</span>
              <span>+15.0°C</span>
            </div>
          </div>

          {/* Warning & Critical Threshold Limits */}
          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-200 text-xs">
            <div>
              <label htmlFor="sim-warning-threshold" className="text-[10px] uppercase font-semibold text-slate-500 block mb-1">
                Warning Limit
              </label>
              <input
                id="sim-warning-threshold"
                type="number"
                value={warningThreshold}
                onChange={(e) => setWarningThreshold(parseFloat(e.target.value))}
                className="w-full bg-white border border-slate-300 rounded px-2 py-1 font-mono text-xs text-slate-900"
              />
            </div>
            <div>
              <label htmlFor="sim-critical-threshold" className="text-[10px] uppercase font-semibold text-slate-500 block mb-1">
                Critical Limit
              </label>
              <input
                id="sim-critical-threshold"
                type="number"
                value={criticalThreshold}
                onChange={(e) => setCriticalThreshold(parseFloat(e.target.value))}
                className="w-full bg-white border border-slate-300 rounded px-2 py-1 font-mono text-xs text-slate-900"
              />
            </div>
          </div>

          <button
            onClick={handleRunSimulation}
            disabled={isLoading}
            className="w-full py-2 px-4 rounded bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5 fill-current text-sky-400" />
            <span>{isLoading ? 'Computing Trajectory...' : 'Run Scenario Simulation'}</span>
          </button>
        </div>

        {/* Output & Chart Column */}
        <div className="lg:col-span-8">
          {error && (
            <div className="p-3.5 rounded bg-amber-50 border border-amber-300 text-amber-900 text-xs flex items-start gap-2 mb-4">
              <AlertTriangle className="w-4 h-4 text-amber-700 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-bold">Scenario Qualified Notice:</span>
                <p className="mt-0.5">{error}</p>
                <p className="mt-1 text-[11px] text-amber-800">
                  Because the Tripura thermal grey-box model is unpromoted, forward projections are withheld under frozen capability gates to prevent ungrounded operational advice.
                </p>
              </div>
            </div>
          )}

          {result ? (
            <div className="space-y-4">
              {/* Flattened Summary Readout Rail */}
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 grid grid-cols-2 sm:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-slate-200">
                <div className="px-3 py-1">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Max Projected Temp</span>
                  <span className="text-lg font-bold font-mono text-slate-900 mt-0.5 block">
                    {result.peak_projected_top_oil_degc?.toFixed(1) ?? '--'} °C
                  </span>
                </div>

                <div className="px-3 py-1">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Steady State Temp</span>
                  <span className="text-lg font-bold font-mono text-slate-900 mt-0.5 block">
                    {result.asymptotic_steady_state_degc?.toFixed(1) ?? (result.trajectory[result.trajectory.length - 1]?.projected_top_oil_degc?.toFixed(1) ?? '--')} °C
                  </span>
                </div>

                <div className="px-3 py-1">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Warning Crossing</span>
                  <span className="text-base font-semibold font-mono text-slate-800 mt-0.5 block">
                    {result.earliest_warning_crossing_minutes != null
                      ? `+${result.earliest_warning_crossing_minutes} min`
                      : 'None'}
                  </span>
                </div>

                <div className="px-3 py-1">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Critical Crossing</span>
                  <span className="text-base font-semibold font-mono text-slate-800 mt-0.5 block">
                    {result.earliest_critical_crossing_minutes != null
                      ? `+${result.earliest_critical_crossing_minutes} min`
                      : 'None'}
                  </span>
                </div>
              </div>

              {/* Trajectory Chart */}
              {chartData.length > 0 && (
                <div className="border border-slate-200 rounded-lg p-4 bg-white">
                  <div className="flex items-center justify-between mb-3 text-xs">
                    <span className="font-bold text-slate-900">2-Hour Top-Oil Projection Trajectory</span>
                    <div className="flex items-center gap-4 text-[11px] text-slate-600">
                      <span className="flex items-center gap-1">
                        <span className="w-2.5 h-2.5 rounded-full bg-sky-600"></span> Projected
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="w-2.5 h-2.5 rounded bg-slate-200"></span> 90% Conformal Band
                      </span>
                    </div>
                  </div>

                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} />
                        <YAxis domain={['auto', 'auto']} stroke="#94a3b8" fontSize={11} unit="°C" />
                        <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '11px' }} />
                        <ReferenceLine y={warningThreshold} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: `Warn (${warningThreshold}°C)`, fill: '#b45309', fontSize: 10 }} />
                        <ReferenceLine y={criticalThreshold} stroke="#ef4444" strokeDasharray="4 4" label={{ value: `Crit (${criticalThreshold}°C)`, fill: '#b91c1c', fontSize: 10 }} />
                        <Line type="monotone" dataKey="projected" stroke="#0284c7" strokeWidth={2.5} dot={{ r: 3 }} name="Projected θ_o" />
                        <Line type="monotone" dataKey="upper" stroke="#94a3b8" strokeDasharray="2 2" strokeWidth={1} dot={false} name="90% Upper Bound" />
                        <Line type="monotone" dataKey="lower" stroke="#94a3b8" strokeDasharray="2 2" strokeWidth={1} dot={false} name="90% Lower Bound" />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="h-64 border border-dashed border-slate-300 rounded-lg flex flex-col items-center justify-center text-center p-6 text-slate-500">
              <Sliders className="w-8 h-8 text-slate-400 mb-2" />
              <p className="text-xs font-semibold text-slate-700">Ready to simulate forward scenario</p>
              <p className="text-[11px] text-slate-400 max-w-sm mt-0.5">
                Adjust the load factor and ambient delta sliders on the left, then click &quot;Run Scenario Simulation&quot;.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
