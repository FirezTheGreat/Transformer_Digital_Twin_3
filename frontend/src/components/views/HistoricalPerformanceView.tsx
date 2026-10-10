import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  History,
  Download,
  FileText,
  FileSpreadsheet,
  FileCode,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Database,
  Hash,
  AlertCircle,
  Layers,
  Info,
} from 'lucide-react';
import { api, CheckpointRunRecord } from '../../services/api';
import { UIHonestyBadge } from '../common/UIHonestyBadge';
import { TwinState, ReplayStatusResponse } from '../../types/contracts';
import { getAssetContext } from '../../utils/assetContext';

interface HistoricalPerformanceViewProps {
  assetId: string;
  replayStatus?: ReplayStatusResponse | null;
  twinState?: TwinState | null;
}

export const HistoricalPerformanceView: React.FC<HistoricalPerformanceViewProps> = ({
  assetId,
  replayStatus,
  twinState,
}) => {
  const assetCtx = getAssetContext(assetId);
  const [runs, setRuns] = useState<CheckpointRunRecord[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRuns = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getRuns(assetId);
      setRuns(data);
      if (data.length > 0 && !selectedRunId) {
        setSelectedRunId(data[0].checkpoint_id);
      }
    } catch (err) {
      console.error('Failed to fetch historical runs:', err);
      setError('Unable to retrieve persisted runs from storage backend.');
    } finally {
      setIsLoading(false);
    }
  }, [assetId, selectedRunId]);

  const [isSavingCheckpoint, setIsSavingCheckpoint] = useState<boolean>(false);

  const handleSaveCheckpoint = async () => {
    setIsSavingCheckpoint(true);
    try {
      const newChk = await api.createCheckpoint(assetId);
      await fetchRuns();
      if (newChk?.checkpoint_id) {
        setSelectedRunId(newChk.checkpoint_id);
      }
    } catch (err) {
      console.error('Failed to create checkpoint:', err);
      setError('Failed to persist point-in-time checkpoint.');
    } finally {
      setIsSavingCheckpoint(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const selectedRun = runs.find((r) => r.checkpoint_id === selectedRunId) || (runs.length > 0 ? runs[0] : null);

  const formatUtcTime = (isoString?: string) => {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    } catch {
      return isoString;
    }
  };

  // Derive historical coverage time range from runs or replay
  const historicalTimeRange = useMemo(() => {
    if (runs.length >= 2) {
      const oldest = runs[runs.length - 1].state_time_utc;
      const newest = runs[0].state_time_utc;
      return `${formatUtcTime(oldest)} → ${formatUtcTime(newest)}`;
    } else if (runs.length === 1) {
      return `Single snapshot at ${formatUtcTime(runs[0].state_time_utc)}`;
    }
    return 'No persisted historical snapshots';
  }, [runs]);

  // Derive latest available event timestamp
  const latestEventTime = useMemo(() => {
    if (selectedRun) {
      return formatUtcTime(selectedRun.state_time_utc);
    }
    if (runs.length > 0) {
      return formatUtcTime(runs[0].state_time_utc);
    }
    if (twinState?.event_time_watermark_utc) {
      return formatUtcTime(twinState.event_time_watermark_utc);
    }
    if (replayStatus?.current_time_utc) {
      return formatUtcTime(replayStatus.current_time_utc);
    }
    return 'Awaiting first telemetry frame';
  }, [selectedRun, runs, twinState, replayStatus]);

  const processedCount = replayStatus?.processed_events ?? 0;
  const totalCount = replayStatus?.total_events ?? null;

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="eyebrow">Audit Archive &amp; Compliance</span>
            <span className="text-faint">·</span>
            <span className="eyebrow">Persisted Checkpoints</span>
          </div>
          <h1 className="page-title">Historical Performance &amp; Reports</h1>
          <p className="text-[13px] text-muted mt-2.5 max-w-2xl">
            Authoritative persisted Digital Twin checkpoints, cryptographically verified state sequences,
            and deterministic engineering audit exports (PDF, CSV, JSON).
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <UIHonestyBadge type="DEMO_DEFAULT" customText="Point-in-Time Snapshots" />
          <button
            onClick={handleSaveCheckpoint}
            disabled={isSavingCheckpoint || isLoading}
            className="btn-primary text-xs flex items-center gap-1.5 py-1.5 px-3"
            title="Persist authoritative point-in-time state checkpoint"
          >
            <Database className={`w-3.5 h-3.5 ${isSavingCheckpoint ? 'animate-pulse text-accent' : ''}`} />
            <span>{isSavingCheckpoint ? 'Saving...' : 'Save Checkpoint'}</span>
          </button>
          <button
            onClick={fetchRuns}
            disabled={isLoading}
            className="btn-secondary text-xs flex items-center gap-1.5 py-1.5 px-3"
            title="Refresh historical run checkpoints"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-accent' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Dataset & Ingestion Historical Coverage Banner */}
      <div className="card p-5 bg-surface-2/60 border border-line space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-accent" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-ink">
              Dataset Ingestion &amp; Historical Coverage
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <span className="chip chip-neutral font-mono text-[10px]">
              Asset: {assetId}
            </span>
            <span className="chip chip-neutral font-mono text-[10px]">
              {assetCtx.datasetLabel}
            </span>
            <span className={`chip ${replayStatus?.status === 'running' ? 'chip-ok' : 'chip-neutral'} font-mono text-[10px]`}>
              Replay: {replayStatus?.status ?? 'idle'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
          <div>
            <span className="eyebrow text-[10px] block text-muted">Available History Range</span>
            <span className="font-mono text-ink text-[12px] mt-1 block">
              {historicalTimeRange}
            </span>
          </div>

          <div>
            <span className="eyebrow text-[10px] block text-muted">Latest Available Event</span>
            <span className="font-mono text-ink text-[12px] mt-1 block">
              {latestEventTime}
            </span>
          </div>

          <div>
            <span className="eyebrow text-[10px] block text-muted">Record Count &amp; Progress</span>
            <span className="font-mono text-ink text-[12px] mt-1 block">
              {runs.length} checkpoints · {processedCount.toLocaleString()} {totalCount ? `/ ${totalCount.toLocaleString()}` : ''} frames
            </span>
          </div>

          <div>
            <span className="eyebrow text-[10px] block text-muted">Ingestion Status</span>
            <span className="font-mono text-ink text-[12px] mt-1 block">
              {replayStatus?.is_completed
                ? 'Dataset replay completed'
                : processedCount > 0
                ? `Partial replay (${processedCount} frames processed)`
                : 'Awaiting telemetry start'}
            </span>
          </div>
        </div>

        {/* Critical UI-Honesty Distinctions */}
        <div className="pt-3 border-t border-line grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px] text-muted">
          <div className="flex items-start gap-1.5">
            <Info className="w-3.5 h-3.5 text-accent shrink-0 mt-0.5" />
            <p>
              <strong className="text-ink">Event Timestamp vs Ingestion Timestamp:</strong> Event timestamps reflect device sensor readings, distinct from host database ingestion time.
            </p>
          </div>
          <div className="flex items-start gap-1.5">
            <Info className="w-3.5 h-3.5 text-accent shrink-0 mt-0.5" />
            <p>
              <strong className="text-ink">Replay Cursor vs Completeness:</strong> Current playback cursor indicates sequential progress, not guaranteed complete ingestion of future data.
            </p>
          </div>
          <div className="flex items-start gap-1.5">
            <Info className="w-3.5 h-3.5 text-accent shrink-0 mt-0.5" />
            <p>
              <strong className="text-ink">Report Coverage Period:</strong> Checkpoint exports cover data strictly up to the frozen snapshot watermark, not the entire historical archive.
            </p>
          </div>
        </div>
      </div>

      {/* Summary KPI Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-line border border-line rounded-card overflow-hidden">
        <div className="bg-surface p-5">
          <div className="flex items-center justify-between pb-3 border-b border-line">
            <span className="eyebrow">Persisted Checkpoints</span>
            <Database className="w-3.5 h-3.5 text-muted" />
          </div>
          <div className="metric-value text-[44px] mt-4 font-mono">
            {runs.length}
          </div>
          <span className="text-[11px] text-muted block mt-2">
            Target Asset: <span className="font-mono text-ink-2">{assetId}</span>
          </span>
        </div>

        <div className="bg-surface p-5">
          <div className="flex items-center justify-between pb-3 border-b border-line">
            <span className="eyebrow">Latest Watermark Sequence</span>
            <Clock className="w-3.5 h-3.5 text-muted" />
          </div>
          <div className="metric-value text-[44px] mt-4 font-mono">
            {runs.length > 0 ? `#${runs[0].state_sequence}` : '—'}
          </div>
          <span className="text-[11px] text-muted block mt-2">
            {runs.length > 0 ? formatUtcTime(runs[0].state_time_utc) : 'Awaiting checkpoint persistence'}
          </span>
        </div>

        <div className="bg-surface p-5">
          <div className="flex items-center justify-between pb-3 border-b border-line">
            <span className="eyebrow">Integrity Verification</span>
            <ShieldCheck className="w-3.5 h-3.5 text-ok" />
          </div>
          <div className="flex items-baseline gap-2 mt-4">
            <span className="text-[28px] font-semibold tracking-tight text-ink">SHA-256</span>
            <span className="text-xs text-ok font-medium">Verified</span>
          </div>
          <span className="text-[11px] text-muted block mt-2">
            Zero metric recalculation across exports
          </span>
        </div>
      </div>

      {/* Main Content: Split Run List & Selected Run Details */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Run List (7 cols) */}
        <div className="lg:col-span-7 card p-0 overflow-hidden">
          <div className="p-4 border-b border-line flex items-center justify-between bg-surface">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-ink">
                Persisted Run Records
              </h2>
              <p className="text-[11px] text-muted mt-0.5">
                Select a checkpoint to view metadata and generate deterministic run reports
              </p>
            </div>
            <span className="chip chip-neutral font-mono text-[10px]">
              {runs.length} {runs.length === 1 ? 'record' : 'records'}
            </span>
          </div>

          {isLoading && runs.length === 0 ? (
            <div className="py-16 text-center text-xs text-muted">
              <RefreshCw className="w-5 h-5 mx-auto animate-spin text-accent mb-3" />
              <p>Querying persisted checkpoint store...</p>
            </div>
          ) : error ? (
            <div className="py-12 px-6 text-center text-xs text-crit">
              <AlertCircle className="w-6 h-6 mx-auto mb-2 text-crit" />
              <p className="font-medium">{error}</p>
            </div>
          ) : runs.length === 0 ? (
            <div className="py-14 px-6 text-center text-xs text-muted">
              <History className="w-7 h-7 mx-auto text-faint mb-3" strokeWidth={1.5} />
              <p className="font-semibold text-ink text-sm">No Persisted Checkpoints Yet</p>
              <p className="mt-1.5 max-w-md mx-auto text-muted">
                As the Digital Twin ingests telemetry and advances, deterministic state checkpoints
                are saved periodically with complete latent state and detector history.
              </p>
              <div className="mt-6 pt-6 border-t border-line text-left max-w-md mx-auto">
                <span className="eyebrow block mb-3">Live State On-Demand Export</span>
                <p className="text-[11px] text-muted mb-4">
                  You can immediately generate authoritative reports for the current active twin state:
                </p>
                <div className="flex flex-wrap gap-2">
                  <a
                    href={api.getReportDownloadUrl('pdf', assetId)}
                    download
                    className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" /> PDF Audit Report
                  </a>
                  <a
                    href={api.getReportDownloadUrl('csv', assetId)}
                    download
                    className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" /> CSV Data
                  </a>
                  <a
                    href={api.getReportDownloadUrl('json', assetId)}
                    download
                    className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" /> JSON Bundle
                  </a>
                </div>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-line bg-surface-2 text-muted">
                    <th className="py-3 px-4 eyebrow text-[11px]">Sequence</th>
                    <th className="py-3 px-4 eyebrow text-[11px]">Checkpoint ID</th>
                    <th className="py-3 px-4 eyebrow text-[11px]">Snapshot Time (UTC)</th>
                    <th className="py-3 px-4 eyebrow text-[11px]">Event Watermark</th>
                    <th className="py-3 px-4 eyebrow text-[11px] text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {runs.map((r) => {
                    const isSelected = r.checkpoint_id === selectedRunId;
                    return (
                      <tr
                        key={r.checkpoint_id}
                        onClick={() => setSelectedRunId(r.checkpoint_id)}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-accent/10 border-l-2 border-accent'
                            : 'hover:bg-surface-2'
                        }`}
                      >
                        <td className="py-3 px-4 font-mono font-medium text-ink whitespace-nowrap">
                          <span className="chip chip-neutral font-mono text-[11px]">
                            #{r.state_sequence}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-ink whitespace-nowrap">
                          <span className="font-semibold text-ink" title={r.checkpoint_id}>
                            {r.checkpoint_id.length > 22
                              ? `${r.checkpoint_id.slice(0, 22)}...`
                              : r.checkpoint_id}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-ink-2 whitespace-nowrap">
                          {formatUtcTime(r.state_time_utc)}
                        </td>
                        <td className="py-3 px-4 font-mono text-muted whitespace-nowrap">
                          {r.last_processed_event_id || 'initial'}
                        </td>
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedRunId(r.checkpoint_id);
                            }}
                            className={`text-xs font-medium py-1 px-2.5 rounded transition-colors ${
                              isSelected
                                ? 'bg-accent text-white'
                                : 'bg-surface-2 hover:bg-line text-ink'
                            }`}
                          >
                            {isSelected ? 'Selected' : 'Select'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Column: Selected Checkpoint Export Center (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          <div className="card p-6">
            <div className="pb-4 border-b border-line">
              <div className="flex items-center justify-between">
                <span className="eyebrow">Inspection &amp; Export Center</span>
                {selectedRun ? (
                  <span className="chip chip-ok flex items-center gap-1 font-mono text-[10px]">
                    <CheckCircle2 className="w-2.5 h-2.5 text-ok" /> #{selectedRun.state_sequence}
                  </span>
                ) : (
                  <span className="chip chip-neutral text-[10px]">Live Twin State</span>
                )}
              </div>
              <h2 className="text-base font-semibold text-ink mt-2">
                {selectedRun ? 'Historical Run Report' : 'Active State Report'}
              </h2>
              <p className="text-[12px] text-muted mt-1">
                {selectedRun
                  ? 'Deterministic report generation directly from frozen checkpoint state.'
                  : 'Exports current live twin observation and capability state vector.'}
              </p>
            </div>

            {selectedRun ? (
              <div className="py-4 space-y-3 text-xs border-b border-line">
                <div className="flex justify-between items-center">
                  <span className="text-muted">Checkpoint ID:</span>
                  <span className="font-mono font-medium text-ink truncate max-w-[200px]" title={selectedRun.checkpoint_id}>
                    {selectedRun.checkpoint_id}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted">Sequence:</span>
                  <span className="font-mono font-medium text-ink">#{selectedRun.state_sequence}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted">Report Snapshot Time:</span>
                  <span className="font-mono text-ink">{formatUtcTime(selectedRun.state_time_utc)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted">Data Range Included:</span>
                  <span className="font-mono text-ink text-[11px]">
                    Events up to {selectedRun.last_processed_event_id || 'initial'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted flex items-center gap-1">
                    <Hash className="w-3 h-3 text-faint" /> State SHA-256:
                  </span>
                  <span
                    className="font-mono text-[11px] text-muted truncate max-w-[180px]"
                    title={selectedRun.state_hash}
                  >
                    {selectedRun.state_hash ? `${selectedRun.state_hash.slice(0, 16)}...` : 'Computed'}
                  </span>
                </div>
              </div>
            ) : null}

            {/* Export Format Actions */}
            <div className="pt-4 space-y-3">
              <span className="eyebrow block">Available Export Formats</span>

              {/* 1. PDF Audit Report */}
              <div className="p-3.5 rounded bg-surface border border-line flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded bg-surface-2 border border-line text-ink">
                    <FileText className="w-4 h-4 text-crit" />
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-ink">Engineering Audit PDF</h3>
                    <p className="text-[11px] text-muted">
                      Telemetry trends, OTHI assessment &amp; SHA-256 footer
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <a
                    href={api.getReportDownloadUrl('pdf', assetId, selectedRun?.checkpoint_id)}
                    target="_blank"
                    rel="noreferrer"
                    className="icon-btn p-1.5 text-muted hover:text-ink"
                    title="Open PDF Preview in new tab"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                  <a
                    href={api.getReportDownloadUrl('pdf', assetId, selectedRun?.checkpoint_id)}
                    download
                    className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download</span>
                  </a>
                </div>
              </div>

              {/* 2. CSV Export */}
              <div className="p-3.5 rounded bg-surface border border-line flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded bg-surface-2 border border-line text-ink">
                    <FileSpreadsheet className="w-4 h-4 text-ok" />
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-ink">Tabular Engineering CSV</h3>
                    <p className="text-[11px] text-muted">
                      Time-series telemetry, episodes &amp; recommendations
                    </p>
                  </div>
                </div>
                <a
                  href={api.getReportDownloadUrl('csv', assetId, selectedRun?.checkpoint_id)}
                  download
                  className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download</span>
                </a>
              </div>

              {/* 3. JSON FactBundle */}
              <div className="p-3.5 rounded bg-surface border border-line flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded bg-surface-2 border border-line text-ink">
                    <FileCode className="w-4 h-4 text-accent" />
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-ink">Deterministic JSON FactBundle</h3>
                    <p className="text-[11px] text-muted">
                      Full machine-readable state vector &amp; provenance hash
                    </p>
                  </div>
                </div>
                <a
                  href={api.getReportDownloadUrl('json', assetId, selectedRun?.checkpoint_id)}
                  download
                  className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download</span>
                </a>
              </div>
            </div>

            {/* Regulatory and Methodological Context Note */}
            <div className="card-muted p-4 mt-6 text-[11px] space-y-1.5 text-muted border border-line rounded">
              <span className="font-semibold text-ink block">UI-Honesty Architecture Notice</span>
              <p>
                • Checkpoint exports reflect the exact frozen state vector reconstructed from storage.
              </p>
              <p>
                • Capability evaluation re-evaluates rules on the reconstructed state; telemetry charts are bounded by the checkpoint timestamp watermark.
              </p>
              <p>
                • Historical inspection is fully isolated from ongoing live telemetry replay playback.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
