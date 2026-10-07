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
    ? new Date(watermarkUtc).toLocaleTimeString('en-US', {
        timeZone: 'UTC',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }) + ' UTC'
    : '2026-10-04 12:00 UTC';

  return (
    <div className="bg-white/95 backdrop-blur-md border border-[#d8e6f2] rounded-2xl p-3 sm:px-5 sm:py-3.5 shadow-sm mb-6 transition-all">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Left: Asset Selector + Live UTC Watermark */}
        <div className="flex items-center gap-3">
          <div className="h-10 flex items-center gap-2 bg-[#f4f8fc] border border-[#d2e2ef] rounded-xl px-3 text-xs font-mono font-bold text-[#0e1824] shadow-inner">
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                isBackendHealthy ? 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.7)] animate-pulse' : 'bg-amber-500'
              }`}
              title={isBackendHealthy ? 'Digital Twin Reducer Connected' : 'Degraded State'}
            />
            <select
              value={assetId}
              onChange={(e) => onAssetChange(e.target.value)}
              className="bg-transparent text-xs font-mono font-bold text-[#0e1824] focus:outline-none cursor-pointer pr-1"
            >
              <option value="tripura_dt_01">tripura_dt_01 (Agartala Substation · Unverified Nameplate)</option>
              <option value="DT-TRIPURA-001">DT-TRIPURA-001 (Legacy Alias)</option>
              <option value="TX_MOCK_STATIC_01">TX_MOCK_STATIC_01 (Trip Fixture)</option>
              <option value="CPRI_MOCK_TX_01">CPRI_MOCK_TX_01 (CPRI SCADA)</option>
            </select>
          </div>

          <div className="hidden md:flex h-10 items-center gap-2 text-xs text-[#5d768f] bg-[#f8fbfe] px-3 rounded-xl border border-[#e2edf6]">
            <Clock className="w-3.5 h-3.5 text-[#0284c7]" />
            <span className="font-mono text-xs font-semibold text-[#0e1824]">
              {formattedTime}
            </span>
          </div>
        </div>

        {/* Center: Replay Engine Deterministic Controller */}
        <div className="flex items-center gap-2">
          {/* Play / Pause Toggle */}
          <button
            onClick={() => onReplayAction(isRunning ? 'pause' : 'resume')}
            className={`h-10 inline-flex items-center gap-2 px-4 rounded-xl text-xs font-semibold shadow-sm transition-all active:scale-95 ${
              isRunning
                ? 'bg-amber-50 text-amber-900 border border-amber-300 hover:bg-amber-100'
                : 'bg-[#0e1824] text-white hover:bg-[#1a2c3f]'
            }`}
          >
            {isRunning ? (
              <>
                <Pause className="w-3.5 h-3.5 text-amber-600 fill-current" />
                <span>Pause</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current text-sky-400" />
                <span>Play Replay</span>
              </>
            )}
          </button>

          {/* Stepper Control Group */}
          <div className="h-10 flex items-center bg-[#f1f6fb] border border-[#d2e2ef] rounded-xl overflow-hidden p-0.5">
            <button
              onClick={() => onReplayAction('step', 1)}
              title="Advance exactly 1 telemetry step through deterministic reducer"
              className="h-full px-2.5 rounded-lg text-xs font-semibold text-[#0e1824] hover:bg-white hover:shadow-sm transition-all flex items-center gap-1 active:scale-95"
            >
              <StepForward className="w-3.5 h-3.5 text-[#0284c7]" />
              <span>+1</span>
            </button>
            <div className="w-px h-4 bg-[#d2e2ef] mx-0.5" />
            <button
              onClick={() => onReplayAction('step', 5)}
              title="Advance 5 telemetry steps"
              className="h-full px-2.5 rounded-lg text-xs font-semibold text-[#0e1824] hover:bg-white hover:shadow-sm transition-all active:scale-95"
            >
              +5
            </button>
          </div>

          {/* Speed Multipliers Segment */}
          <div className="hidden sm:flex h-10 items-center bg-[#f1f6fb] p-0.5 rounded-xl border border-[#d2e2ef]">
            {[
              { val: 1, label: '1×' },
              { val: 5, label: '5×' },
              { val: 10, label: '10×' },
              { val: 0, label: 'MAX' },
            ].map(({ val, label }) => (
              <button
                key={label}
                onClick={() => onSpeedChange(val)}
                className={`h-full px-2.5 rounded-lg text-[11px] font-mono font-bold transition-all ${
                  speedMultiplier === val
                    ? 'bg-white text-[#0e1824] shadow-sm'
                    : 'text-[#5d768f] hover:text-[#0e1824]'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Reset Button */}
          <button
            onClick={() => onReplayAction('reset')}
            title="Reset Replay & State Reducer"
            className="w-10 h-10 flex items-center justify-center rounded-xl text-[#5d768f] hover:text-[#0e1824] bg-[#f1f6fb] hover:bg-[#e4eff8] border border-[#d2e2ef] transition-colors active:scale-95"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Right: Chronology Buffer & Seed Trigger */}
        <div className="flex items-center gap-2.5">
          <div className="h-10 flex items-center gap-2 px-3 rounded-xl bg-[#f8fbfe] border border-[#e2edf6]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#0284c7]" />
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] tracking-wider uppercase font-bold text-[#627d98]">
                CHRONO:
              </span>
              <span className="text-xs font-mono font-bold text-[#0e1824]">
                {processed} / {total} frames
              </span>
            </div>
          </div>

          <button
            onClick={onSeedDemoData}
            disabled={isSeeding}
            title="Feed canonical telemetry frames into DuckDB storage"
            className="h-10 inline-flex items-center gap-1.5 px-3.5 rounded-xl bg-white hover:bg-[#f0f7fd] text-[#0369a1] text-xs font-semibold border border-[#b9d9f2] shadow-sm transition-all active:scale-95"
          >
            <Database className="w-3.5 h-3.5 text-[#0284c7]" />
            <span className="hidden sm:inline">{isSeeding ? 'Feeding...' : 'Seed Data'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
