import React from 'react';
import { X, Cpu } from 'lucide-react';
import { ModelCardData } from '../services/api';

interface ModelCardModalProps {
  isOpen: boolean;
  onClose: () => void;
  modelCard: ModelCardData | null;
}

export const ModelCardModal: React.FC<ModelCardModalProps> = ({
  isOpen,
  onClose,
  modelCard,
}) => {
  if (!isOpen) return null;

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
      diagnostic_messages: ['Boundary hit on tau (0.50h). Model active as shadow descriptive twin only.'],
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm overflow-y-auto">
      <div className="bg-white rounded-lg p-6 max-w-xl w-full shadow-elevated border border-slate-200 relative my-8 text-xs">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 p-1.5 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="mb-4 pb-3 border-b border-slate-200 pr-8">
          <div className="flex items-center gap-2 mb-1">
            <Cpu className="w-4 h-4 text-sky-600" />
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
              Model Specification
            </span>
            <span
              className={`text-[10px] font-mono font-bold px-1.5 py-0.2 rounded ${
                isPromoted
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-amber-100 text-amber-900 border border-amber-300'
              }`}
            >
              {card.promotion.status}
            </span>
          </div>
          <h3 className="text-lg font-bold text-slate-900">
            First-Order Grey-Box Thermal ODE
          </h3>
          <p className="text-slate-500 mt-0.5 font-mono text-[11px]">
            Model: {card.model_version} · Asset: {card.asset_id}
          </p>
        </div>

        {/* 1. ODE Equation & Parameters */}
        <div className="bg-slate-50 rounded p-3 border border-slate-200 mb-4">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
            ODE Formulation
          </span>
          <div className="font-mono text-xs text-slate-900 bg-white p-2 rounded border border-slate-200">
            dθ_o / dt = (1 / τ) · (β₀ + β₁ · u² - θ_o)
          </div>
          <div className="grid grid-cols-3 gap-2 mt-2 text-[11px]">
            <div>
              <span className="text-slate-400 block">τ (time const)</span>
              <strong className="font-mono text-slate-900">{card.parameters.tau_hours.toFixed(2)}h</strong>
            </div>
            <div>
              <span className="text-slate-400 block">β₀ (ambient offset)</span>
              <strong className="font-mono text-slate-900">{card.parameters.beta_0.toFixed(4)}°C</strong>
            </div>
            <div>
              <span className="text-slate-400 block">β₁ (load coeff)</span>
              <strong className="font-mono text-slate-900">{card.parameters.beta_1.toFixed(4)}°C</strong>
            </div>
          </div>
        </div>

        {/* 2. Validation Metrics & Test Partition */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
              Test Accuracy
            </span>
            <div className="space-y-1 text-[11px]">
              <div className="flex justify-between">
                <span className="text-slate-500">MAE:</span>
                <span className="font-mono font-bold text-slate-900">{card.test_metrics.mae_degc.toFixed(2)}°C</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">RMSE:</span>
                <span className="font-mono font-bold text-slate-900">{card.test_metrics.rmse_degc.toFixed(2)}°C</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">90% Coverage:</span>
                <span className="font-mono font-bold text-emerald-700">{card.test_metrics.marginal_coverage_90_pct.toFixed(1)}%</span>
              </div>
            </div>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
              Qualification Status
            </span>
            <div className="space-y-1 text-[11px]">
              <div className="flex justify-between">
                <span className="text-slate-500">Interpretability:</span>
                <span className="font-mono text-slate-800">{card.qualification.parameter_interpretability}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Forecast Gate:</span>
                <span className="font-mono text-slate-800">{card.qualification.forecast_qualification}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Status:</span>
                <span className="font-mono font-bold text-amber-800">{card.promotion.status}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-slate-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-colors"
          >
            Close Specification
          </button>
        </div>
      </div>
    </div>
  );
};
