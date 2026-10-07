import React from 'react';
import { Play, Pause, StepForward, RotateCcw, Database, ShieldAlert, Sparkles, Sliders } from 'lucide-react';
import { ReplayStatusResponse } from '../types/contracts';

interface HeroSectionProps {
  assetId: string;
  onAssetChange: (id: string) => void;
  replayStatus: ReplayStatusResponse | null;
  onReplayAction: (action: 'start' | 'pause' | 'resume' | 'step' | 'reset', batchSize?: number) => void;
  onSeedDemoData: () => void;
  onSeedTripData: () => void;
  isSeeding: boolean;
  totalEventsCount: number;
}

export const HeroSection: React.FC<HeroSectionProps> = ({
  assetId,
  onAssetChange,
  replayStatus,
  onReplayAction,
  onSeedDemoData,
  onSeedTripData,
  isSeeding,
  totalEventsCount,
}) => {
  const isRunning = replayStatus?.status === 'running';

  return (
    <section className="pt-10 pb-14">
      {/* Category Tag matching "STAYGRID EXPLORE" */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#486581]">
          TRANSFORMER DIGITAL TWIN EXPLORE
        </span>
      </div>

      {/* Massive Editorial Serif Headline matching "Find your next stay." */}
      <h1 className="text-5xl sm:text-7xl lg:text-8xl font-normal font-editorial text-[#0e1824] leading-[0.98] tracking-tight max-w-4xl">
        Monitor and <br />
        predict your grid.
      </h1>

      {/* Subtitle matching the reference style */}
      <p className="mt-6 text-lg sm:text-xl text-[#486581] max-w-2xl font-light leading-relaxed">
        Physics-grounded grey-box thermal ODE, multi-domain gated OTHI health index,
        empirical 90% conformal uncertainty, and deterministic maintenance policies.
      </p>

      {/* Meta Line matching "Discover stays across India. ... 74 stays" */}
      <div className="mt-8 flex flex-wrap items-center justify-between text-sm text-[#486581] border-b border-[#d8e6f2] pb-6 gap-4">
        <div className="flex items-center gap-3">
          <span className="inline-block w-2 h-2 rounded-full bg-[#0284c7]"></span>
          <span className="font-medium text-[#102a43]">Tripura Distribution Grid</span>
          <span className="text-[#829ab1]">·</span>
          <span>11 kV / 433 V ONAN Substation</span>
          <span className="text-[#829ab1]">·</span>
          <span className="text-xs bg-[#e2edf6] px-2.5 py-0.5 rounded-full text-[#1c3c5c] font-mono">
            Agartala Feeder
          </span>
        </div>
        <div className="flex items-center gap-2 text-right">
          <span className="font-editorial text-2xl font-bold text-[#0e1824]">
            {replayStatus?.total_events || totalEventsCount || 74}
          </span>
          <span className="text-xs tracking-wider uppercase font-semibold text-[#5d768f]">
            telemetry frames
          </span>
        </div>
      </div>

      {/* Elevated White Form / Controller Card matching the card in Photo 1 */}
      <div className="mt-8 bg-white rounded-3xl p-6 sm:p-8 shadow-card border border-[#d8e6f2] transition-shadow hover:shadow-card-hover">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
          {/* Section 1: Asset Selector */}
          <div className="md:col-span-4 border-b md:border-b-0 md:border-r border-[#e5eff8] pb-5 md:pb-0 md:pr-6">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-6 h-6 rounded-full bg-[#eff5fb] flex items-center justify-center text-[#2b4c6f]">
                <Sparkles className="w-3.5 h-3.5 text-[#0284c7]" />
              </div>
              <label className="text-[10px] tracking-[0.16em] uppercase font-bold text-[#5d768f]">
                ASSET IDENTIFIER
              </label>
            </div>
            <select
              value={assetId}
              onChange={(e) => onAssetChange(e.target.value)}
              className="w-full bg-[#f8fbfe] hover:bg-[#eff5fb] border border-[#d2e2ef] rounded-xl px-3.5 py-2.5 text-[#0e1824] font-medium text-sm focus:outline-none focus:ring-2 focus:ring-[#0284c7]/30 transition-all font-mono"
            >
              <option value="DT-TRIPURA-001">DT-TRIPURA-001 (Agartala Substation 250kVA)</option>
              <option value="TX_MOCK_STATIC_01">TX_MOCK_STATIC_01 (Trip Fixture Asset)</option>
              <option value="CPRI_MOCK_TX_01">CPRI_MOCK_TX_01 (CPRI SCADA Multi-Source)</option>
            </select>
          </div>

          {/* Section 2: Chronological Replay Controller */}
          <div className="md:col-span-5 border-b md:border-b-0 md:border-r border-[#e5eff8] pb-5 md:pb-0 md:pr-6">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-[#eff5fb] flex items-center justify-center text-[#2b4c6f]">
                  <Sliders className="w-3.5 h-3.5 text-[#0284c7]" />
                </div>
                <label className="text-[10px] tracking-[0.16em] uppercase font-bold text-[#5d768f]">
                  CHRONOLOGICAL REPLAY
                </label>
              </div>
              <span className="text-[11px] font-mono font-medium text-[#486581]">
                Cursor: {replayStatus?.processed_events ?? 0} / {replayStatus?.total_events ?? totalEventsCount}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => onReplayAction(isRunning ? 'pause' : 'resume')}
                className="flex-1 inline-flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-[#eff5fb] hover:bg-[#e1eef8] text-[#0e1824] text-xs font-semibold border border-[#d2e2ef] transition-colors"
              >
                {isRunning ? (
                  <>
                    <Pause className="w-3.5 h-3.5 text-amber-600" /> Pause Replay
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 text-[#0284c7] fill-current" /> Auto Play
                  </>
                )}
              </button>

              <button
                onClick={() => onReplayAction('step', 1)}
                title="Advance 1 Telemetry Step"
                className="inline-flex items-center justify-center gap-1 py-2 px-3 rounded-xl bg-[#0e1824] hover:bg-[#192b3d] text-white text-xs font-semibold shadow-pill transition-all active:scale-95"
              >
                <StepForward className="w-3.5 h-3.5" />
                Step +1
              </button>

              <button
                onClick={() => onReplayAction('step', 5)}
                title="Advance 5 Telemetry Steps"
                className="inline-flex items-center justify-center py-2 px-2.5 rounded-xl bg-[#eff5fb] hover:bg-[#e1eef8] text-[#0e1824] text-xs font-semibold border border-[#d2e2ef] transition-colors"
              >
                +5
              </button>

              <button
                onClick={() => onReplayAction('reset')}
                title="Reset Replay"
                className="p-2 rounded-xl text-[#5d768f] hover:text-[#0e1824] hover:bg-[#eff5fb] border border-[#d2e2ef] transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Section 3: Quick Ingest / Seed Telemetry */}
          <div className="md:col-span-3 flex flex-col justify-center">
            <label className="text-[10px] tracking-[0.16em] uppercase font-bold text-[#5d768f] mb-2 block">
              DATA STREAMING
            </label>
            <div className="flex flex-col gap-2">
              <button
                onClick={onSeedDemoData}
                disabled={isSeeding}
                className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-white hover:bg-[#f0f7fd] border border-[#bcd3e6] text-[#0e1824] text-xs font-semibold shadow-sm transition-all hover:border-[#0284c7]"
              >
                <Database className="w-3.5 h-3.5 text-[#0284c7]" />
                {isSeeding ? 'Feeding Stream...' : 'Seed Live Telemetry'}
              </button>

              <button
                onClick={onSeedTripData}
                disabled={isSeeding}
                className="w-full inline-flex items-center justify-center gap-2 py-1.5 px-3 rounded-xl bg-[#fff5f5] hover:bg-[#fee2e2] text-rose-800 text-[11px] font-semibold border border-rose-200 transition-colors"
              >
                <ShieldAlert className="w-3 h-3 text-rose-600" />
                Inject Trip Fault Fixture
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
