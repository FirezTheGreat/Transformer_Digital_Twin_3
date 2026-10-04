/**
 * Canonical Digital Twin Data Contracts and Type Definitions.
 * Synchronized strictly with backend Pydantic models in backend/app/models/.
 */

// ==========================================
// 1. Telemetry & Ingestion Contracts
// ==========================================

export type QualitySeverity = 'GOOD' | 'UNCERTAIN' | 'BAD';

export interface SourceRef {
  system: string;
  adapter_id: string;
  source_record_id: string;
  source_uri: string;
  raw_sha256: string;
}

export interface MeasurementQuality {
  severity: QualitySeverity;
  flags: string[];
  source_code?: string | null;
}

export type ElectricalPhase = 'L1' | 'L2' | 'L3' | 'N' | 'L1_L2' | 'L2_L3' | 'L3_L1';
export type MeasurementValueType = 'float' | 'int' | 'str' | 'bool';

export interface Measurement {
  signal_id: string;
  phase?: ElectricalPhase | null;
  value: number | string | boolean;
  value_type: MeasurementValueType;
  unit_ucum: string;
  original_name: string;
  original_value: string;
  original_unit: string;
  quality: MeasurementQuality;
}

export interface CanonicalEvent {
  schema_version: string;
  event_id: string;
  asset_id: string;
  event_time_utc: string; // ISO 8601 UTC
  received_time_utc?: string | null; // ISO 8601 UTC or null for historical telemetry without native receive time
  source: SourceRef;
  measurements: Measurement[];
  event_quality_flags: string[];
  mapping_version: string;
}

export interface RawTelemetryFrame {
  raw_id: string;
  source_system: string;
  received_time_utc: string;
  raw_payload: Record<string, unknown>;
  raw_sha256: string;
}

// ==========================================
// 2. Asset Profile Contracts
// ==========================================

export type InsulationClass = 'NON_THERMALLY_UPGRADED' | 'THERMALLY_UPGRADED' | 'UNKNOWN';
export type ProfileVerificationStatus = 'VERIFIED' | 'UNVERIFIED' | 'UNKNOWN';
export type PhaseTopology = 'THREE_PHASE_4W' | 'THREE_PHASE_3W' | 'SINGLE_PHASE';

export interface ProfileField {
  value: unknown;
  unit?: string | null;
  source_document: string;
  verified_by?: string | null;
  verified_at_utc?: string | null;
  status: ProfileVerificationStatus;
}

export interface AssetProfile {
  asset_id: string;
  phase_topology: PhaseTopology;
  nominal_frequency_hz: number;
  rated_kva?: number | null;
  rated_voltage_hv_v?: number | null;
  rated_voltage_lv_v?: number | null;
  cooling_class: string;
  insulation_paper_class: InsulationClass;
  expected_cadence_s: number;
  profile_status: ProfileVerificationStatus;
  fields: Record<string, ProfileField>;
  profile_version: string;
}

// ==========================================
// 3. Capability Manifest Contracts
// ==========================================

export type CapabilityTier = 'C0' | 'C1' | 'C2' | 'C3' | 'C4';
export type EvidenceGrade = 'A' | 'B' | 'C' | 'U';

export interface CapabilityItem {
  enabled: boolean;
  evidence_grade: EvidenceGrade;
  required_inputs: string[];
  missing_inputs: string[];
  disabled_reason_codes: string[];
  coverage_pct: number;
  model_status: string;
  extrapolation: boolean;
}

export interface CapabilityManifest {
  asset_id: string;
  evaluated_at_utc: string;
  evaluation_window_s: number;
  highest_tier: CapabilityTier;
  available_signal_ids: string[];
  verified_metadata_ids: string[];
  expected_cadence_s: number;
  current_freshness_s: number;
  capabilities: Record<string, CapabilityItem>;
  schema_version: string;
  profile_version: string;
  model_version: string;
}

// ==========================================
// 4. Derived Features Contracts
// ==========================================

export interface DerivedFeatures {
  timestamp_utc: string;
  apparent_power_derived_kva?: number | null;
  power_factor_derived?: number | null;
  current_mean_a?: number | null;
  current_magnitude_imbalance_pct?: number | null;
  voltage_magnitude_imbalance_pct?: number | null;
  neutral_current_ratio?: number | null;
  pqs_inconsistency?: number | null;
  relative_load_index?: number | null;
  thermal_residual_degc?: number | null;
  transform_version: string;
}

// ==========================================
// 5. Anomaly & Episode Contracts
// ==========================================

export type AnomalyCategory =
  | 'DATA_QUALITY'
  | 'SENSOR_PLAUSIBILITY'
  | 'THERMAL_DEVIATION'
  | 'THERMAL_LIMIT'
  | 'LOADING'
  | 'PHASE_OR_NEUTRAL'
  | 'VOLTAGE_PF_FREQUENCY'
  | 'PROTECTION_OR_OIL_STATUS';

export type EpisodeState =
  | 'NORMAL'
  | 'WATCH'
  | 'WARNING'
  | 'CRITICAL'
  | 'RECOVERING'
  | 'CLOSED';

