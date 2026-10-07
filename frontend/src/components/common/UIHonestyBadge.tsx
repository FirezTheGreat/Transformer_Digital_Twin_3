import React from 'react';
import { Info, AlertTriangle, ShieldCheck } from 'lucide-react';

export type HonestyBadgeType =
  | 'DEMO_DEFAULT'
  | 'relative_load_index'
  | 'SYNTHETIC_SCENARIO'
  | 'GATED_EVIDENCE'
  | 'FALLBACK_PERSISTENCE';

interface UIHonestyBadgeProps {
  type: HonestyBadgeType;
  customText?: string;
  className?: string;
}

export const UIHonestyBadge: React.FC<UIHonestyBadgeProps> = ({
  type,
  customText,
  className = '',
}) => {
  switch (type) {
    case 'DEMO_DEFAULT':
      return (
        <span
          title="Standard reference parameter applied for baseline demonstration."
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200 ${className}`}
        >
          <Info className="w-3 h-3 text-slate-500" />
          <span>{customText || 'Standard Baseline'}</span>
        </span>
      );

    case 'relative_load_index':
      return (
        <span
          title="Relative load index computed against empirical dataset 95th percentile loading (142.9 kVA). Manufacturer nameplate rating is unverified."
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200 ${className}`}
        >
          <Info className="w-3 h-3 text-slate-500" />
          <span>{customText || 'Ref: 142.9 kVA (non-nameplate)'}</span>
        </span>
      );

    case 'SYNTHETIC_SCENARIO':
      return (
        <span
          title="Synthetic what-if forward projection or injected test condition, not real-time telemetry."
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-900 border border-amber-200 ${className}`}
        >
          <AlertTriangle className="w-3 h-3 text-amber-600" />
          <span>{customText || 'Simulated Scenario'}</span>
        </span>
      );

    case 'GATED_EVIDENCE':
      return (
        <span
          title="Health score calculation gated: requires multi-domain evidence corroboration or direct protection flag."
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-50 text-rose-800 border border-rose-200 ${className}`}
        >
          <AlertTriangle className="w-3 h-3 text-rose-600" />
          <span>{customText || 'Evaluation Gated'}</span>
        </span>
      );

    case 'FALLBACK_PERSISTENCE':
      return (
        <span
          title="Thermal model operating in last-observed persistence mode due to missing inputs or unpromoted model status."
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-800 border border-amber-200 ${className}`}
        >
          <ShieldCheck className="w-3 h-3 text-amber-600" />
          <span>{customText || 'Persistence Mode'}</span>
        </span>
      );

    default:
      return null;
  }
};
