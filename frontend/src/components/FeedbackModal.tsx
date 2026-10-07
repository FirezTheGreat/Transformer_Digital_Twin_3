import React, { useState } from 'react';
import { X, User } from 'lucide-react';
import { MaintenanceRecommendation } from '../types/contracts';
import { api } from '../services/api';

interface FeedbackModalProps {
  recommendation: MaintenanceRecommendation | null;
  assetId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (recId: string, action: string) => void;
}

export const FeedbackModal: React.FC<FeedbackModalProps> = ({
  recommendation,
  assetId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  if (!isOpen || !recommendation) return null;

  const [operatorId, setOperatorId] = useState<string>('OP-SHIVANSH-01');
  const [action, setAction] = useState<'ACKNOWLEDGE' | 'DISMISS'>('ACKNOWLEDGE');
  const [notes, setNotes] = useState<string>('Operator acknowledged telemetry advisory. Scheduled site inspection.');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await api.submitFeedback({
        asset_id: assetId,
        recommendation_id: recommendation.recommendation_id,
        merge_key: recommendation.merge_key,
        action: action,
        operator_id: operatorId,
        notes: notes,
      });

      onSuccess(recommendation.recommendation_id, action);
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Feedback recording failed';
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#0e1824]/40 backdrop-blur-sm animate-fade-in">
      <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-lg w-full shadow-2xl border border-[#d8e6f2] relative">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-5 top-5 p-2 rounded-full text-[#5d768f] hover:text-[#0e1824] hover:bg-[#eff5fb] transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="mb-6">
          <span className="text-[10px] font-bold tracking-[0.18em] uppercase text-[#5d768f] block mb-1">
            OPERATOR FEEDBACK LEDGER
          </span>
          <h3 className="text-2xl font-editorial font-bold text-[#0e1824]">
            {recommendation.title}
          </h3>
          <p className="text-xs text-[#5d768f] mt-1 font-mono">
            Recommendation ID: {recommendation.recommendation_id} · Priority: {recommendation.priority}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Action Choice */}
          <div>
            <label className="text-[10px] uppercase font-bold tracking-wider text-[#5d768f] block mb-1.5">
              LEDGER ACTION
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setAction('ACKNOWLEDGE')}
                className={`py-2.5 px-4 rounded-xl text-xs font-semibold border transition-all ${
                  action === 'ACKNOWLEDGE'
                    ? 'bg-[#0e1824] text-white border-[#0e1824] shadow-sm'
                    : 'bg-[#f8fbfe] text-[#354e6b] border-[#d2e2ef] hover:bg-[#eff5fb]'
                }`}
              >
                Acknowledge Advisory
              </button>
              <button
                type="button"
                onClick={() => setAction('DISMISS')}
                className={`py-2.5 px-4 rounded-xl text-xs font-semibold border transition-all ${
                  action === 'DISMISS'
                    ? 'bg-rose-900 text-white border-rose-900 shadow-sm'
                    : 'bg-[#f8fbfe] text-[#354e6b] border-[#d2e2ef] hover:bg-[#eff5fb]'
                }`}
              >
                Dismiss Advisory
              </button>
            </div>
          </div>

          {/* Operator ID */}
          <div>
            <label className="text-[10px] uppercase font-bold tracking-wider text-[#5d768f] block mb-1.5">
              OPERATOR BADGE ID
            </label>
            <div className="relative">
              <input
                type="text"
                value={operatorId}
                onChange={(e) => setOperatorId(e.target.value)}
                required
                className="w-full bg-[#f8fbfe] border border-[#d2e2ef] rounded-xl pl-9 pr-3.5 py-2.5 text-xs font-mono font-medium text-[#0e1824] focus:outline-none focus:ring-2 focus:ring-[#0284c7]/30"
              />
              <User className="w-4 h-4 text-[#829ab1] absolute left-3 top-2.5" />
            </div>
          </div>

          {/* Operator Notes */}
          <div>
            <label className="text-[10px] uppercase font-bold tracking-wider text-[#5d768f] block mb-1.5">
              ENGINEERING AUDIT NOTES
            </label>
            <div className="relative">
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                required
                className="w-full bg-[#f8fbfe] border border-[#d2e2ef] rounded-xl p-3 text-xs text-[#0e1824] leading-relaxed focus:outline-none focus:ring-2 focus:ring-[#0284c7]/30"
              />
            </div>
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
              {error}
            </div>
          )}

          {/* Submit Button */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full inline-flex items-center justify-center gap-2 py-3 px-6 rounded-full bg-[#0e1824] hover:bg-[#1a2c3f] text-white text-xs font-semibold shadow-pill hover:shadow-md transition-all active:scale-95"
            >
              <span>{isSubmitting ? 'Recording Event...' : 'Commit to Immutable Ledger →'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