export interface EvidenceItem {
  evidence_id: string;
  asset_id: string;
  event_time_utc: string;
  category: AnomalyCategory;
  detector_id: string;
  observed_value: unknown;
  expected_value?: unknown | null;
  unit?: string | null;
  threshold_or_band?: string | null;
  direction?: string | null;
  severity: number; // [0.0, 1.0]
  confidence: number; // [0.0, 1.0]
  input_lineage: string[];
  reason_codes: string[];
  hypothesis_codes: string[];
}

export interface AnomalyEpisode {
  episode_id: string;
  asset_id: string;
  state: EpisodeState;
  category: AnomalyCategory;
  severity_score: number; // [0.0, 1.0]
  start_time_utc: string;
  last_seen_time_utc: string;
  recovery_start_time_utc?: string | null;
  closed_time_utc?: string | null;
  evidence_ids: string[];
  is_monitoring_gap: boolean;
  primary_reason: string;
  hypothesis_codes: string[];
}

// ==========================================
// 6. Domain Health & OTHI Contracts
// ==========================================

export type CanonicalDomain =
  | 'thermal'
  | 'loading'
  | 'phase_neutral'
  | 'voltage_pf_freq'
  | 'oil_protection';

export type HealthStatus = 'NORMAL' | 'WATCH' | 'WARNING' | 'CRITICAL';

export interface DomainHealth {
  domain_name: CanonicalDomain;
  severity: number; // [0.0, 1.0]
  status: HealthStatus;
  driving_evidence_id?: string | null;
  evidence_count: number;
  details: string;
}

export interface OTHIBundle {
  asset_id: string;
  timestamp_utc: string;
  othi_score?: number | null; // [0, 100] or null if gated
  status?: HealthStatus | null;
  evidence_grade: EvidenceGrade;
  driving_domain?: string | null;
  base_penalty: number;
  secondary_penalty: number;
  total_penalty: number;
  is_gated: boolean;
  gate_reason?: string | null;
  available_domains: string[];
  domains: Record<string, DomainHealth>;
}

// ==========================================
// 7. Maintenance & Feedback Contracts
// ==========================================

export type MaintenancePriority = 'P0' | 'P1' | 'P2' | 'P3' | 'P4';
export type ActionWindow =
  | 'IMMEDIATE'
  | 'WITHIN_24H'
  | 'NEXT_AUTHORIZED_MAINTENANCE_WINDOW'
  | 'MONITOR'
  | 'MODEL_REVIEW';

export interface MaintenanceRecommendation {
  recommendation_id: string;
  rule_id: string;
  rule_version: string;
  title: string;
  priority: MaintenancePriority;
  priority_label: string;
  action_window: ActionWindow;
  advisory_wording: string;
  rationale: string;
  evidence_ids: string[];
  source_reference: string;
  merge_key: string;
  created_at_utc: string;
  acknowledged: boolean;
  acknowledged_at_utc?: string | null;
  acknowledged_by?: string | null;
}

export type FeedbackAction = 'ACKNOWLEDGE' | 'DISMISS' | 'INSPECTION_RECORDED' | 'OVERRIDE';

export interface OperatorFeedbackEvent {
  feedback_id: string;
  asset_id: string;
  timestamp_utc: string;
  recommendation_id?: string | null;
  action: FeedbackAction;
  operator_id: string;
  notes?: string | null;
  inspection_outcome?: Record<string, unknown> | null;
}

// ==========================================
// 8. Twin State & FactBundle Contracts
// ==========================================

export interface ThermalLatentState {
  top_oil_expected_degc?: number | null;
  last_free_running_top_oil_degc?: number | null;
  time_constant_tau_hours: number;
  warmup_samples_remaining: number;
  model_status: string;
  conformal_interval_lower_degc?: number | null;
  conformal_interval_upper_degc?: number | null;
}

export interface DetectorState {
  cusum_pos: number;
  cusum_neg: number;
  cusum_alarm_active: boolean;
  persistence_timers: Record<string, number>;
  cooldown_timers: Record<string, number>;
}

export interface ExposureState {
  time_above_bands_s: Record<string, number>;
  equivalent_ageing_hours?: number | null;
  is_ageing_enabled: boolean;
}

export interface TwinState {
  asset_id: string;
  state_time_utc: string;
  last_processed_event_id: string;
  event_time_watermark_utc: string;
  state_sequence: number;
  current_observations: Record<string, Measurement>;
  derived_electrical?: DerivedFeatures | null;
  thermal_latent: ThermalLatentState;
  detector_state: DetectorState;
  open_episodes: AnomalyEpisode[];
  health_bundle?: OTHIBundle | null;
  exposure_state: ExposureState;
  active_recommendations: MaintenanceRecommendation[];
  versions: Record<string, string>;
  state_hash: string;
}

export interface FactBundle {
  fact_bundle_id: string;
  asset_id: string;
  timestamp_utc: string;
  twin_state: TwinState;
  capabilities: CapabilityManifest;
  health: OTHIBundle;
  open_episodes: AnomalyEpisode[];
  active_recommendations: MaintenanceRecommendation[];
  provenance_hash: string;
  bundle_version: string;
}
