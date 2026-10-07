import React from 'react';
import { Cpu } from 'lucide-react';
import { ModelCardData } from '../../services/api';
import { UIHonestyBadge } from '../common/UIHonestyBadge';

interface DataModelCardViewProps {
  modelCard: ModelCardData | null;
}

export const DataModelCardView: React.FC<DataModelCardViewProps> = ({ modelCard }) => {
  const card = modelCard ?? {
    schema_version: '1.2.0',
    model_version: 'greybox_v1_0',
    asset_id: 'tripura_dt_01',
    created_at_utc: '2026-10-07T07:55:17Z',
    selected_load_driver: 'rms_current_a',
    load_driver_reference_value: 153.8652,
    parameters: {
      beta_0: 1.0880,
      beta_1: 2.8979,
      tau_hours: 0.50,
    },
    identifiability: {
      is_identifiable: false,
      fit_samples_count: 10941,
      fit_span_days: 150.39,
      load_cv: 0.5331,
      diagnostic_messages: ['Parameters sit on boundary: tau = 0.50h (lower domain limit). Status: SHADOW_DESCRIPTIVE.'],
    },
    conformal_uncertainty: {
      horizon_steps: 8,
      block_quantile_90: 5.9891,
      horizon_half_widths_degc: [2.99, 3.11, 3.37, 4.08, 5.04, 6.29, 8.20, 9.56],
    },
    test_metrics: {
      mae_degc: 1.65,
      rmse_degc: 2.29,
      marginal_coverage_90_pct: 97.33,
    },
    promotion: {
      status: 'NOT_PROMOTED',
      mae_improvement_pct: 18.59,
      all_criteria_met: false,
      reasons: ['Boundary hit on tau (0.50h). Model active as shadow descriptive twin only.'],
    },
    qualification: {
      parameter_interpretability: 'UNVERIFIED',
      forecast_qualification: 'PENDING_VALIDATION',
      scenario_qualification: 'PENDING_VALIDATION',
      residual_anomaly_qualification: 'NOT_QUALIFIED',
    },
  };

  const isPromoted = card.promotion.status === 'PROMOTED';

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-subtle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                Model Card & Audit Specification
              </span>
              <span
                className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                  isPromoted
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-amber-100 text-amber-900 border border-amber-300'
                }`}
              >
                {card.promotion.status} · Descriptive Shadow Mode
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
              Grey-Box Thermal Model Card
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Physics-grounded first-order differential equation parameters, empirical calibration results, and qualification boundaries.
            </p>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <UIHonestyBadge type="DEMO_DEFAULT" />
            <UIHonestyBadge type="relative_load_index" />
          </div>
        </div>
      </div>

      {/* 1. Model Formulation & Calibrated Parameters */}
      <div className="bg-white rounded-lg p-5 border border-slate-200 shadow-subtle">
        <div className="flex items-center gap-2 pb-3 border-b border-slate-100 mb-4">
          <Cpu className="w-4 h-4 text-sky-600" />
          <h3 className="text-sm font-bold text-slate-900">
            Thermal Differential Equation & Parameter Values
          </h3>
        </div>

        <div className="bg-slate-50 rounded-lg p-4 border border-slate-200 mb-4">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
            Differential Equation Formulation
          </span>
          <div className="font-mono text-xs text-slate-900 bg-white p-2.5 rounded border border-slate-200">
            dθ_o / dt = (1 / τ) · (β₀ + β₁ · u² - θ_o)
          </div>
          <p className="text-[11px] text-slate-500 mt-2">
            Where <span className="font-mono text-slate-700">θ_o</span> is top-oil temperature, <span className="font-mono text-slate-700">u = I_rms / I_ref</span> is relative load, <span className="font-mono text-slate-700">τ</span> is the thermal time constant, <span className="font-mono text-slate-700">β₀</span> is the ambient baseline offset, and <span className="font-mono text-slate-700">β₁</span> is the load heating coefficient.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] font-semibold text-slate-400 uppercase block">Time Constant (τ)</span>
            <div className="text-xl font-bold font-mono text-slate-900 mt-0.5">
              {card.parameters.tau_hours.toFixed(2)} hours
            </div>
            <span className="text-[10px] text-slate-500 mt-0.5 block">Estimated thermal inertia</span>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] font-semibold text-slate-400 uppercase block">Ambient Offset (β₀)</span>
            <div className="text-xl font-bold font-mono text-slate-900 mt-0.5">
              {card.parameters.beta_0.toFixed(4)} °C
            </div>
            <span className="text-[10px] text-slate-500 mt-0.5 block">Steady-state no-load temperature rise</span>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] font-semibold text-slate-400 uppercase block">Load Coefficient (β₁)</span>
            <div className="text-xl font-bold font-mono text-slate-900 mt-0.5">
              {card.parameters.beta_1.toFixed(4)} °C
            </div>
            <span className="text-[10px] text-slate-500 mt-0.5 block">Full-load squared heating coefficient</span>
          </div>
        </div>
      </div>

      {/* 2. Calibration & Test Partition Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg p-5 border border-slate-200 shadow-subtle">
          <h3 className="text-sm font-bold text-slate-900 pb-2 border-b border-slate-100 mb-3">
            Test Partition Accuracy
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Mean Absolute Error (MAE):</span>
              <span className="font-mono font-bold text-slate-900">{card.test_metrics.mae_degc.toFixed(2)} °C</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Root Mean Square Error (RMSE):</span>
              <span className="font-mono font-bold text-slate-900">{card.test_metrics.rmse_degc.toFixed(2)} °C</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">90% Conformal Coverage:</span>
              <span className="font-mono font-bold text-emerald-700">{card.test_metrics.marginal_coverage_90_pct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Training Samples:</span>
              <span className="font-mono text-slate-700">{card.identifiability.fit_samples_count.toLocaleString()} frames ({card.identifiability.fit_span_days.toFixed(0)} days)</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg p-5 border border-slate-200 shadow-subtle">
          <h3 className="text-sm font-bold text-slate-900 pb-2 border-b border-slate-100 mb-3">
            Qualification & Safety Governance
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Parameter Interpretability:</span>
              <span className="font-mono text-slate-800">{card.qualification.parameter_interpretability}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Forecast Qualification:</span>
              <span className="font-mono text-slate-800">{card.qualification.forecast_qualification}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Scenario Projection:</span>
              <span className="font-mono text-slate-800">{card.qualification.scenario_qualification}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Promotion Status:</span>
              <span className="font-mono font-bold text-amber-800">{card.promotion.status}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
