import React from 'react';
import { ShieldAlert, Wrench, Clock, CheckCircle2, ArrowRight } from 'lucide-react';
import { MaintenanceRecommendation } from '../types/contracts';

interface RecommendationsListProps {
  recommendations: MaintenanceRecommendation[];
  onOpenFeedback: (rec: MaintenanceRecommendation) => void;
}

export const RecommendationsList: React.FC<RecommendationsListProps> = ({
  recommendations,
  onOpenFeedback,
}) => {
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
        <h2 className="section-title">
          Actionable Maintenance Advisories ({recommendations.length})
        </h2>
        <p className="text-xs text-muted">
          Ranked by operational priority and risk severity.
        </p>
      </div>

      {recommendations.length === 0 ? (
        <div className="card-muted p-10 text-center">
          <span className="chip chip-ok mb-3">
            <CheckCircle2 className="w-3 h-3" /> Nominal
          </span>
          <h4 className="card-title">All systems operating within standard parameters</h4>
          <p className="text-xs text-muted mt-1 max-w-sm mx-auto">
            No active maintenance actions or safety limit excursions flagged.
          </p>
        </div>
      ) : (
        <div className="card divide-y divide-line overflow-hidden">
          {recommendations.map((rec) => {
            const isP0 = rec.priority === 'P0';
            const isP1 = rec.priority === 'P1';

            return (
              <div
                key={rec.recommendation_id}
                className="p-5 hover:bg-surface-2 transition-colors grid grid-cols-1 md:grid-cols-[auto_1fr_auto] gap-x-5 gap-y-4 items-start"
              >
                {/* Priority Glyph */}
                <div
                  className={`hidden md:flex w-10 h-10 rounded-card items-center justify-center border ${
                    isP0
                      ? 'border-crit/25 bg-crit/5 text-crit'
                      : isP1
                      ? 'border-warn/25 bg-warn/5 text-warn'
                      : 'border-line bg-surface-2 text-muted'
                  }`}
                >
                  {isP0 ? (
                    <ShieldAlert className="w-[18px] h-[18px]" strokeWidth={1.75} />
                  ) : isP1 ? (
                    <Wrench className="w-[18px] h-[18px]" strokeWidth={1.75} />
                  ) : (
                    <Clock className="w-[18px] h-[18px]" strokeWidth={1.75} />
                  )}
                </div>

                {/* Details */}
                <div className="min-w-0 max-w-3xl">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <span className={`chip ${isP0 ? 'chip-crit' : isP1 ? 'chip-warn' : 'chip-neutral'}`}>
                      {rec.priority_label || `Priority ${rec.priority}`}
                    </span>

                    {rec.acknowledged && (
                      <span className="chip chip-ok normal-case tracking-normal font-medium text-[11px]">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Acknowledged in Ledger</span>
                      </span>
                    )}

                    <span className="text-[10.5px] font-mono text-muted">
                      Rule: {rec.rule_id}
                    </span>
                  </div>

                  <h4 className="text-[16px] font-medium tracking-[-0.01em] text-ink">
                    {rec.title}
                  </h4>

                  <p className="mt-1.5 text-xs text-ink-2 leading-relaxed">
                    {rec.advisory_wording}
                  </p>

                  <div className="mt-2.5 text-[11px] text-muted">
                    Standard Reference: <span className="text-ink-2 font-medium">{rec.source_reference}</span>
                  </div>
                </div>

                {/* Action Window & Button */}
                <div className="flex md:flex-col items-center md:items-end justify-between gap-3 pt-3 md:pt-0 border-t md:border-t-0 border-line">
                  <div className="md:text-right">
                    <span className="eyebrow text-[10px] block">Action Window</span>
                    <span className="text-[13px] font-medium font-mono text-ink mt-1.5 block">
                      {rec.action_window.replace(/_/g, ' ')}
                    </span>
                  </div>

                  <button
                    onClick={() => onOpenFeedback(rec)}
                    className={`btn ${rec.acknowledged ? 'btn-ghost' : 'btn-primary'}`}
                  >
                    <span>{rec.acknowledged ? 'Operator Record' : 'Acknowledge Advisory'}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
