import React, { useState, useEffect, useCallback } from 'react';
import { Navbar } from './components/Navbar';
import { ReplayBar } from './components/layout/ReplayBar';
import { OverviewView } from './components/views/OverviewView';
import { TwinAnalysisView } from './components/views/TwinAnalysisView';
import { AnomalyTimelineView } from './components/views/AnomalyTimelineView';
import { MaintenanceView } from './components/views/MaintenanceView';
import { TelemetryView } from './components/views/TelemetryView';
import { DataModelCardView } from './components/views/DataModelCardView';
import { Transformer3DView } from './components/views/Transformer3DView';
import { FeedbackModal } from './components/FeedbackModal';
import { ModelCardModal } from './components/ModelCardModal';

import {
  TwinState,
  OTHIBundle,
  MaintenanceRecommendation,
  AnomalyEpisode,
  CapabilityManifest,
  ReplayStatusResponse,
  CanonicalEvent,
} from './types/contracts';
import { api, ModelCardData } from './services/api';
import { INITIAL_FACT_BUNDLE, SEED_TELEMETRY_EVENTS } from './data/initialData';

export default function App(): React.ReactElement {
  const [assetId, setAssetId] = useState<string>('tripura_dt_01');
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<string>('overview');

  // Core Twin State
  const [twinState, setTwinState] = useState<TwinState | null>(INITIAL_FACT_BUNDLE.twin_state);
  const [health, setHealth] = useState<OTHIBundle | null>(INITIAL_FACT_BUNDLE.health);
  const [recommendations, setRecommendations] = useState<MaintenanceRecommendation[]>(
    INITIAL_FACT_BUNDLE.active_recommendations
  );
  const [episodes, setEpisodes] = useState<AnomalyEpisode[]>(INITIAL_FACT_BUNDLE.open_episodes);
  const [capabilities, setCapabilities] = useState<CapabilityManifest | null>(
    INITIAL_FACT_BUNDLE.capabilities
  );

  const [historyEvents, setHistoryEvents] = useState<CanonicalEvent[]>([]);
  const [replayStatus, setReplayStatus] = useState<ReplayStatusResponse | null>(null);
  const [speedMultiplier, setSpeedMultiplier] = useState<number>(1);
  const [modelCard, setModelCard] = useState<ModelCardData | null>(null);

  // UI States
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isSeeding, setIsSeeding] = useState<boolean>(false);
  const [selectedRecForFeedback, setSelectedRecForFeedback] =
    useState<MaintenanceRecommendation | null>(null);
  const [isModelCardOpen, setIsModelCardOpen] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // 1. Fetch Backend Health, Asset State/FactBundle, History, and Model-Card in parallel
  const loadState = useCallback(async (currentAssetId: string) => {
    setIsRefreshing(true);
    try {
      const [healthRes, stateRes, historyRes, modelCardRes] = await Promise.allSettled([
        api.getHealthz(),
        api.getAssetState(currentAssetId),
        api.getAssetHistory(currentAssetId, { limit: 50 }),
        api.getAssetModelCard(currentAssetId),
      ]);

      // 1. Process Health
      if (healthRes.status === 'fulfilled') {
        setIsBackendHealthy(healthRes.value.is_ready);
      } else {
        setIsBackendHealthy(false);
      }

      // 2. Process Asset State & FactBundle
      if (stateRes.status === 'fulfilled' && stateRes.value) {
        const data = stateRes.value;
        if (
          data.twin_state?.current_observations &&
          Object.keys(data.twin_state.current_observations).length > 0
        ) {
          setTwinState(data.twin_state);
        }
        if (data.fact_bundle) {
          if (data.fact_bundle.health) {
            setHealth(data.fact_bundle.health);
          }
          if (data.fact_bundle.active_recommendations?.length > 0) {
            setRecommendations(data.fact_bundle.active_recommendations);
          }
          if (data.fact_bundle.open_episodes?.length > 0) {
            setEpisodes(data.fact_bundle.open_episodes);
          }
          if (data.fact_bundle.capabilities) {
            setCapabilities(data.fact_bundle.capabilities);
          }
        }
      }

      // 3. Process History Events
      if (historyRes.status === 'fulfilled' && historyRes.value?.events) {
        setHistoryEvents(historyRes.value.events);
      }

      // 4. Process Calibrated Model Card
      if (modelCardRes.status === 'fulfilled' && modelCardRes.value) {
        setModelCard(modelCardRes.value);
      }
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadState(assetId);
  }, [assetId, loadState]);

  // 2. Replay Controller
  const handleReplayAction = async (
    action: 'start' | 'pause' | 'resume' | 'step' | 'reset',
    batchSize: number = 1,
    overrideSpeed?: number
  ) => {
    const activeSpeed = overrideSpeed !== undefined ? overrideSpeed : speedMultiplier;
    try {
      const res = await api.controlReplay({
        action,
        batch_size: batchSize,
        asset_id: assetId,
        speed_multiplier: activeSpeed,
      });
      setReplayStatus(res);
      showToast(`Replay ${action.toUpperCase()} action executed.`);
      await loadState(assetId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Replay action failed';
      showToast(msg);
    }
  };

  const handleSpeedChange = (speed: number) => {
    setSpeedMultiplier(speed);
    handleReplayAction('resume', 1, speed);
  };

  // 3. Seed Telemetry Ingestion
  const handleSeedDemoData = async () => {
    setIsSeeding(true);
    try {
      const res = await api.ingestTelemetry({
        asset_id: assetId,
        events: SEED_TELEMETRY_EVENTS,
      });
      showToast(`Ingested ${res.ingested_count} canonical telemetry frames to reducer!`);
      await loadState(assetId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Telemetry ingestion failed';
      showToast(msg);
    } finally {
      setIsSeeding(false);
    }
  };

  // 4. Seed Trip Fault Fixture
  const handleSeedTripData = async () => {
    setIsSeeding(true);
    try {
      const tripEvent = {
        schema_version: '1.0.0',
        event_id: `evt-trip-${Date.now()}`,
        asset_id: assetId,
        event_time_utc: new Date().toISOString(),
        source: {
          system: 'protection_relay_trip',
          adapter_id: 'trip_adapter',
          source_record_id: 'rec_trip',
          source_uri: 'fixtures/fixture_direct_protection_trip.json',
          raw_sha256: '4444555566667777888899990000111122223333444455556666777788889999',
        },
        measurements: [
          {
            signal_id: 'oil_temp_trip_flag',
            value: true,
            value_type: 'bool' as const,
            unit_ucum: '1',
            original_name: 'OTI_T',
            original_value: '1',
            original_unit: 'flag',
            quality: { severity: 'BAD' as const, flags: ['DIRECT_TRIP'] },
          },
          {
            signal_id: 'top_oil_temperature',
            value: 98.4,
            value_type: 'float' as const,
            unit_ucum: 'Cel',
            original_name: 'OTI',
            original_value: '98.4',
            original_unit: 'degC',
            quality: { severity: 'BAD' as const, flags: ['CRITICAL_LIMIT'] },
          },
          {
            signal_id: 'current_l1',
            value: 0.0,
            value_type: 'float' as const,
            unit_ucum: 'A',
            original_name: 'I_R',
            original_value: '0.0',
            original_unit: 'A',
            quality: { severity: 'GOOD' as const, flags: [] },
          },
        ],
        event_quality_flags: ['PROTECTION_TRIP_ACTIVE'],
        mapping_version: '1.0.0',
      };

      await api.ingestTelemetry({
        asset_id: assetId,
        events: [tripEvent],
      });

      showToast('Discrete Protection Trip Injected: CRITICAL Escalation triggered!');
      await loadState(assetId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Trip injection failed';
      showToast(msg);
    } finally {
      setIsSeeding(false);
    }
  };

  // 5. Feedback handler
  const handleFeedbackSuccess = (recId: string, actionChosen: string) => {
    setRecommendations((prev) =>
      prev.map((r) =>
        r.recommendation_id === recId
          ? {
              ...r,
              acknowledged: actionChosen === 'ACKNOWLEDGE',
              acknowledged_at_utc: new Date().toISOString(),
              acknowledged_by: 'OP-SHIVANSH-01',
            }
          : r
      )
    );
    showToast(`Recommendation ${actionChosen} committed to immutable audit ledger.`);
  };

  const watermarkUtc = twinState?.event_time_watermark_utc || twinState?.state_time_utc;

  return (
    <div className="min-h-screen text-[#0e1824] flex flex-col justify-between selection:bg-[#d0e5f7]">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#0e1824] text-white px-5 py-3 rounded-2xl shadow-2xl text-xs font-semibold flex items-center gap-2 border border-slate-700 animate-slide-up">
          <span className="w-2 h-2 rounded-full bg-sky-400"></span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Editorial Navbar */}
      <Navbar
        isBackendHealthy={isBackendHealthy}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onRefresh={() => loadState(assetId)}
        isRefreshing={isRefreshing}
      />

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-6 w-full flex-grow pt-6">
        {/* Persistent Replay & Asset Control Bar */}
        <ReplayBar
          assetId={assetId}
          onAssetChange={(newId) => setAssetId(newId)}
          replayStatus={replayStatus}
          onReplayAction={handleReplayAction}
          speedMultiplier={speedMultiplier}
          onSpeedChange={handleSpeedChange}
          watermarkUtc={watermarkUtc}
          isBackendHealthy={isBackendHealthy}
          onSeedDemoData={handleSeedDemoData}
          isSeeding={isSeeding}
        />

        {/* View 1: Overview (Compact, Zero Endless Scrolling, with Reserved 3D Model space at the end) */}
        {activeTab === 'overview' && (
          <OverviewView
            assetId={assetId}
            twinState={twinState}
            health={health}
            capabilities={capabilities}
            recommendations={recommendations}
            episodes={episodes}
            onNavigateTab={setActiveTab}
            onOpenFeedback={(rec) => setSelectedRecForFeedback(rec)}
          />
        )}

        {/* View 2: Twin Analysis (Residuals & 2-Hour What-If Simulator) */}
        {activeTab === 'twin-analysis' && (
          <TwinAnalysisView
            assetId={assetId}
            twinState={twinState}
            health={health}
            onOpenModelCard={() => setIsModelCardOpen(true)}
          />
        )}

        {/* View 3: Anomaly Timeline (6-State FSM Episodes & CUSUM Tracker) */}
        {activeTab === 'anomalies' && (
          <AnomalyTimelineView
            episodes={episodes}
            twinState={twinState}
            onSeedTripData={handleSeedTripData}
            isSeeding={isSeeding}
          />
        )}

        {/* View 4: Maintenance Advisories (Prioritized Rules & Operator Feedback) */}
        {activeTab === 'maintenance' && (
          <MaintenanceView
            recommendations={recommendations}
            onOpenFeedback={(rec) => setSelectedRecForFeedback(rec)}
          />
        )}

        {/* View 5: Telemetry & Capabilities (3-Phase Metrics, C0-C4 Tier Manifest & DuckDB Storage Log) */}
        {activeTab === 'telemetry' && (
          <TelemetryView
            assetId={assetId}
            twinState={twinState}
            capabilities={capabilities}
            historyEvents={historyEvents}
          />
        )}

        {/* View 6: Data & Model Card (Transparency, Calibration Metrics, Qualification) */}
        {activeTab === 'model-card' && (
          <DataModelCardView modelCard={modelCard} />
        )}

        {/* View 7: 3D Twin Workspace (Dedicated Space for Three.js Transformer Model) */}
        {activeTab === 'twin-3d' && (
          <Transformer3DView twinState={twinState} />
        )}
      </main>

      {/* Operator Feedback Modal */}
      <FeedbackModal
        isOpen={Boolean(selectedRecForFeedback)}
        recommendation={selectedRecForFeedback}
        assetId={assetId}
        onClose={() => setSelectedRecForFeedback(null)}
        onSuccess={handleFeedbackSuccess}
      />

      {/* Calibrated Model Card Modal */}
      <ModelCardModal
        isOpen={isModelCardOpen}
        onClose={() => setIsModelCardOpen(false)}
        modelCard={modelCard}
      />

      {/* Minimal Footer */}
      <footer className="mt-16 border-t border-[#d8e6f2] bg-white/60 py-6 text-xs text-[#5d768f]">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-extrabold text-[#0e1824] font-sans">
              Grid<span className="text-[#0284c7]">Pulse</span>
            </span>
            <span>· POWERNext-AI Hackathon 2026 (Track 2: Digital Twin Health Monitoring)</span>
          </div>
          <div className="flex items-center gap-4 text-[11px] font-mono">
            <span>Phase 8 React Dashboard</span>
            <span>·</span>
            <span>Gated OTHI</span>
            <span>·</span>
            <span>90% Conformal Bounds</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
