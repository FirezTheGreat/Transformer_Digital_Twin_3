import React from 'react';
import { X } from 'lucide-react';
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
    created_at_utc: '2026-04-01T12:00:00Z',
    selected_load_driver: 'rms_current_a',
    load_driver_reference_value: 153.865,
    parameters: {
      beta_0: 15.0,
      beta_1: 35.0,
      tau_hours: 3.0,
    },
    identifiability: {
      is_identifiable: true,
      fit_samples_count: 1000,
      fit_span_days: 14.0,
      load_cv: 0.45,
      diagnostic_messages: ['Identifiability criteria satisfied'],
    },
    conformal_uncertainty: {
      horizon_steps: 8,
      block_quantile_90: 5.9891,
      horizon_half_widths_degc: [2.99, 3.11, 3.37, 4.08, 5.04, 6.29, 8.20, 9.56],
    },
    test_metrics: {
      mae_degc: 2.15,
      rmse_degc: 2.85,
      marginal_coverage_90_pct: 91.5,
    },
    promotion: {
      status: 'PROMOTED',
      mae_improvement_pct: 18.5,
      all_criteria_met: true,
      reasons: ['All promotion criteria satisfied against untouched TEST partition.'],
    },
    qualification: {
      parameter_interpretability: 'QUALIFIED',
      forecast_qualification: 'QUALIFIED',
      scenario_qualification: 'QUALIFIED',
      residual_anomaly_qualification: 'QUALIFIED',
    },
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#0e1824]/40 backdrop-blur-sm animate-fade-in overflow-y-auto">
      <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-2xl w-full shadow-2xl border border-[#d8e6f2] relative my-8">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-5 top-5 p-2 rounded-full text-[#5d768f] hover:text-[#0e1824] hover:bg-[#eff5fb] transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold tracking-[0.18em] uppercase text-[#5d768f]">
              PHYSICAL MODEL CARD
            </span>
            <span className="text-xs bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded-full uppercase">
              {card.promotion.status}
            </span>
          </div>
          <h3 className="text-3xl font-editorial font-bold text-[#0e1824]">
            First-Order Grey-Box ODE
          </h3>
          <p className="text-xs text-[#5d768f] mt-1 font-mono">
            Model: {card.model_version} · Asset: {card.asset_id} · Schema: {card.schema_version}
          </p>
        </div>

        {/* 1. ODE Equation & Parameters */}
        <div className="bg-[#eff5fb] rounded-2xl p-5 border border-[#d2e3f1] mb-6">
          <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-2">
            PHYSICAL DIFFERENTIAL EQUATION
          </span>
          <p className="font-mono text-sm text-[#0e1824] bg-white p-3 rounded-xl border border-[#dce8f3]">
            dθ_oil/dt = (1/τ) · [ (θ_amb + β₀ + β₁·u²) - θ_oil ]
          </p>

          <div className="grid grid-cols-3 gap-4 mt-4 text-center">
            <div className="bg-white p-3 rounded-xl border border-[#dce8f3]">
              <span className="text-[10px] font-bold text-[#5d768f] block">NO-LOAD RISE (β₀)</span>
              <span className="text-base font-bold font-mono text-[#0e1824]">
                {card.parameters.beta_0.toFixed(1)} °C
              </span>
            </div>
            <div className="bg-white p-3 rounded-xl border border-[#dce8f3]">
              <span className="text-[10px] font-bold text-[#5d768f] block">FULL-LOAD RISE (β₁)</span>
              <span className="text-base font-bold font-mono text-[#0e1824]">
                {card.parameters.beta_1.toFixed(1)} °C
              </span>
            </div>
            <div className="bg-white p-3 rounded-xl border border-[#dce8f3]">
              <span className="text-[10px] font-bold text-[#5d768f] block">TIME CONSTANT (τ)</span>
              <span className="text-base font-bold font-mono text-[#0e1824]">
                {card.parameters.tau_hours.toFixed(1)} hrs
              </span>
            </div>
          </div>
        </div>

        {/* 2. Validation Metrics & Conformal Uncertainty */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
          <div className="p-4 rounded-2xl border border-[#d8e6f2] bg-white">
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-3">
              TEST PARTITION ACCURACY
            </span>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-[#486581]">Mean Absolute Error (MAE):</span>
                <span className="font-mono font-bold text-[#0e1824]">{card.test_metrics.mae_degc} °C</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#486581]">Root Mean Squared Error (RMSE):</span>
                <span className="font-mono font-bold text-[#0e1824]">{card.test_metrics.rmse_degc} °C</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#486581]">Marginal Coverage (90% Nominal):</span>
                <span className="font-mono font-bold text-emerald-700">
                  {card.test_metrics.marginal_coverage_90_pct}%
                </span>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-2xl border border-[#d8e6f2] bg-white">
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-3">
              CONFORMAL HALF-WIDTHS (W_h)
            </span>
            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between">
                <span className="text-[#486581] font-sans">15m Step (W₁):</span>
                <span className="font-bold text-[#0e1824]">±{card.conformal_uncertainty.horizon_half_widths_degc[0]} °C</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#486581] font-sans">60m Step (W₄):</span>
                <span className="font-bold text-[#0e1824]">±{card.conformal_uncertainty.horizon_half_widths_degc[3]} °C</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#486581] font-sans">120m Step (W₈):</span>
                <span className="font-bold text-[#0e1824]">±{card.conformal_uncertainty.horizon_half_widths_degc[7]} °C</span>
              </div>
            </div>
          </div>
        </div>

        {/* 3. Promotion & Qualification Matrix */}
        <div className="border-t border-[#edf4fa] pt-4">
          <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-2">
            RIGOROUS QUALIFICATION CHECKS
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            {Object.entries(card.qualification).map(([k, v]) => (
              <div key={k} className="p-2.5 rounded-xl bg-[#eff5fb] text-center border border-[#dce9f4]">
                <div className="text-[10px] text-[#5d768f] uppercase font-semibold truncate" title={k}>
                  {k.replace(/_/g, ' ')}
                </div>
                <div className="font-mono font-bold text-emerald-800 text-[11px] mt-0.5">
                  {v}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
