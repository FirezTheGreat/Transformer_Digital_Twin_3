import React, { useState } from 'react';
import { X, User, CheckCircle2 } from 'lucide-react';
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div className="bg-white rounded-lg p-6 max-w-md w-full shadow-elevated border border-slate-200 relative text-xs">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 p-1.5 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="mb-4 pb-3 border-b border-slate-200 pr-8">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono block mb-1">
            Operator Audit Ledger Action
          </span>
          <h3 className="text-base font-bold text-slate-900">
            {recommendation.title}
          </h3>
          <p className="text-[11px] text-slate-500 mt-0.5 font-mono">
            Rec: {recommendation.recommendation_id} · Priority: {recommendation.priority}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {/* Action Choice */}
          <div>
            <label className="text-[10px] uppercase font-bold tracking-wider text-slate-500 block mb-1">
              Action Selection
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setAction('ACKNOWLEDGE')}
                className={`py-2 px-3 rounded text-xs font-semibold border transition-colors ${
                  action === 'ACKNOWLEDGE'
                    ? 'bg-slate-900 text-white border-slate-900'
                    : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100'
                }`}
              >
                Acknowledge
              </button>
              <button
                type="button"
                onClick={() => setAction('DISMISS')}
                className={`py-2 px-3 rounded text-xs font-semibold border transition-colors ${
                  action === 'DISMISS'
                    ? 'bg-slate-900 text-white border-slate-900'
                    : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100'
                }`}
              >
                Dismiss with Reason
              </button>
            </div>
          </div>

          {/* Operator ID */}
          <div>
            <label htmlFor="feedback-operator-id" className="text-[10px] uppercase font-bold tracking-wider text-slate-500 block mb-1">
              Operator Identifier
            </label>
            <div className="relative">
              <User className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
              <input
                id="feedback-operator-id"
                type="text"
                value={operatorId}
                onChange={(e) => setOperatorId(e.target.value)}
                required
                className="w-full pl-8 pr-3 py-1.5 bg-slate-50 border border-slate-300 rounded font-mono text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
            </div>
          </div>

          {/* Notes / Rationale */}
          <div>
            <label htmlFor="feedback-operator-notes" className="text-[10px] uppercase font-bold tracking-wider text-slate-500 block mb-1">
              Resolution Notes / Dispatch Memo
            </label>
            <textarea
              id="feedback-operator-notes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full p-2.5 bg-slate-50 border border-slate-300 rounded text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-sky-500 resize-none"
            />
          </div>

          {error && (
            <div className="p-2 rounded bg-rose-50 border border-rose-200 text-rose-800 text-[11px]">
              {error}
            </div>
          )}

          {/* Submit / Cancel Footer */}
          <div className="pt-3 border-t border-slate-200 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded text-slate-600 hover:text-slate-900 text-xs font-medium"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-colors disabled:opacity-50"
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-sky-400" />
              <span>{isSubmitting ? 'Recording...' : 'Commit to Audit Ledger'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
