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
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-2 border-b border-slate-200">
        <div>
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider text-[11px]">
            Actionable Maintenance Advisories ({recommendations.length})
          </h3>
          <p className="text-xs text-slate-500">
            Ranked by operational priority and risk severity.
          </p>
        </div>
      </div>

      {recommendations.length === 0 ? (
        <div className="bg-white rounded-lg p-8 text-center border border-slate-200 shadow-subtle text-slate-500">
          <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-2">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <h4 className="text-sm font-bold text-slate-900">All systems operating within standard parameters</h4>
          <p className="text-xs text-slate-400 mt-0.5 max-w-sm mx-auto">
            No active maintenance actions or safety limit excursions flagged.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {recommendations.map((rec) => {
            const isP0 = rec.priority === 'P0';
            const isP1 = rec.priority === 'P1';

            return (
              <div
                key={rec.recommendation_id}
                className="bg-white rounded-lg p-5 border border-slate-200 shadow-subtle hover:border-slate-300 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                {/* Left: Details */}
                <div className="flex items-start gap-4 max-w-2xl">
                  <div
                    className={`p-2.5 rounded-lg flex-shrink-0 mt-0.5 ${
                      isP0
                        ? 'bg-rose-100 text-rose-800'
                        : isP1
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-slate-100 text-slate-700'
                    }`}
                  >
                    {isP0 ? (
                      <ShieldAlert className="w-5 h-5 text-rose-600" />
                    ) : isP1 ? (
                      <Wrench className="w-5 h-5 text-amber-700" />
                    ) : (
                      <Clock className="w-5 h-5 text-slate-600" />
                    )}
                  </div>

                  <div>
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span
                        className={`text-[9px] uppercase font-bold tracking-wider px-2 py-0.5 rounded ${
                          isP0
                            ? 'bg-rose-100 text-rose-800'
                            : isP1
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {rec.priority_label || `Priority ${rec.priority}`}
                      </span>

                      {rec.acknowledged && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          <span>Acknowledged in Ledger</span>
                        </span>
                      )}

                      <span className="text-[11px] font-mono text-slate-400">
                        Rule: {rec.rule_id}
                      </span>
                    </div>

                    <h4 className="text-base font-bold text-slate-900">
                      {rec.title}
                    </h4>

                    <p className="mt-1 text-xs text-slate-600 leading-relaxed">
                      {rec.advisory_wording}
                    </p>

                    <div className="mt-2 text-[11px] text-slate-400">
                      Standard Reference: <span className="text-slate-600 font-medium">{rec.source_reference}</span>
                    </div>
                  </div>
                </div>

                {/* Right: Action Window & Button */}
                <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-3 flex-shrink-0 pt-3 sm:pt-0 border-t sm:border-t-0 border-slate-100">
                  <div className="text-left sm:text-right">
                    <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 block">
                      Action Window
                    </span>
                    <span className="text-xs font-semibold font-mono text-slate-800 mt-0.5 block">
                      {rec.action_window.replace(/_/g, ' ')}
                    </span>
                  </div>

                  <button
                    onClick={() => onOpenFeedback(rec)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-colors"
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
