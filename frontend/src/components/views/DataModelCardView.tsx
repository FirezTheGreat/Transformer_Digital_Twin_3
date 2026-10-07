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
    <div className="space-y-8">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between pb-4 border-b border-[#d8e6f2] gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-[#5d768f]">
              ENGINEERING TRANSPARENCY & AUDIT
            </span>
            <span
              className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
                isPromoted
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-amber-100 text-amber-900 border border-amber-300'
              }`}
            >
              {isPromoted ? 'Model Promoted' : 'Not Validated for Prediction'} ({card.promotion.status} · Shadow Twin)
            </span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-[#0e1824] tracking-tight">
            Thermal Model Card & Audit.
          </h2>
          <p className="text-xs sm:text-sm text-[#5d768f] font-light mt-0.5">
            First-order grey-box thermal ODE parameters, qualification criteria, and test partition accuracy.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <UIHonestyBadge type="DEMO_DEFAULT" />
          <UIHonestyBadge type="relative_load_index" />
        </div>
      </div>

      {/* 1. Physical ODE Formulation */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-card border border-[#d8e6f2]">
        <div className="flex items-center gap-2 mb-3">
          <Cpu className="w-5 h-5 text-[#0284c7]" />
          <h3 className="font-editorial text-2xl font-bold text-[#0e1824]">
            First-Order Grey-Box Thermal ODE
          </h3>
        </div>

        <div className="bg-[#eff5fb] rounded-2xl p-5 border border-[#d2e3f1] my-4">
          <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-2">
            PHYSICAL DIFFERENTIAL EQUATION FORMULATION
          </span>
          <div className="font-mono text-sm text-[#0e1824] bg-white p-3.5 rounded-xl border border-[#dce8f3]">
            dθ_oil/dt = (1/τ) · [ (θ_amb + β₀ + β₁·u²) - θ_oil ]
          </div>
          <p className="text-xs text-[#5d768f] mt-2 leading-relaxed">
            Where <strong>β₀</strong> is the load-independent no-load temperature rise, <strong>β₁</strong> is the full-load rise at rated index u = 1.0, and <strong>τ</strong> is the oil thermal time constant.
          </p>
        </div>

        {/* 3 ODE Parameters */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
          <div className="bg-[#f8fbfe] p-4 rounded-2xl border border-[#dce9f4] text-center">
            <span className="text-[10px] font-bold text-[#5d768f] block">NO-LOAD RISE (β₀)</span>
            <div className="text-3xl font-extrabold font-sans text-[#0e1824] tracking-tight mt-1">
              {card.parameters.beta_0.toFixed(2)} °C
            </div>
            <span className="text-[11px] text-[#5d768f] mt-1 block font-mono">Core loss thermal driver</span>
          </div>

          <div className="bg-[#f8fbfe] p-4 rounded-2xl border border-[#dce9f4] text-center">
            <span className="text-[10px] font-bold text-[#5d768f] block">FULL-LOAD RISE (β₁)</span>
            <div className="text-3xl font-extrabold font-sans text-[#0e1824] tracking-tight mt-1">
              {card.parameters.beta_1.toFixed(2)} °C
            </div>
            <span className="text-[11px] text-[#5d768f] mt-1 block font-mono">Winding I²R loss thermal driver</span>
          </div>

          <div className="bg-[#f8fbfe] p-4 rounded-2xl border border-[#dce9f4] text-center">
            <span className="text-[10px] font-bold text-[#5d768f] block">TIME CONSTANT (τ)</span>
            <div className="text-3xl font-extrabold font-sans text-[#0e1824] tracking-tight mt-1">
              {card.parameters.tau_hours.toFixed(2)} hrs
            </div>
            <span className="text-[11px] text-[#5d768f] mt-1 block font-mono">Oil tank thermal inertia</span>
          </div>
        </div>
      </div>

      {/* 2. Calibration Metrics & Empirical Conformal Uncertainty */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Test Partition Accuracy */}
        <div className="bg-white rounded-3xl p-6 sm:p-7 shadow-card border border-[#d8e6f2]">
          <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-3">
            UNTOUCHED TEST PARTITION EVALUATION
          </span>
          <h4 className="font-editorial text-xl font-bold text-[#0e1824] mb-4">
            Model Validation Accuracy
          </h4>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between p-3 rounded-xl bg-[#eff5fb] border border-[#dce8f3]">
              <span className="text-[#354e6b]">Mean Absolute Error (MAE):</span>
              <span className="font-mono font-bold text-[#0e1824]">{card.test_metrics.mae_degc} °C</span>
            </div>
            <div className="flex justify-between p-3 rounded-xl bg-[#eff5fb] border border-[#dce8f3]">
              <span className="text-[#354e6b]">Root Mean Squared Error (RMSE):</span>
              <span className="font-mono font-bold text-[#0e1824]">{card.test_metrics.rmse_degc} °C</span>
            </div>
            <div className="flex justify-between p-3 rounded-xl bg-[#eff5fb] border border-[#dce8f3]">
              <span className="text-[#354e6b]">Marginal Coverage (90% Nominal):</span>
              <span className="font-mono font-bold text-emerald-700">
                {card.test_metrics.marginal_coverage_90_pct}% (Calibrated)
              </span>
            </div>
            <div className="flex justify-between p-3 rounded-xl bg-[#eff5fb] border border-[#dce8f3]">
              <span className="text-[#354e6b]">MAE Improvement vs Persistence:</span>
              <span className="font-mono font-bold text-emerald-700">
                +{card.promotion.mae_improvement_pct}%
              </span>
            </div>
          </div>
        </div>

        {/* Conformal Half-Widths Table */}
        <div className="bg-white rounded-3xl p-6 sm:p-7 shadow-card border border-[#d8e6f2]">
          <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-3">
            90% CONFORMAL UNCERTAINTY PATH BOUNDS
          </span>
          <h4 className="font-editorial text-xl font-bold text-[#0e1824] mb-4">
            Step-Specific Half-Widths (W_h)
          </h4>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            {card.conformal_uncertainty.horizon_half_widths_degc.map((w, idx) => (
              <div
                key={idx}
                className="p-2.5 rounded-xl bg-[#eff5fb] border border-[#dce8f3] flex justify-between"
              >
                <span className="text-[#5d768f] font-sans">Step +{(idx + 1) * 15}m:</span>
                <span className="font-bold text-[#0e1824]">±{w.toFixed(2)} °C</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 3. Rigorous Qualification Checks */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-card border border-[#d8e6f2]">
        <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-2">
          GATEWAY QUALIFICATION MATRIX
        </span>
        <h4 className="font-editorial text-2xl font-bold text-[#0e1824] mb-4">
          Physics & Identifiability Invariants
        </h4>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          {Object.entries(card.qualification).map(([k, v]) => (
            <div key={k} className="p-3.5 rounded-2xl bg-[#eff5fb] border border-[#dce9f4] text-center">
              <span className="text-[10px] uppercase font-bold text-[#5d768f] block truncate" title={k}>
                {k.replace(/_/g, ' ')}
              </span>
              <span
                className={`font-mono font-bold text-xs mt-1 block px-2 py-0.5 rounded ${
                  v === 'QUALIFIED'
                    ? 'text-emerald-800 bg-emerald-50 border border-emerald-200'
                    : 'text-amber-800 bg-amber-50 border border-amber-200'
                }`}
              >
                {v}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
