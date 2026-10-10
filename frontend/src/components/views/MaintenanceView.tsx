import React from 'react';
import { MaintenanceRecommendation, ReviewFlagRecord } from '../../types/contracts';
import { RecommendationsList } from '../RecommendationsList';
import { UIHonestyBadge } from '../common/UIHonestyBadge';
import { Flag, ShieldAlert, CheckCircle2, XCircle, Clock } from 'lucide-react';

interface MaintenanceViewProps {
  recommendations: MaintenanceRecommendation[];
  activeReviews?: ReviewFlagRecord[];
  onOpenFeedback: (rec: MaintenanceRecommendation) => void;
  onAcknowledgeReview?: (review: ReviewFlagRecord) => void;
  onDismissReview?: (review: ReviewFlagRecord) => void;
}

export const MaintenanceView: React.FC<MaintenanceViewProps> = ({
  recommendations,
  activeReviews = [],
  onOpenFeedback,
  onAcknowledgeReview,
  onDismissReview,
}) => {
  const p0Count = recommendations.filter((r) => r.priority === 'P0').length;
  const p1Count = recommendations.filter((r) => r.priority === 'P1').length;
  const p2Count = recommendations.filter((r) => r.priority === 'P2' || r.priority === 'P3').length;

  const openReviews = activeReviews.filter(
    (r) => r.lifecycle_state === 'OPEN' || r.lifecycle_state === 'CLEARING'
  );

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
          <h1 className="page-title">Maintenance Advisories &amp; Review Flags</h1>
          <p className="text-[13px] text-muted mt-2.5 max-w-2xl">
            Deterministic rule-based recommendations mapped directly from corroborated diagnostic evidence,
            with auditable operator review lifecycle controls.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {openReviews.length > 0 && (
            <span className="badge badge-warn text-xs flex items-center gap-1.5 py-1 px-2.5">
              <Flag className="w-3.5 h-3.5 text-warn animate-pulse" />
              <span>{openReviews.length} Review Flag{openReviews.length > 1 ? 's' : ''} Active</span>
            </span>
          )}
          <UIHonestyBadge type="DEMO_DEFAULT" customText="Standard Action Windows" />
        </div>
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

      {/* Active Review Flags Section */}
      {openReviews.length > 0 && (
        <div className="border border-warn/30 bg-warn/5 rounded-card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-warn/20 pb-3">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-warn" />
              <h2 className="text-sm font-semibold text-text uppercase tracking-wider">
                Active Review Flags (Human-in-the-Loop)
              </h2>
            </div>
            <span className="text-xs text-muted">
              Observed behaviour warrants human review; evidence does not support an unqualified conclusion.
            </span>
          </div>

          <div className="space-y-3">
            {openReviews.map((rev) => (
              <div
                key={rev.review_id}
                className="bg-surface border border-line rounded p-4 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-xs text-text">{rev.condition_family}</span>
                    <span className="text-xs text-faint">·</span>
                    <span className="text-xs text-muted font-mono">{rev.target}</span>
                    <span className={`badge text-[10px] uppercase font-mono ${
                      rev.workflow_state === 'ACKNOWLEDGED' ? 'badge-info' : 'badge-warn'
                    }`}>
                      {rev.workflow_state}
                    </span>
                    <span className="badge badge-neutral text-[10px] font-mono">
                      Rev #{rev.revision}
                    </span>
                  </div>
                  <p className="text-xs text-muted leading-relaxed">
                    {rev.rationale || `Condition: ${rev.condition} · Observability: ${rev.observability}`}
                  </p>
                  <div className="flex items-center gap-4 text-[11px] text-faint">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      Updated: {rev.last_updated_event_time_utc?.slice(0, 19).replace('T', ' ')} UTC
                    </span>
                    <span>Lifecycle: {rev.lifecycle_state}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {rev.workflow_state === 'UNACKNOWLEDGED' && onAcknowledgeReview && (
                    <button
                      onClick={() => onAcknowledgeReview(rev)}
                      className="btn-secondary text-xs flex items-center gap-1 py-1.5 px-3"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 text-accent" />
                      <span>Acknowledge</span>
                    </button>
                  )}
                  {onDismissReview && (
                    <button
                      onClick={() => onDismissReview(rev)}
                      className="btn-secondary text-xs flex items-center gap-1 py-1.5 px-3 text-muted hover:text-crit"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Dismiss</span>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Full Recommendations List */}
      <RecommendationsList
        recommendations={recommendations}
        onOpenFeedback={onOpenFeedback}
      />
    </div>
  );
};
