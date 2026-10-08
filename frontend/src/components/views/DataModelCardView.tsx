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
    asset_id: 'DT-TRIPURA-001',
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
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-subtle transition-colors">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 font-mono">
                Model Card & Audit Specification
              </span>
              <span
                className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                  isPromoted
                    ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300'
                    : 'bg-amber-100 dark:bg-amber-950 text-amber-900 dark:text-amber-200 border border-amber-300 dark:border-amber-800'
                }`}
              >
                {card.promotion.status} · Descriptive Shadow Mode
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
              Grey-Box Thermal Model Card
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
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
      <div className="bg-white dark:bg-slate-900 rounded-lg p-5 border border-slate-200 dark:border-slate-800 shadow-subtle transition-colors">
        <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800 mb-4">
          <Cpu className="w-4 h-4 text-sky-600 dark:text-sky-400" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            Thermal Differential Equation & Parameter Values
          </h3>
        </div>

        <div className="bg-slate-50 dark:bg-slate-800/60 rounded-lg p-4 border border-slate-200 dark:border-slate-700 mb-4">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-1">
            Differential Equation Formulation
          </span>
          <div className="font-mono text-xs text-slate-900 dark:text-slate-100 bg-white dark:bg-slate-800 p-2.5 rounded border border-slate-200 dark:border-slate-700">
            dθ_o / dt = (1 / τ) · (β₀ + β₁ · u² - θ_o)
          </div>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-2">
            Where <span className="font-mono text-slate-700 dark:text-slate-300">θ_o</span> is top-oil temperature, <span className="font-mono text-slate-700 dark:text-slate-300">u = I_rms / I_ref</span> is relative load, <span className="font-mono text-slate-700 dark:text-slate-300">τ</span> is the thermal time constant, <span className="font-mono text-slate-700 dark:text-slate-300">β₀</span> is the ambient baseline offset, and <span className="font-mono text-slate-700 dark:text-slate-300">β₁</span> is the load heating coefficient.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded border border-slate-200 dark:border-slate-700">
            <span className="text-[10px] font-semibold text-slate-400 uppercase block">Time Constant (τ)</span>
            <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100 mt-0.5">
              {card.parameters.tau_hours.toFixed(2)} hours
            </div>
            <span className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5 block">Estimated thermal inertia</span>
          </div>

          <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded border border-slate-200 dark:border-slate-700">
            <span className="text-[10px] font-semibold text-slate-400 uppercase block">Ambient Offset (β₀)</span>
            <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100 mt-0.5">
              {card.parameters.beta_0.toFixed(4)} °C
            </div>
            <span className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5 block">Steady-state no-load temperature rise</span>
          </div>

          <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded border border-slate-200 dark:border-slate-700">
            <span className="text-[10px] font-semibold text-slate-400 uppercase block">Load Coefficient (β₁)</span>
            <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100 mt-0.5">
              {card.parameters.beta_1.toFixed(4)} °C
            </div>
            <span className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5 block">Full-load squared heating coefficient</span>
          </div>
        </div>
      </div>

      {/* 2. Calibration & Test Partition Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-slate-900 rounded-lg p-5 border border-slate-200 dark:border-slate-800 shadow-subtle transition-colors">
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 pb-2 border-b border-slate-100 dark:border-slate-800 mb-3">
            Test Partition Accuracy
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400">Mean Absolute Error (MAE):</span>
              <span className="font-mono font-bold text-slate-900 dark:text-slate-100">{card.test_metrics.mae_degc.toFixed(2)} °C</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400">Root Mean Square Error (RMSE):</span>
              <span className="font-mono font-bold text-slate-900 dark:text-slate-100">{card.test_metrics.rmse_degc.toFixed(2)} °C</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400">90% Conformal Coverage:</span>
              <span className="font-mono font-bold text-emerald-700 dark:text-emerald-400">{card.test_metrics.marginal_coverage_90_pct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500 dark:text-slate-400">Training Samples:</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">{card.identifiability.fit_samples_count.toLocaleString()} frames ({card.identifiability.fit_span_days.toFixed(0)} days)</span>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 rounded-lg p-5 border border-slate-200 dark:border-slate-800 shadow-subtle transition-colors">
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 pb-2 border-b border-slate-100 dark:border-slate-800 mb-3">
            Qualification & Safety Governance
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400">Parameter Interpretability:</span>
              <span className="font-mono text-slate-800 dark:text-slate-200">{card.qualification.parameter_interpretability}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400">Forecast Qualification:</span>
              <span className="font-mono text-slate-800 dark:text-slate-200">{card.qualification.forecast_qualification}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400">Scenario Projection:</span>
              <span className="font-mono text-slate-800 dark:text-slate-200">{card.qualification.scenario_qualification}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500 dark:text-slate-400">Promotion Status:</span>
              <span className="font-mono font-bold text-amber-800 dark:text-amber-400">{card.promotion.status}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Discoverable Audit Reports & Data Export */}
      <div className="bg-white dark:bg-slate-900 rounded-lg p-5 border border-slate-200 dark:border-slate-800 shadow-subtle transition-colors">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800 gap-3 mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Audit Reports & Authoritative Data Export
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Download frozen engineering records directly from the digital twin report pipeline.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <a
            href="/v1/reports/summary.pdf"
            target="_blank"
            rel="noopener noreferrer"
            className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors flex flex-col justify-between group"
          >
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-slate-900 dark:text-slate-100">Export PDF</span>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 font-semibold">
                  PDF
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Audit / historical condition report with frozen provenance and qualification gates.
              </p>
            </div>
            <span className="text-xs font-semibold text-sky-600 dark:text-sky-400 group-hover:underline mt-3 block">
              Download PDF Report →
            </span>
          </a>

          <a
            href="/v1/reports/summary.csv"
            target="_blank"
            rel="noopener noreferrer"
            className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors flex flex-col justify-between group"
          >
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-slate-900 dark:text-slate-100">Export CSV</span>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-semibold">
                  CSV
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Tabular metrics and electrical features export for external statistical audit.
              </p>
            </div>
            <span className="text-xs font-semibold text-sky-600 dark:text-sky-400 group-hover:underline mt-3 block">
              Download CSV Data →
            </span>
          </a>

          <a
            href="/v1/reports/summary.json"
            target="_blank"
            rel="noopener noreferrer"
            className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors flex flex-col justify-between group"
          >
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-slate-900 dark:text-slate-100">Export JSON</span>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-sky-100 dark:bg-sky-950 text-sky-800 dark:text-sky-300 font-semibold">
                  JSON
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Complete machine-readable FactBundle state vector snapshot with SHA-256 hashes.
              </p>
            </div>
            <span className="text-xs font-semibold text-sky-600 dark:text-sky-400 group-hover:underline mt-3 block">
              Download JSON FactBundle →
            </span>
          </a>
        </div>
      </div>
    </div>
  );
};
