import React from 'react';
import { X, Cpu } from 'lucide-react';
import { ModelCardData } from '../services/api';

const fmt = (v: number | null | undefined, digits: number): string => (v == null ? '—' : v.toFixed(digits));


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

  if (!modelCard) {
    return (
      <div className="modal-backdrop">
        <div className="modal p-6 max-w-md w-full text-xs">
          <p className="text-muted">Model card unavailable: the backend has not returned a model artifact for this asset.</p>
          <button onClick={onClose} className="btn mt-4">Close</button>
        </div>
      </div>
    );
  }
  const card = modelCard;

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
          <span className="text-[11px] font-semibold uppercase tracking-eyebrow text-on-inverse/70 block mb-2">
            ODE Formulation
          </span>
          <div className="font-mono text-[13px] text-on-inverse">
            dθ_o / dt = (1 / τ) · (β₀ + β₁ · u² - θ_o)
          </div>
          <div className="grid grid-cols-3 gap-3 mt-4 pt-3 border-t border-on-inverse/15 text-[11px]">
            <div>
              <span className="text-on-inverse/60 block">τ (time const)</span>
              <strong className="font-mono font-medium text-[15px] text-on-inverse">{fmt(card.parameters?.tau_hours, 2)}h</strong>
            </div>
            <div>
              <span className="text-on-inverse/60 block">β₀ (ambient offset)</span>
              <strong className="font-mono font-medium text-[15px] text-on-inverse">{fmt(card.parameters?.beta_0, 4)}°C</strong>
            </div>
            <div>
              <span className="text-on-inverse/60 block">β₁ (load coeff)</span>
              <strong className="font-mono font-medium text-[15px] text-on-inverse">{fmt(card.parameters?.beta_1, 4)}°C</strong>
            </div>
          </div>
        </div>

        {/* 2. Validation Metrics & Test Partition */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-5">
          <div className="card-muted px-4 py-3">
            <span className="eyebrow text-[11px] block mb-1">Test Accuracy</span>
            <div className="kv">
              <span>MAE</span>
              <span className="font-mono font-semibold text-ink">{fmt(card.test_metrics?.mae_degc, 2)}°C</span>
            </div>
            <div className="kv">
              <span>RMSE</span>
              <span className="font-mono font-semibold text-ink">{fmt(card.test_metrics?.rmse_degc, 2)}°C</span>
            </div>
            <div className="kv">
              <span>90% Marginal Coverage (Test)</span>
              <span className="font-mono font-semibold text-ink">{fmt(card.test_metrics?.marginal_coverage_90_pct, 1)}%</span>
            </div>
          </div>

          <div className="card-muted px-4 py-3">
            <span className="eyebrow text-[11px] block mb-1">Qualification Status</span>
            <div className="kv">
              <span>Interpretability</span>
              <span className="font-mono text-ink-2">{card.qualification?.parameter_interpretability}</span>
            </div>
            <div className="kv">
              <span>Forecast Gate</span>
              <span className="font-mono text-ink-2">{card.qualification?.forecast_qualification}</span>
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
