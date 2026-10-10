import React, { useState } from 'react';
import { X, User, CheckCircle2, AlertTriangle, FileText } from 'lucide-react';
import { MaintenanceRecommendation } from '../types/contracts';
import { api } from '../services/api';

interface FeedbackModalProps {
  recommendation: MaintenanceRecommendation | null;
  assetId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (recId: string, action: string, notes?: string, operatorId?: string) => void;
}

const P0_REASON_CODES = [
  { code: 'SITE_CLEARANCE_VERIFIED', label: 'Site Clearance Verified & Confirmed' },
  { code: 'SAFETY_PROCEDURE_COMPLETED', label: 'Substation Safety Isolation SOP Completed' },
  { code: 'TRIP_RESOLVED_AND_RESET', label: 'Protection Relay Reset & Clearance Verified' },
  { code: 'FIELD_INSPECTION_CLEARED', label: 'Physical Field Inspection Cleared' },
  { code: 'DOCUMENTED_RESOLUTION', label: 'Authorized Documented Resolution' },
];

export const FeedbackModal: React.FC<FeedbackModalProps> = ({
  recommendation,
  assetId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  if (!isOpen || !recommendation) return null;

  const isP0 = recommendation.priority === 'P0' || recommendation.rule_id === 'MNT-PROT-001';

  const [operatorId, setOperatorId] = useState<string>('OP-SHIVANSH-01');
  const [action, setAction] = useState<'ACKNOWLEDGE' | 'RESOLVE' | 'DISMISS'>('ACKNOWLEDGE');
  const [reasonCode, setReasonCode] = useState<string>(isP0 ? 'SITE_CLEARANCE_VERIFIED' : 'OPERATOR_VERIFIED');
  const [notes, setNotes] = useState<string>(
    recommendation.acknowledged
      ? 'Advisory acknowledged by operator. Maintenance inspection proceeding.'
      : 'Operator acknowledged telemetry advisory. Scheduled site inspection.'
  );
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    setError(null);

    try {
      await api.submitFeedback({
        asset_id: assetId,
        recommendation_id: recommendation.recommendation_id,
        merge_key: recommendation.merge_key,
        action: action,
        operator_id: operatorId,
        reason_code: (action === 'DISMISS' || action === 'RESOLVE') ? reasonCode : undefined,
        notes: notes,
        rationale: notes,
      });

      onSuccess(recommendation.recommendation_id, action, notes, operatorId);
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
      <div className="modal p-6 max-w-lg w-full relative text-xs">
        {/* Close Button */}
        <button
          onClick={onClose}
          disabled={isSubmitting}
          className="absolute right-4 top-4 icon-btn border-transparent"
          aria-label="Close modal"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="mb-5 pb-4 border-b border-line pr-10">
          <div className="flex items-center gap-2 mb-2">
            <span className="eyebrow">Operator Audit Ledger</span>
            <span className="text-faint">·</span>
            <span className={`chip ${isP0 ? 'chip-crit' : 'chip-neutral'} text-[10px]`}>
              Priority {recommendation.priority}
            </span>
            {recommendation.acknowledged && (
              <span className="chip chip-ok text-[10px] flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Acknowledged
              </span>
            )}
          </div>
          <h3 className="text-[17px] font-medium tracking-tight text-ink leading-snug">
            {recommendation.title}
          </h3>
          <p className="text-[11px] text-muted mt-1 font-mono">
            {recommendation.recommendation_id} · Rule: {recommendation.rule_id}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Action Choice */}
          <div>
            <label className="eyebrow text-[11px] block mb-2">
              Action Workflow Transition
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setAction('ACKNOWLEDGE')}
                className={`btn py-2 text-xs border ${
                  action === 'ACKNOWLEDGE'
                    ? 'bg-primary text-on-primary border-primary font-medium'
                    : 'bg-surface text-ink-2 border-line hover:bg-surface-2'
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Acknowledge</span>
              </button>
              <button
                type="button"
                onClick={() => setAction('RESOLVE')}
                className={`btn py-2 text-xs border ${
                  action === 'RESOLVE'
                    ? 'bg-primary text-on-primary border-primary font-medium'
                    : 'bg-surface text-ink-2 border-line hover:bg-surface-2'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Resolve</span>
              </button>
              <button
                type="button"
                onClick={() => setAction('DISMISS')}
                className={`btn py-2 text-xs border ${
                  action === 'DISMISS'
                    ? 'bg-primary text-on-primary border-primary font-medium'
                    : 'bg-surface text-ink-2 border-line hover:bg-surface-2'
                }`}
              >
                <X className="w-3.5 h-3.5" />
                <span>Dismiss</span>
              </button>
            </div>
            <p className="text-[11px] text-muted mt-1.5">
              {action === 'ACKNOWLEDGE' && 'Records operator review. Preserves advisory as acknowledged in history.'}
              {action === 'RESOLVE' && 'Documents physical fault resolution and marks advisory cleared.'}
              {action === 'DISMISS' && 'Dismisses advisory with reason code. Re-excursion re-triggers.'}
            </p>
          </div>

          {/* Structured Reason Code for P0 or Dismissal/Resolution */}
          {(action === 'DISMISS' || action === 'RESOLVE') && (
            <div>
              <label htmlFor="reason-code-select" className="eyebrow text-[11px] block mb-2 flex items-center justify-between">
                <span>Reason / Clearance Code</span>
                {isP0 && <span className="text-crit font-medium text-[10px]">P0 Mandatory Safety Code</span>}
              </label>
              {isP0 ? (
                <select
                  id="reason-code-select"
                  value={reasonCode}
                  onChange={(e) => setReasonCode(e.target.value)}
                  className="input text-xs font-mono"
                >
                  {P0_REASON_CODES.map((rc) => (
                    <option key={rc.code} value={rc.code}>
                      {rc.code} — {rc.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id="reason-code-select"
                  type="text"
                  value={reasonCode}
                  onChange={(e) => setReasonCode(e.target.value)}
                  className="input font-mono text-xs"
                  placeholder="e.g. OPERATOR_FIELD_VERIFIED"
                  required
                />
              )}
            </div>
          )}

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
                className="input pl-8 font-mono text-xs"
              />
            </div>
          </div>

          {/* Notes / Rationale */}
          <div>
            <label htmlFor="feedback-operator-notes" className="eyebrow text-[11px] block mb-2">
              Operator Memo &amp; Inspection Notes
            </label>
            <textarea
              id="feedback-operator-notes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              required
              className="input p-2.5 resize-none leading-relaxed text-xs"
              placeholder="Document operator review, site inspection dispatch, or resolution rationale..."
            />
          </div>

          {error && (
            <div className="p-3 rounded bg-crit/5 border border-crit/30 text-crit text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <strong className="block font-semibold">Submission Error</strong>
                <span>{error}</span>
              </div>
            </div>
          )}

          {/* Submit / Cancel Footer */}
          <div className="pt-4 border-t border-line flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="btn btn-quiet"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn btn-primary px-4 flex items-center gap-1.5"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{isSubmitting ? 'Recording...' : `Commit ${action}`}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
