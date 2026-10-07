import React from 'react';
import {
  Play,
  Pause,
  StepForward,
  RotateCcw,
  Clock,
  Database,
} from 'lucide-react';
import { ReplayStatusResponse } from '../../types/contracts';

interface ReplayBarProps {
  assetId: string;
  onAssetChange: (id: string) => void;
  replayStatus: ReplayStatusResponse | null;
  onReplayAction: (
    action: 'start' | 'pause' | 'resume' | 'step' | 'reset',
    batchSize?: number
  ) => void;
  speedMultiplier: number;
  onSpeedChange: (speed: number) => void;
  watermarkUtc?: string | null;
  isBackendHealthy: boolean;
  onSeedDemoData: () => void;
  isSeeding: boolean;
}

export const ReplayBar: React.FC<ReplayBarProps> = ({
  assetId,
  onAssetChange,
  replayStatus,
  onReplayAction,
  speedMultiplier,
  onSpeedChange,
  watermarkUtc,
  isBackendHealthy,
  onSeedDemoData,
  isSeeding,
}) => {
  const isRunning = replayStatus?.status === 'running';
  const processed = replayStatus?.processed_events ?? 0;
  const total = replayStatus?.total_events && replayStatus.total_events > 0 ? replayStatus.total_events : '—';

  const formattedTime = watermarkUtc
    ? new Date(watermarkUtc).toISOString().replace('T', ' ').slice(0, 19) + ' UTC'
    : '2026-10-04 12:00:00 UTC';

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-subtle mb-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Left: Asset Selector & UTC Watermark */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${isBackendHealthy ? 'bg-emerald-500' : 'bg-rose-500'}`}
              title={isBackendHealthy ? 'Connected to digital twin server' : 'Backend offline'}
            />
            <label htmlFor="replay-asset-select" className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Asset:
            </label>
            <select
              id="replay-asset-select"
              value={assetId}
              onChange={(e) => onAssetChange(e.target.value)}
              className="bg-slate-50 border border-slate-300 rounded px-2.5 py-1 text-xs font-mono font-medium text-slate-900 focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer"
            >
              <option value="tripura_dt_01">DT-TRIPURA-001 (Agartala Substation · 33/11kV)</option>
            </select>
          </div>

          <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-500 pl-3 border-l border-slate-200">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span className="font-mono text-[11px] text-slate-700">{formattedTime}</span>
          </div>
        </div>

        {/* Center: Replay Controls */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => onReplayAction(isRunning ? 'pause' : 'resume')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold transition-colors ${
              isRunning
                ? 'bg-amber-100 text-amber-900 border border-amber-300 hover:bg-amber-200'
                : 'bg-slate-900 text-white hover:bg-slate-800'
            }`}
          >
            {isRunning ? (
              <>
                <Pause className="w-3 h-3 text-amber-700" />
                <span>Pause</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3 text-sky-400 fill-current" />
                <span>Play Replay</span>
              </>
            )}
          </button>

          <div className="flex items-center border border-slate-200 rounded overflow-hidden">
            <button
              onClick={() => onReplayAction('step', 1)}
              title="Step forward 1 frame"
              className="px-2.5 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold flex items-center gap-1 border-r border-slate-200"
            >
              <StepForward className="w-3 h-3 text-sky-600" />
              <span>+1</span>
            </button>
            <button
              onClick={() => onReplayAction('step', 5)}
              title="Step forward 5 frames"
              className="px-2.5 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold"
            >
              +5
            </button>
          </div>

          <div className="hidden sm:flex items-center border border-slate-200 rounded overflow-hidden">
            {[
              { val: 1, label: '1x' },
              { val: 5, label: '5x' },
              { val: 10, label: '10x' },
            ].map(({ val, label }) => (
              <button
                key={label}
                onClick={() => onSpeedChange(val)}
                className={`px-2 py-1.5 text-[11px] font-mono transition-colors ${
                  speedMultiplier === val
                    ? 'bg-slate-900 text-white font-bold'
                    : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <button
            onClick={() => onReplayAction('reset')}
            title="Reset replay to initial state"
            className="p-1.5 text-slate-500 hover:text-slate-900 rounded hover:bg-slate-100 border border-slate-200 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Right: Chronology Buffer & Ingestion */}
        <div className="flex items-center gap-3">
          <div className="text-[11px] font-mono text-slate-600">
            <span className="text-slate-400 uppercase text-[10px] font-sans font-semibold mr-1">Progress:</span>
            <span className="font-semibold text-slate-900">{processed}</span>
            <span className="text-slate-400"> / {total} frames</span>
          </div>

          <button
            onClick={onSeedDemoData}
            disabled={isSeeding}
            title="Ingest canonical SCADA dataset into DuckDB storage"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-50 hover:bg-slate-100 text-slate-800 text-xs font-medium border border-slate-300 transition-colors disabled:opacity-50"
          >
            <Database className="w-3 h-3 text-sky-600" />
            <span>{isSeeding ? 'Ingesting...' : 'Ingest Dataset'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
