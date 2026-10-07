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

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-subtle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                Maintenance Dispatch
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                IEEE C57.91 & CBIP Rules
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
              Prioritized Maintenance Advisories
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Deterministic rule-based recommendations mapped directly from corroborated diagnostic evidence.
            </p>
          </div>

          <UIHonestyBadge type="DEMO_DEFAULT" customText="Standard Action Windows" />
        </div>
      </div>

      {/* Priority Summary Counters */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-subtle flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-bold tracking-wider text-rose-700 block mb-0.5">
              P0 Safety Critical
            </span>
            <div className="text-2xl font-bold font-mono text-slate-900">
              {p0Count}
            </div>
            <span className="text-[11px] text-slate-500 block mt-0.5">
              Immediate action window
            </span>
          </div>
          <span className={`w-3 h-3 rounded-full ${p0Count > 0 ? 'bg-rose-600 animate-pulse' : 'bg-slate-300'}`} />
        </div>

        <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-subtle flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-bold tracking-wider text-amber-700 block mb-0.5">
              P1 Urgent Inspection
            </span>
            <div className="text-2xl font-bold font-mono text-slate-900">
              {p1Count}
            </div>
            <span className="text-[11px] text-slate-500 block mt-0.5">
              Action within 24 hours
            </span>
          </div>
          <span className={`w-3 h-3 rounded-full ${p1Count > 0 ? 'bg-amber-500' : 'bg-slate-300'}`} />
        </div>

        <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-subtle flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-bold tracking-wider text-slate-600 block mb-0.5">
              P2–P3 Planned / Review
            </span>
            <div className="text-2xl font-bold font-mono text-slate-900">
              {p2Count}
            </div>
            <span className="text-[11px] text-slate-500 block mt-0.5">
              Scheduled maintenance window
            </span>
          </div>
          <span className="w-3 h-3 rounded-full bg-slate-300" />
        </div>
      </div>

      {/* Full Recommendations List */}
      <RecommendationsList
        recommendations={recommendations}
        onOpenFeedback={onOpenFeedback}
      />
    </div>
  );
};
