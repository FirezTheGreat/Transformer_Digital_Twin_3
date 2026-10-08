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
          className={`inline-flex items-center gap-1.5 px-2 py-[3px] rounded text-[10.5px] font-medium bg-surface-2 text-ink-2 border border-line whitespace-nowrap ${className}`}
        >
          <Info className="w-3 h-3 text-muted" />
          <span>{customText || 'Standard Baseline'}</span>
        </span>
      );

    case 'relative_load_index':
      return (
        <span
          title="Relative load index computed against empirical dataset 95th percentile loading (142.9 kVA). Manufacturer nameplate rating is unverified."
          className={`inline-flex items-center gap-1.5 px-2 py-[3px] rounded text-[10.5px] font-medium bg-surface-2 text-ink-2 border border-line whitespace-nowrap ${className}`}
        >
          <Info className="w-3 h-3 text-muted" />
          <span>{customText || 'Ref: 142.9 kVA (non-nameplate)'}</span>
        </span>
      );

    case 'SYNTHETIC_SCENARIO':
      return (
        <span
          title="Synthetic what-if forward projection or injected test condition, not real-time telemetry."
          className={`inline-flex items-center gap-1.5 px-2 py-[3px] rounded text-[10.5px] font-medium bg-surface-2 text-ink-2 border border-line whitespace-nowrap ${className}`}
        >
          <AlertTriangle className="w-3 h-3 text-muted" />
          <span>{customText || 'Simulated Scenario'}</span>
        </span>
      );

    case 'GATED_EVIDENCE':
      return (
        <span
          title="Health score calculation gated: requires multi-domain evidence corroboration or direct protection flag."
          className={`inline-flex items-center gap-1.5 px-2 py-[3px] rounded text-[10.5px] font-medium bg-surface-2 text-ink-2 border border-line whitespace-nowrap ${className}`}
        >
          <AlertTriangle className="w-3 h-3 text-muted" />
          <span>{customText || 'Evaluation Gated'}</span>
        </span>
      );

    case 'FALLBACK_PERSISTENCE':
      return (
        <span
          title="Thermal model operating in last-observed persistence mode due to missing inputs or unpromoted model status."
          className={`inline-flex items-center gap-1.5 px-2 py-[3px] rounded text-[10.5px] font-medium bg-surface-2 text-ink-2 border border-line whitespace-nowrap ${className}`}
        >
          <ShieldCheck className="w-3 h-3 text-muted" />
          <span>{customText || 'Persistence Mode'}</span>
        </span>
      );

    default:
      return null;
  }
};
