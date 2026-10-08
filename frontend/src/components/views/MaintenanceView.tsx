import React from 'react';
import { MaintenanceRecommendation } from '../../types/contracts';
import { RecommendationsList } from '../RecommendationsList';
import { UIHonestyBadge } from '../common/UIHonestyBadge';

interface MaintenanceViewProps {
  recommendations: MaintenanceRecommendation[];
  onOpenFeedback: (rec: MaintenanceRecommendation) => void;
}

export const MaintenanceView: React.FC<MaintenanceViewProps> = ({
  recommendations,
  onOpenFeedback,
}) => {
  const p0Count = recommendations.filter((r) => r.priority === 'P0').length;
  const p1Count = recommendations.filter((r) => r.priority === 'P1').length;
  const p2Count = recommendations.filter((r) => r.priority === 'P2' || r.priority === 'P3').length;

  const counters = [
    {
      label: 'P0 Safety Critical',
      count: p0Count,
      note: 'Immediate action window',
      dot: p0Count > 0 ? 'bg-crit animate-pulse' : 'bg-line-strong',
      inverse: true,
    },
    {
      label: 'P1 Urgent Inspection',
      count: p1Count,
      note: 'Action within 24 hours',
      dot: p1Count > 0 ? 'bg-warn' : 'bg-line-strong',
      inverse: false,
    },
    {
      label: 'P2–P3 Planned / Review',
      count: p2Count,
      note: 'Scheduled maintenance window',
      dot: 'bg-line-strong',
      inverse: false,
    },
  ];

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="eyebrow">Maintenance Dispatch</span>
            <span className="text-faint">·</span>
            <span className="eyebrow">IEEE C57.91 &amp; CBIP Rules</span>
          </div>
          <h1 className="page-title">Maintenance Advisories</h1>
          <p className="text-[13px] text-muted mt-2.5 max-w-2xl">
            Deterministic rule-based recommendations mapped directly from corroborated diagnostic evidence.
          </p>
        </div>

        <UIHonestyBadge type="DEMO_DEFAULT" customText="Standard Action Windows" />
      </div>

      {/* Priority Summary Counters */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-line border border-line rounded-card overflow-hidden">
        {counters.map((c) => (
          <div key={c.label} className={c.inverse ? 'bg-inverse text-on-inverse p-5' : 'bg-surface p-5'}>
            <div
              className={`flex items-center justify-between pb-3 border-b ${
                c.inverse ? 'border-on-inverse/15' : 'border-line'
              }`}
            >
              <span
                className={`text-[11px] font-semibold uppercase tracking-eyebrow leading-none ${
                  c.inverse ? 'text-on-inverse/70' : 'text-muted'
                }`}
              >
                {c.label}
              </span>
              <span className={`dot w-2 h-2 ${c.dot}`} />
            </div>
            <div className={`metric-value text-[44px] mt-4 ${c.inverse ? 'text-on-inverse' : ''}`}>
              {c.count}
            </div>
            <span className={`text-[11px] block mt-2 ${c.inverse ? 'text-on-inverse/60' : 'text-muted'}`}>
              {c.note}
            </span>
          </div>
        ))}
      </div>

      {/* Full Recommendations List */}
      <RecommendationsList
        recommendations={recommendations}
        onOpenFeedback={onOpenFeedback}
      />
    </div>
  );
};
