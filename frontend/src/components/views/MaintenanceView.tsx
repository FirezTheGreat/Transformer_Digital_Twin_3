import React, { useState, useEffect, useMemo } from 'react';
import {
  MaintenanceRecommendation,
  ReviewFlagRecord,
  OTHIBundle,
  AnomalyEpisode,
  OperatorFeedbackEvent,
} from '../../types/contracts';
import { RecommendationsList } from '../RecommendationsList';
import { UIHonestyBadge } from '../common/UIHonestyBadge';
import {
  Flag,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingDown,
  History,
  Search,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  UserCheck,
  Activity,
  Zap,
} from 'lucide-react';
import { api } from '../../services/api';

export interface HealthHistoryEntry {
  health: OTHIBundle;
  recommendations: MaintenanceRecommendation[];
}

interface MaintenanceViewProps {
  assetId?: string;
  recommendations: MaintenanceRecommendation[];
  episodes?: AnomalyEpisode[];
  activeReviews?: ReviewFlagRecord[];
  healthHistory?: HealthHistoryEntry[];
  onOpenFeedback: (rec: MaintenanceRecommendation) => void;
  onAcknowledgeReview?: (review: ReviewFlagRecord) => void;
  onDismissReview?: (review: ReviewFlagRecord) => void;
}

interface DeteriorationEvent {
  id: string;
  assetId: string;
  timestamp: string;
  prevOthi: number;
  currentOthi: number;
  delta: number;
  drivingDomain: string | null;
  evidenceGrade: string;
  reasonCode?: string;
  recommendation?: MaintenanceRecommendation | null;
}

type AuditEventType = 'ALL' | 'OPERATOR' | 'EPISODE' | 'DETERIORATION';
type SeverityFilter = 'ALL' | 'CRITICAL' | 'WARNING';

