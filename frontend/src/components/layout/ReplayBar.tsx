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
  selectedDataset: string;
  onDatasetChange: (dataset: string) => void;
  assetId: string;
  isTwinStarted: boolean;
  onStartTwin: () => void;
  replayStatus: ReplayStatusResponse | null;
  isPlaying: boolean;
  onPlayToggle: () => void;
  onNext: (batchSize?: number) => void;
  speedMultiplier: number;
  onSpeedChange: (speed: number) => void;
  onReset: () => void;
  isBackendHealthy: boolean;
}

export const ReplayBar: React.FC<ReplayBarProps> = ({
  selectedDataset,
  onDatasetChange,
  assetId,
  isTwinStarted,
  onStartTwin,
  replayStatus,
  isPlaying,
  onPlayToggle,
  onNext,
  speedMultiplier,
  onSpeedChange,
  onReset,
  isBackendHealthy,
}) => {
  const processed = replayStatus?.processed_events ?? 0;
  const total =
    replayStatus?.total_events && replayStatus.total_events > 0
      ? replayStatus.total_events.toLocaleString()
      : '3,659';

  // Format timestamp: if processed is 0 or current_time_utc is missing, wait for first frame
  const currentTime = replayStatus?.current_time_utc;
  const hasFrames = processed > 0 && Boolean(currentTime);
  const formattedTime = hasFrames && currentTime
    ? new Date(currentTime).toISOString().replace('T', ' ').slice(0, 19) + ' UTC'
    : 'Waiting for first telemetry frame';

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-subtle mb-6">
      {/* Top Row: Dataset Hierarchy & Primary Twin State */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2.5 mb-2.5 border-b border-slate-100">
        {/* Left: Dataset Selector */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                isBackendHealthy ? 'bg-emerald-500' : 'bg-rose-500'
              }`}
              title={isBackendHealthy ? 'Connected to digital twin server' : 'Backend offline'}
            />
            <label
              htmlFor="replay-dataset-select"
              className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1"
            >
              <Database className="w-3.5 h-3.5 text-slate-400" />
              Dataset:
            </label>
            <select
              id="replay-dataset-select"
              value={selectedDataset}
              onChange={(e) => onDatasetChange(e.target.value)}
              className="bg-slate-50 border border-slate-300 rounded px-2.5 py-1 text-xs font-medium text-slate-900 focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer"
            >
              <option value="tripura_dev">
                Tripura Transformer — Development Dataset
              </option>
              <option value="synthetic_val" disabled>
                Synthetic Validation Dataset (Coming soon / Not available yet)
              </option>
            </select>
          </div>

          {/* Contextual Asset Identity */}
          <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-500 pl-3 border-l border-slate-200">
            <span className="text-[10px] uppercase font-bold text-slate-400">Transformer:</span>
            <span className="font-mono text-[11px] font-semibold text-slate-700">
              {assetId} · Agartala Substation
            </span>
          </div>
        </div>

        {/* Right: Digital Twin Lifecycle Status & Start Action */}
        <div className="flex items-center gap-3">
          {!isTwinStarted ? (
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500 hidden lg:inline max-w-md text-right">
                Replay telemetry through the digital twin one 15-minute measurement at a time.
              </span>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                  Ready to start
                </span>
                <button
                  onClick={onStartTwin}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-all shadow-sm active:scale-95"
                >
                  <Play className="w-3.5 h-3.5 text-sky-400 fill-current" />
                  <span>Start Digital Twin</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-semibold ${
                  isPlaying
                    ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                    : 'bg-slate-100 text-slate-700 border border-slate-200'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    isPlaying ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'
                  }`}
                />
                <span>{isPlaying ? 'Twin Running' : 'Twin Paused'}</span>
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Row: Replay Controls & Frame Progress (Active After Start) */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Left: Event Timestamp */}
        <div className="flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span
            className={`font-mono text-xs ${
              hasFrames
                ? 'font-medium text-slate-800'
                : 'text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 text-[11px]'
            }`}
          >
            {formattedTime}
          </span>
        </div>

        {/* Center: Interactive Playback Controls */}
        <div className="flex items-center gap-2">
          {/* Play / Pause */}
          <button
            onClick={onPlayToggle}
            disabled={!isTwinStarted}
            title={isPlaying ? 'Pause automatic replay' : 'Play automatic replay'}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
              isPlaying
                ? 'bg-amber-100 text-amber-900 border border-amber-300 hover:bg-amber-200'
                : 'bg-slate-900 text-white hover:bg-slate-800'
            }`}
          >
            {isPlaying ? (
              <>
                <Pause className="w-3 h-3 text-amber-700" />
                <span>Pause</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3 text-sky-400 fill-current" />
                <span>Play</span>
              </>
            )}
          </button>

          {/* Stepping Controls: Next & +5 */}
          <div className="flex items-center border border-slate-200 rounded overflow-hidden">
            <button
              onClick={() => onNext(1)}
              disabled={!isTwinStarted}
              title="Process exactly the next 1 telemetry frame"
              className="px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-800 text-xs font-semibold flex items-center gap-1.5 border-r border-slate-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed active:bg-slate-200"
            >
              <StepForward className="w-3 h-3 text-sky-600" />
              <span>Next</span>
            </button>
            <button
              onClick={() => onNext(5)}
              disabled={!isTwinStarted}
              title="Process the next 5 telemetry frames"
              className="px-2.5 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed active:bg-slate-200"
            >
              +5
            </button>
          </div>

          {/* Speed Multipliers: 1x, 5x, 10x */}
          <div className="hidden sm:flex items-center border border-slate-200 rounded overflow-hidden">
            {[
              { val: 1, label: '1×' },
              { val: 5, label: '5×' },
              { val: 10, label: '10×' },
            ].map(({ val, label }) => (
              <button
                key={label}
                onClick={() => onSpeedChange(val)}
                disabled={!isTwinStarted}
                title={`Advance replay at ${label} speed`}
                className={`px-2.5 py-1.5 text-[11px] font-mono transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                  speedMultiplier === val
                    ? 'bg-slate-900 text-white font-bold'
                    : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Reset */}
          <button
            onClick={onReset}
            disabled={!isTwinStarted}
            title="Reset replay to frame 0 and clear derived state"
            className="p-1.5 text-slate-500 hover:text-slate-900 rounded hover:bg-slate-100 border border-slate-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Right: Frame Progress Count */}
        <div className="flex items-center gap-2">
          <div className="text-[11px] font-mono text-slate-700 bg-slate-50 border border-slate-200 px-2.5 py-1 rounded">
            <span className="text-slate-400 uppercase text-[10px] font-sans font-semibold mr-1.5">
              Progress:
            </span>
            <span className="font-bold text-slate-900">{processed.toLocaleString()}</span>
            <span className="text-slate-400"> / {total} frames</span>
          </div>
        </div>
      </div>
    </div>
  );
};
