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
    <div className="modal-backdrop">
      <div className="modal p-6 max-w-md w-full relative text-xs">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 icon-btn border-transparent"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="mb-5 pb-4 border-b border-line pr-10">
          <span className="eyebrow block mb-2">
            Operator Audit Ledger Action
          </span>
          <h3 className="text-[19px] font-normal tracking-[-0.015em] text-ink leading-snug">
            {recommendation.title}
          </h3>
          <p className="text-[11px] text-muted mt-1 font-mono">
            Rec: {recommendation.recommendation_id} · Priority: {recommendation.priority}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Action Choice */}
          <div>
            <label className="eyebrow text-[11px] block mb-2">
              Action Selection
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setAction('ACKNOWLEDGE')}
                className={`btn py-2 border ${
                  action === 'ACKNOWLEDGE'
                    ? 'bg-primary text-on-primary border-primary'
                    : 'bg-surface text-ink-2 border-line hover:bg-surface-2'
                }`}
              >
                Acknowledge
              </button>
              <button
                type="button"
                onClick={() => setAction('DISMISS')}
                className={`btn py-2 border ${
                  action === 'DISMISS'
                    ? 'bg-primary text-on-primary border-primary'
                    : 'bg-surface text-ink-2 border-line hover:bg-surface-2'
                }`}
              >
                Dismiss with Reason
              </button>
            </div>
          </div>

          {/* Operator ID */}
          <div>
            <label htmlFor="feedback-operator-id" className="eyebrow text-[11px] block mb-2">
              Operator Identifier
            </label>
            <div className="relative">
              <User className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
              <input
                id="feedback-operator-id"
                type="text"
                value={operatorId}
                onChange={(e) => setOperatorId(e.target.value)}
                required
                className="input pl-8 font-mono"
              />
            </div>
          </div>

          {/* Notes / Rationale */}
          <div>
            <label htmlFor="feedback-operator-notes" className="eyebrow text-[11px] block mb-2">
              Resolution Notes / Dispatch Memo
            </label>
            <textarea
              id="feedback-operator-notes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="input p-2.5 resize-none leading-relaxed"
            />
          </div>

          {error && (
            <div className="p-2.5 rounded bg-crit/5 border border-crit/25 text-crit text-[11px]">
              {error}
            </div>
          )}

          {/* Submit / Cancel Footer */}
          <div className="pt-4 border-t border-line flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-quiet"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn btn-primary px-4"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{isSubmitting ? 'Recording...' : 'Commit to Audit Ledger'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