export const MaintenanceView: React.FC<MaintenanceViewProps> = ({
  assetId = '',
  recommendations,
  episodes = [],
  activeReviews = [],
  healthHistory = [],
  onOpenFeedback,
  onAcknowledgeReview,
  onDismissReview,
}) => {
  // Mobile / responsive view tab toggle
  const [activePanelTab, setActivePanelTab] = useState<'audit' | 'advisories'>('audit');

  // Audit filters and search
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState<AuditEventType>('ALL');
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('ALL');

  // Expanded episode details state
  const [expandedEpisodes, setExpandedEpisodes] = useState<Record<string, boolean>>({});

  // Operator feedback ledger records from backend
  const [feedbackRecords, setFeedbackRecords] = useState<OperatorFeedbackEvent[]>([]);
  const [isLoadingFeedback, setIsLoadingFeedback] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  // Load backend feedback ledger
  useEffect(() => {
    if (!assetId) return;
    setIsLoadingFeedback(true);
    setFeedbackError(null);
    api
      .getFeedback({ assetId })
      .then((data) => {
        setFeedbackRecords(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        setFeedbackError(err instanceof Error ? err.message : 'Failed to load audit feedback ledger');
      })
      .finally(() => {
        setIsLoadingFeedback(false);
      });
  }, [assetId, recommendations]);

  // Compute historical deterioration events
  const deteriorationEvents = useMemo<DeteriorationEvent[]>(() => {
    const list: DeteriorationEvent[] = [];
    if (!healthHistory || healthHistory.length < 2) return list;

    for (let i = 1; i < healthHistory.length; i++) {
      const prev = healthHistory[i - 1];
      const curr = healthHistory[i];

      const pScore = prev.health.othi_score;
      const cScore = curr.health.othi_score;

      if (typeof pScore === 'number' && typeof cScore === 'number' && cScore < pScore) {
        const delta = Number((cScore - pScore).toFixed(1));
        const matchedRec = curr.recommendations.length > 0 ? curr.recommendations[0] : null;

        list.push({
          id: `det-${curr.health.timestamp_utc}-${i}`,
          assetId: curr.health.asset_id || assetId,
          timestamp: curr.health.timestamp_utc,
          prevOthi: Number(pScore.toFixed(1)),
          currentOthi: Number(cScore.toFixed(1)),
          delta,
          drivingDomain: curr.health.driving_domain ?? null,
          evidenceGrade: curr.health.evidence_grade ?? 'U',
          reasonCode: curr.health.driving_domain
            ? `DETERIORATION_DOMAIN_${curr.health.driving_domain.toUpperCase()}`
            : undefined,
          recommendation: matchedRec,
        });
      }
    }

    return list.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }, [healthHistory, assetId]);

  // Priority count calculations
  const p0Count = recommendations.filter((r) => r.priority === 'P0').length;
  const p1Count = recommendations.filter((r) => r.priority === 'P1').length;

  const openReviews = activeReviews.filter(
    (r) => r.lifecycle_state === 'OPEN' || r.lifecycle_state === 'CLEARING'
  );

  const toggleEpisodeExpand = (id: string) => {
    setExpandedEpisodes((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const formatUtcTime = (isoString?: string | null) => {
    if (!isoString) return '—';
    try {
      return new Date(isoString).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    } catch {
      return isoString;
    }
  };

  const formatDuration = (seconds?: number) => {
    if (seconds === undefined || seconds === null) return '0s';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    if (mins < 60) return `${mins}m ${secs}s`;
    const hrs = Math.floor(mins / 60);
    const remMins = mins % 60;
    return `${hrs}h ${remMins}m`;
  };

  const computeEpisodeDurationSec = (start?: string, last?: string) => {
    if (!start || !last) return 0;
    const s = new Date(start).getTime();
    const e = new Date(last).getTime();
    return Math.max(0, (e - s) / 1000);
  };

  // Build unified filtered audit items
  const auditEntries = useMemo(() => {
    interface UnifiedAuditItem {
      id: string;
      category: 'OPERATOR' | 'EPISODE' | 'DETERIORATION';
      timestamp: string;
      severity: 'CRITICAL' | 'WARNING' | 'INFO';
      title: string;
      subtitle: string;
      data: unknown;
    }

    const items: UnifiedAuditItem[] = [];

    // 1. Operator feedback items
    feedbackRecords.forEach((f) => {
      const isAck = f.action === 'ACKNOWLEDGE';
      const isResolve = f.action === 'DISMISS';
      items.push({
        id: `op-${f.feedback_id}`,
        category: 'OPERATOR',
        timestamp: f.timestamp_utc,
        severity: isResolve ? 'INFO' : isAck ? 'WARNING' : 'INFO',
        title: `Operator Action: ${f.action}`,
        subtitle: `Actor: ${f.operator_id} · Target: ${f.recommendation_id || 'Advisory'}`,
        data: f,
      });
    });

    // 2. Episodes (continuous, grouped incidents)
    episodes.forEach((ep) => {
      const isCrit = ep.state === 'CRITICAL' || ep.severity_score >= 0.75;
      const durationSec = computeEpisodeDurationSec(ep.start_time_utc, ep.last_seen_time_utc);
      items.push({
        id: `ep-${ep.episode_id}`,
        category: 'EPISODE',
        timestamp: ep.last_seen_time_utc || ep.start_time_utc,
        severity: isCrit ? 'CRITICAL' : 'WARNING',
        title: `Electrical Episode: ${ep.category.replace(/_/g, ' ')}`,
        subtitle: `State: ${ep.state} · Sustained: ${formatDuration(durationSec)} · Score: ${(ep.severity_score * 100).toFixed(0)}%`,
        data: ep,
      });
    });

    // 3. Health Deterioration items
    deteriorationEvents.forEach((det) => {
      items.push({
        id: det.id,
        category: 'DETERIORATION',
        timestamp: det.timestamp,
        severity: Math.abs(det.delta) >= 10 ? 'CRITICAL' : 'WARNING',
        title: `Authoritative Health Deterioration (${det.delta > 0 ? `+${det.delta}` : det.delta} OTHI)`,
        subtitle: `Transition: ${det.prevOthi} → ${det.currentOthi} / 100 · Domain: ${det.drivingDomain || 'Unknown'}`,
        data: det,
      });
    });

    // Sort chronologically (most recent first)
    items.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

    // Apply filters
    return items.filter((item) => {
      if (typeFilter !== 'ALL' && item.category !== typeFilter) return false;
      if (severityFilter === 'CRITICAL' && item.severity !== 'CRITICAL') return false;
      if (severityFilter === 'WARNING' && item.severity !== 'WARNING') return false;
      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        const matchesTitle = item.title.toLowerCase().includes(query);
        const matchesSub = item.subtitle.toLowerCase().includes(query);
        const matchesId = item.id.toLowerCase().includes(query);
        if (!matchesTitle && !matchesSub && !matchesId) return false;
      }
      return true;
    });
  }, [feedbackRecords, episodes, deteriorationEvents, typeFilter, severityFilter, searchTerm]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className="eyebrow">Operations &amp; Integrity Console</span>
            <span className="text-faint">·</span>
            <span className="eyebrow">IEEE C57.91 &amp; CBIP Rules</span>
            <span className="text-faint">·</span>
            <span className="eyebrow font-mono">{assetId || 'ASSET-TR-01'}</span>
          </div>
          <h1 className="page-title text-xl font-bold tracking-tight">
            History, Audit &amp; Maintenance Advisories
          </h1>
          <p className="text-xs text-muted mt-1 max-w-2xl leading-relaxed">
            Persistent episode lifecycle management, verified protection events, deterministic rule-based
            maintenance advisories, and operator feedback audit trail.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {openReviews.length > 0 && (
            <span className="badge badge-warn text-xs flex items-center gap-1.5 py-1 px-2.5">
              <Flag className="w-3.5 h-3.5 text-warn animate-pulse" />
              <span>{openReviews.length} Review Flag{openReviews.length > 1 ? 's' : ''} Active</span>
            </span>
          )}
          <UIHonestyBadge type="DEMO_DEFAULT" customText="Auditable Ledger" />
        </div>
      </div>

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 bg-surface border border-line rounded-card flex items-center justify-between">
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted block">
              P0 Critical
            </span>
            <span className={`text-2xl font-bold font-mono ${p0Count > 0 ? 'text-crit' : 'text-text'}`}>
              {p0Count}
            </span>
            <span className="text-[10px] text-muted block mt-0.5">Immediate Trip / Action</span>
          </div>
          <span className={`w-2.5 h-2.5 rounded-full ${p0Count > 0 ? 'bg-crit animate-pulse' : 'bg-line-strong'}`} />
        </div>

        <div className="p-3 bg-surface border border-line rounded-card flex items-center justify-between">
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted block">
              P1 Urgent
            </span>
            <span className={`text-2xl font-bold font-mono ${p1Count > 0 ? 'text-warn' : 'text-text'}`}>
              {p1Count}
            </span>
            <span className="text-[10px] text-muted block mt-0.5">&lt;24h Inspection Window</span>
          </div>
          <span className={`w-2.5 h-2.5 rounded-full ${p1Count > 0 ? 'bg-warn' : 'bg-line-strong'}`} />
        </div>

        <div className="p-3 bg-surface border border-line rounded-card flex items-center justify-between">
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted block">
              Active Episodes
            </span>
            <span className="text-2xl font-bold font-mono text-text">
              {episodes.filter((e) => e.state !== 'CLOSED').length}
            </span>
            <span className="text-[10px] text-muted block mt-0.5">Continuous Anomaly State</span>
          </div>
          <Zap className="w-4 h-4 text-accent/70" />
        </div>

        <div className="p-3 bg-surface border border-line rounded-card flex items-center justify-between">
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted block">
              Audit Entries
            </span>
            <span className="text-2xl font-bold font-mono text-text">
              {auditEntries.length}
            </span>
            <span className="text-[10px] text-muted block mt-0.5">Ledger &amp; State Events</span>
          </div>
          <History className="w-4 h-4 text-muted" />
        </div>
      </div>

      {/* Responsive Screen View Switcher (Visible on mobile/tablet < lg) */}
      <div className="lg:hidden flex items-center gap-2 p-1 bg-surface-2 border border-line rounded-lg">
        <button
          onClick={() => setActivePanelTab('audit')}
          className={`flex-1 py-2 px-3 text-xs font-medium rounded-md transition-all flex items-center justify-center gap-2 ${
            activePanelTab === 'audit'
              ? 'bg-surface text-text shadow-sm border border-line'
              : 'text-muted hover:text-text'
          }`}
        >
          <History className="w-3.5 h-3.5" />
          <span>Panel A: Audit Log ({auditEntries.length})</span>
        </button>
        <button
          onClick={() => setActivePanelTab('advisories')}
          className={`flex-1 py-2 px-3 text-xs font-medium rounded-md transition-all flex items-center justify-center gap-2 ${
            activePanelTab === 'advisories'
              ? 'bg-surface text-text shadow-sm border border-line'
              : 'text-muted hover:text-text'
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Panel B: Advisories ({recommendations.length})</span>
        </button>
      </div>

      {/* Two-Panel Layout on Desktop (Side-by-side) / Tabbed on Mobile */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* ========================================================= */}
        {/* PANEL A: History & Audit Log (lg:col-span-7)              */}
        {/* ========================================================= */}
        <section
          className={`lg:col-span-7 flex flex-col space-y-3 ${
            activePanelTab !== 'audit' ? 'hidden lg:flex' : 'flex'
          }`}
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-2 border-b border-line">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-accent" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-text">
                Panel A — History &amp; Audit Log
              </h2>
              <span className="badge badge-neutral text-[10px] font-mono">
                {auditEntries.length} Event{auditEntries.length === 1 ? '' : 's'}
              </span>
            </div>

            {/* Quick search input */}
            <div className="relative w-full sm:w-56">
              <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search audit log..."
                className="w-full text-xs pl-8 pr-2.5 py-1.5 bg-surface border border-line rounded focus:outline-none focus:border-accent text-text placeholder:text-muted"
              />
            </div>
          </div>

          {/* Filtering toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-muted mr-1">Type:</span>
              {(['ALL', 'OPERATOR', 'EPISODE', 'DETERIORATION'] as AuditEventType[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setTypeFilter(t)}
                  className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                    typeFilter === t
                      ? 'bg-accent/15 text-accent border border-accent/30'
                      : 'bg-surface border border-line text-muted hover:text-text'
                  }`}
                >
                  {t === 'ALL'
                    ? 'All Events'
                    : t === 'OPERATOR'
                    ? 'Operator'
                    : t === 'EPISODE'
                    ? 'Episodes'
                    : 'Health Drops'}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-muted mr-1">Severity:</span>
              {(['ALL', 'CRITICAL', 'WARNING'] as SeverityFilter[]).map((s) => (
                <button
                  key={s}
                  onClick={() => setSeverityFilter(s)}
                  className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                    severityFilter === s
                      ? s === 'CRITICAL'
                        ? 'bg-crit/15 text-crit border border-crit/30'
                        : s === 'WARNING'
                        ? 'bg-warn/15 text-warn border border-warn/30'
                        : 'bg-surface-3 text-text border border-line-strong'
                      : 'bg-surface border border-line text-muted hover:text-text'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Independent Scrolling Container for History & Audit */}
          <div className="h-[680px] overflow-y-auto border border-line rounded-card bg-surface divide-y divide-line pr-1 shadow-sm">
            {isLoadingFeedback && auditEntries.length === 0 ? (
              <div className="p-12 text-center text-xs text-muted space-y-2">
                <Activity className="w-5 h-5 mx-auto animate-spin text-accent" />
                <p>Loading audit ledger events...</p>
              </div>
            ) : feedbackError && auditEntries.length === 0 ? (
              <div className="p-8 text-center text-xs text-crit space-y-1">
                <AlertTriangle className="w-5 h-5 mx-auto mb-1 text-crit" />
                <p className="font-semibold">Failed to load audit history</p>
                <p className="text-muted text-[11px]">{feedbackError}</p>
              </div>
            ) : auditEntries.length === 0 ? (
              <div className="p-12 text-center text-xs space-y-2">
                <CheckCircle2 className="w-6 h-6 mx-auto text-ok/70 mb-2" />
                <h3 className="card-title text-sm">No Matching Audit Events</h3>
                <p className="text-muted max-w-sm mx-auto">
                  {searchTerm || typeFilter !== 'ALL' || severityFilter !== 'ALL'
                    ? 'No events match the selected filter criteria.'
                    : 'No historical health drops or operator actions recorded yet.'}
                </p>
              </div>
            ) : (
              auditEntries.map((item) => {
                if (item.category === 'EPISODE') {
                  const ep = item.data as AnomalyEpisode;
                  const isExpanded = Boolean(expandedEpisodes[ep.episode_id]);
                  const durationSec = computeEpisodeDurationSec(ep.start_time_utc, ep.last_seen_time_utc);

                  return (
                    <div
                      key={item.id}
                      className="p-3.5 hover:bg-surface-2/60 transition-colors space-y-2 text-xs"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1 flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-mono text-[11px] font-semibold text-text">
                              {ep.episode_id}
                            </span>
                            <span className="text-faint">·</span>
                            <span
                              className={`badge text-[10px] font-mono ${
                                ep.state === 'CRITICAL' ? 'badge-crit' : 'badge-warn'
                              }`}
                            >
                              {ep.state}
                            </span>
                            <span className="badge badge-neutral text-[10px] font-mono">
                              {(ep.severity_score * 100).toFixed(0)}% Sev
                            </span>
                          </div>

                          <p className="text-xs font-medium text-text">
                            {ep.primary_reason || ep.category.replace(/_/g, ' ')}
                          </p>

                          <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted">
                            <span className="flex items-center gap-1 font-mono">
                              <Clock className="w-3 h-3 text-muted" />
                              {formatUtcTime(ep.last_seen_time_utc || ep.start_time_utc)}
                            </span>
                            <span>
                              Sustained: <strong className="text-text font-mono">{formatDuration(durationSec)}</strong>
                            </span>
                            <span>
                              Evidence IDs: <strong className="text-text font-mono">{ep.evidence_ids?.length || 1}</strong>
                            </span>
                          </div>
                        </div>

                        <button
                          onClick={() => toggleEpisodeExpand(ep.episode_id)}
                          className="btn-secondary text-[11px] py-1 px-2 flex items-center gap-1 shrink-0"
                          title="Toggle Episode Evidence"
                        >
                          <span>Evidence</span>
                          {isExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>

                      {/* Expandable Episode Diagnostics & Evidence */}
                      {isExpanded && (
                        <div className="mt-2 pt-2 border-t border-line/70 space-y-2.5 bg-surface-2 p-2.5 rounded">
                          <div className="grid grid-cols-2 gap-2 text-[11px]">
                            <div>
                              <span className="text-muted block text-[10px] uppercase">First Detected</span>
                              <span className="font-mono text-text">{formatUtcTime(ep.start_time_utc)}</span>
                            </div>
                            <div>
                              <span className="text-muted block text-[10px] uppercase">Last Confirmed</span>
                              <span className="font-mono text-text">{formatUtcTime(ep.last_seen_time_utc)}</span>
                            </div>
                          </div>

                          {ep.hypothesis_codes && ep.hypothesis_codes.length > 0 && (
                            <div>
                              <span className="text-[10px] uppercase font-semibold text-muted block mb-1">
                                Engineering Hypotheses
                              </span>
                              <div className="flex flex-wrap gap-1.5">
                                {ep.hypothesis_codes.map((hc, idx) => (
                                  <span
                                    key={idx}
                                    className="p-1 px-2 rounded bg-surface border border-line text-[11px] font-mono text-text"
                                  >
                                    {hc}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {ep.evidence_ids && ep.evidence_ids.length > 0 && (
                            <div>
                              <span className="text-[10px] uppercase font-semibold text-muted block mb-1">
                                Corroborated Evidence IDs ({ep.evidence_ids.length})
                              </span>
                              <div className="max-h-32 overflow-y-auto space-y-1 pr-1 font-mono text-[10px]">
                                {ep.evidence_ids.map((evId, idx) => (
                                  <div
                                    key={idx}
                                    className="p-1 rounded bg-surface border border-line text-muted"
                                  >
                                    {evId}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                }

                if (item.category === 'OPERATOR') {
                  const f = item.data as OperatorFeedbackEvent;
                  const isAck = f.action === 'ACKNOWLEDGE';
                  const isResolve = f.action === 'DISMISS';

                  return (
                    <div
                      key={item.id}
                      className="p-3.5 hover:bg-surface-2/60 transition-colors space-y-1.5 text-xs"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1 flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className={`badge text-[10px] font-mono flex items-center gap-1 ${
                                isResolve
                                  ? 'badge-ok'
                                  : isAck
                                  ? 'badge-info'
                                  : 'badge-neutral'
                              }`}
                            >
                              <UserCheck className="w-3 h-3" />
                              {f.action}
                            </span>
                            <span className="font-mono text-[11px] font-semibold text-text">
                              {f.operator_id}
                            </span>
                            <span className="text-faint">·</span>
                            <span className="font-mono text-[11px] text-muted">
                              {formatUtcTime(f.timestamp_utc)}
                            </span>
                          </div>

                          <div className="text-xs text-text">
                            Target Advisory:{' '}
                            <span className="font-mono text-[11px] font-semibold text-accent">
                              {f.recommendation_id || 'System Flag'}
                            </span>
                          </div>

                          {f.notes && (
                            <p className="text-[11px] text-muted italic bg-surface-2 p-2 rounded border border-line">
                              &ldquo;{f.notes}&rdquo;
                            </p>
                          )}
                        </div>

                        <span className="badge badge-neutral text-[10px] font-mono shrink-0">
                          Ledger #{f.feedback_id.slice(-6)}
                        </span>
                      </div>
                    </div>
                  );
                }

                // Health Deterioration
                const det = item.data as DeteriorationEvent;
                return (
                  <div
                    key={item.id}
                    className="p-3.5 hover:bg-surface-2/60 transition-colors space-y-2 text-xs"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1 flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="chip chip-warn flex items-center gap-1 text-[11px] font-mono">
                            <TrendingDown className="w-3 h-3 text-warn" />
                            {det.delta > 0 ? `+${det.delta}` : det.delta} OTHI
                          </span>
                          <span className="font-mono text-[11px] text-muted">
                            {formatUtcTime(det.timestamp)}
                          </span>
                          <span className="chip chip-outline text-[10px]">
                            Grade {det.evidenceGrade} Evidence
                          </span>
                        </div>

                        <div className="flex flex-wrap items-baseline gap-2 text-xs text-muted">
                          <span>
                            Transition:{' '}
                            <strong className="font-mono text-text">{det.prevOthi}</strong> →{' '}
                            <strong className="font-mono text-warn">{det.currentOthi}</strong> / 100
                          </span>
                          {det.drivingDomain && (
                            <span>
                              Domain: <strong className="text-text capitalize">{det.drivingDomain.replace('_', ' ')}</strong>
                            </span>
                          )}
                        </div>

                        {det.recommendation && (
                          <div className="mt-1 p-2 rounded bg-surface-2 border border-line text-[11px] flex items-center justify-between gap-2">
                            <span className="text-text truncate">
                              [{det.recommendation.priority}] {det.recommendation.title}
                            </span>
                            <span className="font-mono text-[10px] text-muted shrink-0">
                              {det.recommendation.rule_id}
                            </span>
                          </div>
                        )}
                      </div>

                      <div className="text-right shrink-0">
                        <span className="text-[10px] uppercase text-muted block">Score Drop</span>
                        <span className="text-base font-bold font-mono text-warn">
                          {Math.abs(det.delta).toFixed(1)} pts
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </section>

        {/* ========================================================= */}
        {/* PANEL B: Maintenance Advisories (lg:col-span-5)           */}
        {/* ========================================================= */}
        <section
          className={`lg:col-span-5 flex flex-col space-y-4 ${
            activePanelTab !== 'advisories' ? 'hidden lg:flex' : 'flex'
          }`}
        >
          {/* Active Review Flags (if present) */}
          {openReviews.length > 0 && (
            <div className="border border-warn/30 bg-warn/5 rounded-card p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-warn/20 pb-2">
                <div className="flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4 text-warn" />
                  <h3 className="text-xs font-semibold text-text uppercase tracking-wider">
                    Active Review Flags ({openReviews.length})
                  </h3>
                </div>
                <span className="text-[10px] text-muted">Human-in-the-Loop</span>
              </div>

              <div className="space-y-2.5">
                {openReviews.map((rev) => (
                  <div
                    key={rev.review_id}
                    className="bg-surface border border-line rounded p-3 space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="font-semibold text-text text-xs">{rev.condition_family}</span>
                        <span className="badge badge-neutral text-[10px] font-mono">
                          {rev.condition}
                        </span>
                        <span className="badge badge-neutral text-[10px] font-mono">
                          Obs: {rev.observability}
                        </span>
                      </div>
                      <span className="badge badge-warn text-[10px] font-mono">
                        {rev.workflow_state}
                      </span>
                    </div>

                    <p className="text-[11px] text-muted leading-relaxed">
                      {rev.rationale || `Condition: ${rev.condition} · Target: ${rev.target}`}
                    </p>

                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted font-mono pt-0.5">
                      <span>Event Time: {formatUtcTime(rev.created_event_time_utc)}</span>
                      {rev.last_updated_event_time_utc && rev.last_updated_event_time_utc !== rev.created_event_time_utc && (
                        <span>· Updated: {formatUtcTime(rev.last_updated_event_time_utc)}</span>
                      )}
                      {rev.supporting_evidence_ids && rev.supporting_evidence_ids.length > 0 && (
                        <span>· Evidence: {rev.supporting_evidence_ids.join(', ')}</span>
                      )}
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-line/60">
                      <span className="text-[10px] text-muted font-mono">
                        Lifecycle: <strong className="text-text">{rev.lifecycle_state}</strong> · Rev #{rev.revision}
                      </span>

                      <div className="flex items-center gap-1.5">
                        {rev.workflow_state === 'UNACKNOWLEDGED' && onAcknowledgeReview && (
                          <button
                            onClick={() => onAcknowledgeReview(rev)}
                            className="btn-secondary text-[11px] py-1 px-2.5 flex items-center gap-1"
                          >
                            <CheckCircle2 className="w-3 h-3 text-accent" />
                            <span>Acknowledge</span>
                          </button>
                        )}
                        {onDismissReview && (
                          <button
                            onClick={() => onDismissReview(rev)}
                            className="btn-secondary text-[11px] py-1 px-2 text-muted hover:text-crit"
                          >
                            <XCircle className="w-3 h-3" />
                            <span>Dismiss</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Full Maintenance Recommendations with independent scrolling */}
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-line">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-warn" />
                <h2 className="text-sm font-semibold uppercase tracking-wider text-text">
                  Panel B — Maintenance Advisories
                </h2>
              </div>
              <span className="text-xs text-muted font-mono">
                {recommendations.length} total
              </span>
            </div>

            <RecommendationsList
              recommendations={recommendations}
              onOpenFeedback={onOpenFeedback}
            />
          </div>
        </section>
      </div>
    </div>
  );
};
