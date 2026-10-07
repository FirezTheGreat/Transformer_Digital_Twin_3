import React from 'react';
import { AlertCircle, ShieldAlert, Info, Sparkles } from 'lucide-react';

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
          title="Demonstration parameter clearly distinguished from site-calibrated standards per UI-Honesty rules."
          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-[#e8f1f8] text-[#1c3c5c] border border-[#d2e2ef] ${className}`}
        >
          <Info className="w-3 h-3 text-[#0284c7]" />
          {customText || 'DEMO_DEFAULT'}
        </span>
      );

    case 'relative_load_index':
      return (
        <span
          title="Relative load index reported because rated kVA nameplate is unverified, avoiding ungrounded per-unit claims."
          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-[#eff5fb] text-[#354e6b] border border-[#d2e2ef] ${className}`}
        >
          <Info className="w-3 h-3 text-[#0284c7]" />
          {customText || 'relative_load_index'}
        </span>
      );

    case 'SYNTHETIC_SCENARIO':
      return (
        <span
          title="Synthetic what-if forward projection or injected test anomaly scenario, not live historical telemetry."
          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-amber-50 text-amber-900 border border-amber-200 ${className}`}
        >
          <Sparkles className="w-3 h-3 text-amber-600" />
          {customText || 'SYNTHETIC_SCENARIO'}
        </span>
      );

    case 'GATED_EVIDENCE':
      return (
        <span
          title="OTHI calculation gated: requires at least 2 current domains with medium-or-better evidence quality or 1 decisive direct protection trip."
          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-rose-50 text-rose-900 border border-rose-200 ${className}`}
        >
          <AlertCircle className="w-3 h-3 text-rose-600" />
          {customText || 'GATED: INSUFFICIENT EVIDENCE'}
        </span>
      );

    case 'FALLBACK_PERSISTENCE':
      return (
        <span
          title="Thermal model degraded to last-value persistence with empirical conformal band due to unpromoted model or missing inputs."
          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-amber-50 text-amber-900 border border-amber-200 ${className}`}
        >
          <ShieldAlert className="w-3 h-3 text-amber-600" />
          {customText || 'FALLBACK: PERSISTENCE ONLY'}
        </span>
      );

    default:
      return null;
  }
};
