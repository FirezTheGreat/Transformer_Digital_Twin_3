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
    <div className="modal-backdrop overflow-y-auto">
      <div className="modal p-6 max-w-xl w-full relative my-8 text-xs">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 icon-btn border-transparent"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="mb-5 pb-4 border-b border-line pr-10">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <Cpu className="w-3.5 h-3.5 text-muted" strokeWidth={1.75} />
            <span className="eyebrow">Model Specification</span>
            <span className={`chip font-mono ${isPromoted ? 'chip-ok' : 'chip-warn'}`}>
              {card.promotion.status}
            </span>
          </div>
          <h3 className="text-[22px] font-normal tracking-[-0.02em] text-ink">
            First-Order Grey-Box Thermal ODE
          </h3>
          <p className="text-muted mt-1 font-mono text-[11px]">
            Model: {card.model_version} · Asset: {card.asset_id}
          </p>
        </div>

        {/* 1. ODE Equation & Parameters */}
        <div className="card-inverse p-4 mb-4">
          <span className="text-[10px] font-semibold uppercase tracking-eyebrow text-on-inverse/70 block mb-2">
            ODE Formulation
          </span>
          <div className="font-mono text-[13px] text-on-inverse">
            dθ_o / dt = (1 / τ) · (β₀ + β₁ · u² - θ_o)
          </div>
          <div className="grid grid-cols-3 gap-3 mt-4 pt-3 border-t border-on-inverse/15 text-[11px]">
            <div>
              <span className="text-on-inverse/60 block">τ (time const)</span>
              <strong className="font-mono font-medium text-[15px] text-on-inverse">{card.parameters.tau_hours.toFixed(2)}h</strong>
            </div>
            <div>
              <span className="text-on-inverse/60 block">β₀ (ambient offset)</span>
              <strong className="font-mono font-medium text-[15px] text-on-inverse">{card.parameters.beta_0.toFixed(4)}°C</strong>
            </div>
            <div>
              <span className="text-on-inverse/60 block">β₁ (load coeff)</span>
              <strong className="font-mono font-medium text-[15px] text-on-inverse">{card.parameters.beta_1.toFixed(4)}°C</strong>
            </div>
          </div>
        </div>

        {/* 2. Validation Metrics & Test Partition */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-5">
          <div className="card-muted px-4 py-3">
            <span className="eyebrow text-[10px] block mb-1">Test Accuracy</span>
            <div className="kv">
              <span>MAE</span>
              <span className="font-mono font-semibold text-ink">{card.test_metrics.mae_degc.toFixed(2)}°C</span>
            </div>
            <div className="kv">
              <span>RMSE</span>
              <span className="font-mono font-semibold text-ink">{card.test_metrics.rmse_degc.toFixed(2)}°C</span>
            </div>
            <div className="kv">
              <span>90% Coverage</span>
              <span className="font-mono font-semibold text-ink">{card.test_metrics.marginal_coverage_90_pct.toFixed(1)}%</span>
            </div>
          </div>

          <div className="card-muted px-4 py-3">
            <span className="eyebrow text-[10px] block mb-1">Qualification Status</span>
            <div className="kv">
              <span>Interpretability</span>
              <span className="font-mono text-ink-2">{card.qualification.parameter_interpretability}</span>
            </div>
            <div className="kv">
              <span>Forecast Gate</span>
              <span className="font-mono text-ink-2">{card.qualification.forecast_qualification}</span>
            </div>
            <div className="kv">
              <span>Status</span>
              <span className="font-mono font-semibold text-warn">{card.promotion.status}</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="pt-4 border-t border-line flex justify-end">
          <button onClick={onClose} className="btn btn-primary px-4">
            Close Specification
          </button>
        </div>
      </div>
    </div>
  );
};
