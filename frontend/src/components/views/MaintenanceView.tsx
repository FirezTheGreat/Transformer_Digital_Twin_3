import React from 'react';
import { Wrench, Clock, ShieldAlert } from 'lucide-react';
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
    <div className="space-y-8">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between pb-4 border-b border-[#d8e6f2] gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-[#5d768f]">
              DETERMINISTIC MAINTENANCE DISPATCH
            </span>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-[#e8f1f8] text-[#1c3c5c]">
              Rules MNT-PROT-001 ~ MNT-MODEL-007
            </span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-[#0e1824] tracking-tight">
            Maintenance Advisories.
          </h2>
          <p className="text-xs sm:text-sm text-[#5d768f] font-light mt-0.5">
            Prioritized engineering advisories grounded in IEEE C57.91, IEC 60076-7, and CBIP transformer standards.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <UIHonestyBadge type="DEMO_DEFAULT" customText="Standard Action Windows" />
        </div>
      </div>

      {/* Priority Summary Pills */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-bold tracking-wider text-rose-800 block mb-1">
              P0 SAFETY CRITICAL
            </span>
            <div className="text-3xl font-extrabold font-sans text-[#0e1824] tracking-tight">
              {p0Count}
            </div>
            <span className="text-[11px] text-[#5d768f] mt-1 block">
              Immediate action window
            </span>
          </div>
          <ShieldAlert className="w-8 h-8 text-rose-600/70" />
        </div>

        <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-bold tracking-wider text-amber-800 block mb-1">
              P1 URGENT INSPECTION
            </span>
            <div className="text-3xl font-extrabold font-sans text-[#0e1824] tracking-tight">
              {p1Count}
            </div>
            <span className="text-[11px] text-[#5d768f] mt-1 block">
              Within 24 hours window
            </span>
          </div>
          <Wrench className="w-8 h-8 text-amber-600/70" />
        </div>

        <div className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-bold tracking-wider text-[#1c3c5c] block mb-1">
              P2–P3 PLANNED / MONITOR
            </span>
            <div className="text-3xl font-extrabold font-sans text-[#0e1824] tracking-tight">
              {p2Count}
            </div>
            <span className="text-[11px] text-[#5d768f] mt-1 block">
              Next authorized maintenance window
            </span>
          </div>
          <Clock className="w-8 h-8 text-[#0284c7]/70" />
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
