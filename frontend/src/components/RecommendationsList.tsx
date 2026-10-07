import React from 'react';
import { Wrench, ShieldAlert, CheckCircle, Clock, ArrowRight, ShieldCheck } from 'lucide-react';
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
    <section className="mt-14 pb-16">
      {/* Header section matching "ROOMS ... Choose your room." */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-8 pb-4 border-b border-[#d8e6f2]">
        <div>
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#5d768f] block mb-2">
            RECOMMENDED ACTIONS
          </span>
          <p className="text-sm text-[#5d768f]">
            Deterministic rule-based policies adhering to IEEE C57.91 & CBIP standards.
          </p>
        </div>
        <h3 className="mt-3 sm:mt-0 text-3xl sm:text-5xl font-normal font-editorial text-[#0e1824] tracking-tight">
          Prioritized advisories.
        </h3>
      </div>

      {recommendations.length === 0 ? (
        <div className="bg-white rounded-3xl p-12 text-center border border-[#d8e6f2] shadow-card">
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-3">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h4 className="font-editorial text-2xl text-[#0e1824]">All systems within nominal operating limits</h4>
          <p className="text-sm text-[#5d768f] mt-1 max-w-md mx-auto">
            No active maintenance advisories or threshold trips flagged by the deterministic engine.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {recommendations.map((rec) => {
            const isP0 = rec.priority === 'P0';
            const isP1 = rec.priority === 'P1';


            return (
              <div
                key={rec.recommendation_id}
                className="bg-white rounded-3xl p-6 sm:p-7 shadow-card border border-[#d8e6f2] hover:border-[#bcd5eb] hover:shadow-card-hover transition-all flex flex-col md:flex-row md:items-center justify-between gap-6"
              >
                {/* Left Column: Icon + Details */}
                <div className="flex items-start gap-5 max-w-2xl">
                  {/* Soft diamond icon badge matching Photo 2 */}
                  <div
                    className={`w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0 border ${
                      isP0 || isP1
                        ? 'bg-amber-50/70 border-amber-200 text-amber-700'
                        : 'bg-[#eff5fb] border-[#d2e3f1] text-[#2b4c6f]'
                    }`}
                  >
                    {isP0 ? (
                      <ShieldAlert className="w-5 h-5 text-rose-600" />
                    ) : isP1 ? (
                      <Wrench className="w-5 h-5 text-amber-700" />
                    ) : (
                      <Clock className="w-5 h-5 text-[#0284c7]" />
                    )}
                  </div>

                  <div>
                    {/* Priority Tier subhead matching "ROOM TYPE" */}
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f]">
                        {rec.priority_label || `PRIORITY ${rec.priority}`}
                      </span>
                      {rec.acknowledged && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                          <CheckCircle className="w-3 h-3" /> Acknowledged
                        </span>
                      )}
                    </div>

                    {/* Headline in bold serif font matching "Deluxe" */}
                    <h4 className="text-xl sm:text-2xl font-editorial font-bold text-[#0e1824] leading-snug">
                      {rec.title}
                    </h4>

                    {/* Advisory description */}
                    <p className="mt-2 text-sm text-[#486581] leading-relaxed font-light">
                      {rec.advisory_wording}
                    </p>

                    {/* Technical rationale and standard citation */}
                    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-[#5d768f]">
                      <span className="bg-[#eff5fb] px-2.5 py-1 rounded-lg border border-[#dce8f3] font-mono">
                        Rule: {rec.rule_id}
                      </span>
                      <span className="italic">
                        {rec.source_reference}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right Column: Window Badge + Solid Black Pill Button matching "Book →" */}
                <div className="flex md:flex-col items-center md:items-end justify-between md:justify-center gap-4 flex-shrink-0 pt-4 md:pt-0 border-t md:border-t-0 border-[#f0f4f8]">
                  <div className="text-left md:text-right">
                    <span className="text-xs uppercase font-bold tracking-wider text-[#5d768f] block">
                      ACTION WINDOW
                    </span>
                    <span className="text-base sm:text-lg font-bold font-editorial text-[#0e1824]">
                      {rec.action_window.replace(/_/g, ' ')}
                    </span>
                  </div>

                  {/* Black Pill Button matching "Book →" */}
                  <button
                    onClick={() => onOpenFeedback(rec)}
                    className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-[#0e1824] hover:bg-[#1a2c3f] text-white text-xs font-semibold shadow-pill hover:shadow-md transition-all active:scale-95 group"
                  >
                    <span>{rec.acknowledged ? 'Operator Record' : 'Acknowledge'}</span>
                    <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
};
