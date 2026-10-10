import React, { useState, useMemo } from 'react';
import { CheckCircle2, ArrowRight, UserCheck, Check } from 'lucide-react';
import { MaintenanceRecommendation } from '../types/contracts';

interface RecommendationsListProps {
  recommendations: MaintenanceRecommendation[];
  onOpenFeedback: (rec: MaintenanceRecommendation) => void;
  externalStatusFilter?: 'ACTIVE' | 'ACKNOWLEDGED' | 'ALL';
  onStatusFilterChange?: (filter: 'ACTIVE' | 'ACKNOWLEDGED' | 'ALL') => void;
}

export const RecommendationsList: React.FC<RecommendationsListProps> = ({
  recommendations,
  onOpenFeedback,
  externalStatusFilter,
  onStatusFilterChange,
}) => {
  const [internalFilter, setInternalFilter] = useState<'ACTIVE' | 'ACKNOWLEDGED' | 'ALL'>('ACTIVE');
  const activeFilter = externalStatusFilter ?? internalFilter;

  const setFilter = (f: 'ACTIVE' | 'ACKNOWLEDGED' | 'ALL') => {
    if (onStatusFilterChange) {
      onStatusFilterChange(f);
    } else {
      setInternalFilter(f);
    }
  };

  const activeCount = useMemo(() => recommendations.filter((r) => !r.acknowledged).length, [recommendations]);
  const ackCount = useMemo(() => recommendations.filter((r) => r.acknowledged).length, [recommendations]);
  const totalCount = recommendations.length;

  const filteredRecs = useMemo(() => {
    if (activeFilter === 'ACTIVE') return recommendations.filter((r) => !r.acknowledged);
    if (activeFilter === 'ACKNOWLEDGED') return recommendations.filter((r) => r.acknowledged);
    return recommendations;
  }, [recommendations, activeFilter]);

  const formatUtcTime = (isoString?: string | null) => {
    if (!isoString) return '—';
    try {
      return new Date(isoString).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    } catch {
      return isoString;
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header and Status Filter Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3 shrink-0">
        <div>
          <h2 className="section-title text-sm flex items-center gap-2">
            <span>Maintenance Advisories</span>
            <span className="font-mono text-xs font-normal text-muted">({filteredRecs.length})</span>
          </h2>
          <p className="text-[11px] text-muted">
            Ranked by deterministic operational priority (P0–P4) and action window.
          </p>
        </div>

        {/* Status Filter Tabs */}
        <div className="inline-flex items-center p-0.5 rounded-lg bg-surface-2 border border-line text-xs">
          <button
            type="button"
            onClick={() => setFilter('ACTIVE')}
            className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
              activeFilter === 'ACTIVE'
                ? 'bg-surface text-ink shadow-sm font-semibold'
                : 'text-muted hover:text-ink'
            }`}
          >
            Active ({activeCount})
          </button>
          <button
            type="button"
            onClick={() => setFilter('ACKNOWLEDGED')}
            className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
              activeFilter === 'ACKNOWLEDGED'
                ? 'bg-surface text-ok font-semibold shadow-sm'
                : 'text-muted hover:text-ink'
            }`}
          >
            Acknowledged ({ackCount})
          </button>
          <button
            type="button"
            onClick={() => setFilter('ALL')}
            className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
              activeFilter === 'ALL'
                ? 'bg-surface text-ink shadow-sm font-semibold'
                : 'text-muted hover:text-ink'
            }`}
          >
            All ({totalCount})
          </button>
        </div>
      </div>

      {/* Advisory Cards List */}
      {filteredRecs.length === 0 ? (
        <div className="card-muted p-8 text-center flex-1 flex flex-col items-center justify-center">
          <span className="chip chip-ok mb-2">
            <CheckCircle2 className="w-3.5 h-3.5" /> Nominal
          </span>
          <h4 className="card-title text-xs font-medium">
            {activeFilter === 'ACTIVE'
              ? activeCount === 0 && ackCount > 0
                ? 'All current advisories have been acknowledged'
                : 'No active maintenance advisories flagged'
              : activeFilter === 'ACKNOWLEDGED'
              ? 'No acknowledged advisories recorded yet'
              : 'All systems operating within standard parameters'}
          </h4>
          <p className="text-[11px] text-muted mt-1 max-w-sm mx-auto">
            {activeFilter === 'ACTIVE' && ackCount > 0
              ? `${ackCount} advisory item${ackCount > 1 ? 's are' : ' is'} acknowledged in the audit ledger.`
              : 'No unhandled safety limits or rule thresholds currently breached.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3 overflow-y-auto pr-1 flex-1">
          {filteredRecs.map((rec) => {
            const isP0 = rec.priority === 'P0';
            const isP1 = rec.priority === 'P1';

            return (
              <div
                key={rec.recommendation_id}
                className={`card p-4 transition-colors ${
                  rec.acknowledged
                    ? 'border-line/70 bg-surface/80'
                    : isP0
                    ? 'border-crit/40 bg-crit/[0.02]'
                    : isP1
                    ? 'border-warn/40 bg-warn/[0.02]'
                    : 'hover:bg-surface-2'
                }`}
              >
                <div className="flex flex-col gap-3">
                  {/* Top Bar: Priority Badge, Acknowledged Status, Rule */}
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2.5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className={`chip text-[10px] ${isP0 ? 'chip-crit' : isP1 ? 'chip-warn' : 'chip-neutral'}`}>
                        {rec.priority_label || `Priority ${rec.priority}`}
                      </span>

                      {rec.acknowledged ? (
                        <span className="chip chip-ok text-[10px] flex items-center gap-1 font-mono">
                          <Check className="w-3 h-3 text-ok" />
                          <span>Acknowledged</span>
                        </span>
                      ) : (
                        <span className="chip chip-warn text-[10px] font-mono animate-pulse">
                          Pending Review
                        </span>
                      )}

                      <span className="text-[10px] font-mono text-muted">
                        Rule: {rec.rule_id}
                      </span>
                    </div>

                    <div className="text-right">
                      <span className="eyebrow text-[9px] block">Action Window</span>
                      <span className="text-[11px] font-mono font-medium text-ink">
                        {rec.action_window.replace(/_/g, ' ')}
                      </span>
                    </div>
                  </div>

                  {/* Advisory Title & Content */}
                  <div>
                    <h4 className="text-sm font-semibold tracking-tight text-ink">
                      {rec.title}
                    </h4>

                    <p className="mt-1 text-xs text-ink-2 leading-relaxed">
                      {rec.advisory_wording}
                    </p>

                    <div className="mt-2 text-[10px] text-muted flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span>Ref: <span className="text-ink-2 font-medium">{rec.source_reference}</span></span>
                    </div>
                  </div>

                  {/* Acknowledged Audit Details Footer (if acknowledged) */}
                  {rec.acknowledged && (
                    <div className="p-2.5 rounded bg-surface-2 border border-line text-[11px] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 text-muted">
                        <UserCheck className="w-3.5 h-3.5 text-ok shrink-0" />
                        <span>Acknowledged by <strong className="font-mono text-ink">{rec.acknowledged_by || 'Operator'}</strong></span>
                        <span className="text-faint">·</span>
                        <span className="font-mono text-[10px] text-muted">{formatUtcTime(rec.acknowledged_at_utc)}</span>
                      </div>
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="flex items-center justify-end gap-2 pt-1 border-t border-line">
                    <button
                      type="button"
                      onClick={() => onOpenFeedback(rec)}
                      className={`btn text-xs py-1.5 px-3 flex items-center gap-1.5 ${
                        rec.acknowledged ? 'btn-secondary text-muted hover:text-ink' : 'btn-primary'
                      }`}
                    >
                      <span>{rec.acknowledged ? 'Update / Document Resolution' : 'Acknowledge Advisory'}</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
