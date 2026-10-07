import {
  FactBundle,
  CanonicalEvent,
} from '../types/contracts';


export const INITIAL_FACT_BUNDLE: FactBundle = {
  fact_bundle_id: "fb-20261004-001",
  asset_id: "tripura_dt_01",
  timestamp_utc: "2026-10-04T12:00:00Z",
  bundle_version: "1.0.0",
  provenance_hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  twin_state: {
    asset_id: "tripura_dt_01",
    state_time_utc: "2026-10-04T12:00:00Z",
    last_processed_event_id: "evt-20261004-048",
    event_time_watermark_utc: "2026-10-04T11:50:00Z",
    state_sequence: 48,
    state_hash: "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
    current_observations: {
      top_oil_temperature: {
        signal_id: "top_oil_temperature",
        phase: null,
        value: 74.8,
        value_type: "float",
        unit_ucum: "Cel",
        original_name: "OTI",
        original_value: "74.8",
        original_unit: "degC",
        quality: { severity: "GOOD", flags: [] }
      },
      ambient_temperature: {
        signal_id: "ambient_temperature",
        phase: null,
        value: 34.2,
        value_type: "float",
        unit_ucum: "Cel",
        original_name: "ATI",
        original_value: "34.2",
        original_unit: "degC",
        quality: { severity: "GOOD", flags: [] }
      },
      voltage_l1_n: {
        signal_id: "voltage_l1_n",
        phase: "L1",
        value: 231.5,
        value_type: "float",
        unit_ucum: "V",
        original_name: "V_R",
        original_value: "231.5",
        original_unit: "V",
        quality: { severity: "GOOD", flags: [] }
      },
      voltage_l2_n: {
        signal_id: "voltage_l2_n",
        phase: "L2",
        value: 229.8,
        value_type: "float",
        unit_ucum: "V",
        original_name: "V_Y",
        original_value: "229.8",
        original_unit: "V",
        quality: { severity: "GOOD", flags: [] }
      },
      voltage_l3_n: {
        signal_id: "voltage_l3_n",
        phase: "L3",
        value: 230.2,
        value_type: "float",
        unit_ucum: "V",
        original_name: "V_B",
        original_value: "230.2",
        original_unit: "V",
        quality: { severity: "GOOD", flags: [] }
      },
      current_l1: {
        signal_id: "current_l1",
        phase: "L1",
        value: 115.4,
        value_type: "float",
        unit_ucum: "A",
        original_name: "I_R",
        original_value: "115.4",
        original_unit: "A",
        quality: { severity: "GOOD", flags: [] }
      },
      current_l2: {
        signal_id: "current_l2",
        phase: "L2",
        value: 112.1,
        value_type: "float",
        unit_ucum: "A",
        original_name: "I_Y",
        original_value: "112.1",
        original_unit: "A",
        quality: { severity: "GOOD", flags: [] }
      },
      current_l3: {
        signal_id: "current_l3",
        phase: "L3",
        value: 110.8,
        value_type: "float",
        unit_ucum: "A",
        original_name: "I_B",
        original_value: "110.8",
        original_unit: "A",
        quality: { severity: "GOOD", flags: [] }
      },
      neutral_current: {
        signal_id: "neutral_current",
        phase: "N",
        value: 4.6,
        value_type: "float",
        unit_ucum: "A",
        original_name: "I_N",
        original_value: "4.6",
        original_unit: "A",
        quality: { severity: "GOOD", flags: [] }
      },
      active_power_total: {
        signal_id: "active_power_total",
        phase: null,
        value: 74.2,
        value_type: "float",
        unit_ucum: "kW",
        original_name: "P_TOT",
        original_value: "74.2",
        original_unit: "kW",
        quality: { severity: "GOOD", flags: [] }
      },
      reactive_power_total: {
        signal_id: "reactive_power_total",
        phase: null,
        value: 24.1,
        value_type: "float",
        unit_ucum: "kvar",
        original_name: "Q_TOT",
        original_value: "24.1",
        original_unit: "kvar",
        quality: { severity: "GOOD", flags: [] }
      },
      frequency: {
        signal_id: "frequency",
        phase: null,
        value: 50.02,
        value_type: "float",
        unit_ucum: "Hz",
        original_name: "FREQ",
        original_value: "50.02",
        original_unit: "Hz",
        quality: { severity: "GOOD", flags: [] }
      }
    },
    derived_electrical: {
      timestamp_utc: "2026-10-04T12:00:00Z",
      apparent_power_derived_kva: 78.01,
      power_factor_derived: 0.951,
      current_mean_a: 112.77,
      current_magnitude_imbalance_pct: 2.33,
      voltage_magnitude_imbalance_pct: 0.43,
      neutral_current_ratio: 0.041,
      pqs_inconsistency: 0.002,
      relative_load_index: 0.78,
      thermal_residual_degc: 4.3,
      transform_version: "1.0.0"
    },
    thermal_latent: {
      top_oil_expected_degc: 70.5,
      last_free_running_top_oil_degc: 70.5,
      time_constant_tau_hours: 0.5,
      warmup_samples_remaining: 0,
      model_status: "SHADOW_DESCRIPTIVE",
      conformal_interval_lower_degc: 68.1,
      conformal_interval_upper_degc: 72.9
    },
    detector_state: {
      cusum_pos: 3.82,
      cusum_neg: 0.0,
      cusum_alarm_active: true,
      persistence_timers: { cusum_thermal_shift: 3600.0 },
      cooldown_timers: {}
    },
    open_episodes: [
      {
        episode_id: "ep-20261004-001",
        asset_id: "tripura_dt_01",
        state: "WARNING",
        category: "THERMAL_DEVIATION",
        severity_score: 0.55,
        start_time_utc: "2026-10-04T11:00:00Z",
        last_seen_time_utc: "2026-10-04T12:00:00Z",
        recovery_start_time_utc: null,
        closed_time_utc: null,
        evidence_ids: ["ev-20261004-001"],
        is_monitoring_gap: false,
        primary_reason: "Persistent positive top-oil temperature residual (+4.3°C over expected grey-box state)",
        hypothesis_codes: ["POSSIBLE_COOLING_DEGRADATION"]
      }
    ],
    health_bundle: {
      asset_id: "tripura_dt_01",
      timestamp_utc: "2026-10-04T12:00:00Z",
      othi_score: 67,
      status: "WATCH",
      evidence_grade: "A",
      driving_domain: "thermal",
      base_penalty: 0.55,
      secondary_penalty: 0.0,
      total_penalty: 0.55,
      is_gated: false,
      gate_reason: null,
      available_domains: ["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"],
      domains: {
        thermal: {
          domain_name: "thermal",
          severity: 0.55,
          status: "WARNING",
          driving_evidence_id: "ev-20261004-001",
          evidence_count: 1,
          details: "Positive thermal CUSUM shift active (observed 74.8°C vs expected 70.5°C)"
        },
        loading: {
          domain_name: "loading",
          severity: 0.0,
          status: "NORMAL",
          driving_evidence_id: null,
          evidence_count: 0,
          details: "Loading at 78.0 kVA (0.78 p.u.), within normal nameplate limits"
        },
        phase_neutral: {
          domain_name: "phase_neutral",
          severity: 0.0,
          status: "NORMAL",
          driving_evidence_id: null,
          evidence_count: 0,
          details: "Phase current unbalance at 2.33%, neutral ratio 4.1%"
        },
        voltage_pf_freq: {
          domain_name: "voltage_pf_freq",
          severity: 0.0,
          status: "NORMAL",
          driving_evidence_id: null,
          evidence_count: 0,
          details: "Voltages balanced (231.5V / 229.8V / 230.2V), PF 0.951, Frequency 50.02 Hz"
        },
        oil_protection: {
          domain_name: "oil_protection",
          severity: 0.0,
          status: "NORMAL",
          driving_evidence_id: null,
          evidence_count: 0,
          details: "Direct protection bits normal, no trip or low oil indications"
        }
      }
    },
    exposure_state: {
      time_above_bands_s: { above_70c: 3600.0, above_80c: 0.0 },
      equivalent_ageing_hours: null,
      is_ageing_enabled: false
    },
    active_recommendations: [
      {
        recommendation_id: "rec-20261004-001",
        rule_id: "MNT-THERM-002",
        rule_version: "1.0.0",
        title: "Cooling Operation Inspection",
        priority: "P1",
        priority_label: "P1 URGENT_INSPECTION",
        action_window: "WITHIN_24H",
        advisory_wording: "Arrange prompt inspection of cooling operation and temperature sensing. Review loading under the approved operating procedure.",
        rationale: "Positive thermal CUSUM warning active with sustained residual over expected top-oil model.",
        evidence_ids: ["ev-20261004-001"],
        source_reference: "IEEE C57.91-2011 §7 / IEC 60076-7 §6",
        merge_key: "THERM_COOLING_INSPECT",
        created_at_utc: "2026-10-04T11:30:00Z",
        acknowledged: false,
        acknowledged_at_utc: null,
        acknowledged_by: null
      },
      {
        recommendation_id: "rec-20261004-002",
        rule_id: "MNT-LOAD-001",
        rule_version: "1.0.0",
        title: "Phase Load Balance Calibration",
        priority: "P3",
        priority_label: "P3 ROUTINE_MONITOR",
        action_window: "NEXT_AUTHORIZED_MAINTENANCE_WINDOW",
        advisory_wording: "Phase loading balanced within 2.33% tolerance. Verify neutral earthing impedance during upcoming scheduled maintenance.",
        rationale: "Continuous three-phase current monitoring validates compliant load distribution.",
        evidence_ids: [],
        source_reference: "CBIP Manual on Transformers Pub 317",
        merge_key: "PHASE_LOAD_BALANCE_CHECK",
        created_at_utc: "2026-10-04T10:00:00Z",
        acknowledged: false,
        acknowledged_at_utc: null,
        acknowledged_by: null
      }
    ],
    versions: {
      schema_version: "1.0.0",
      profile_version: "1.0.0",
      model_version: "tripura_fit_20261003",
      rules_version: "1.0.0"
    }
  },
  capabilities: {
    asset_id: "tripura_dt_01",
    evaluated_at_utc: "2026-10-04T12:00:00Z",
    evaluation_window_s: 86400,
    highest_tier: "C2",
    available_signal_ids: [
      "top_oil_temperature",
      "ambient_temperature",
      "voltage_l1_n",
      "voltage_l2_n",
      "voltage_l3_n",
      "current_l1",
      "current_l2",
      "current_l3",
      "neutral_current",
      "active_power_total",
      "reactive_power_total",
      "frequency"
    ],
    verified_metadata_ids: ["cooling_class"],
    expected_cadence_s: 900,
    current_freshness_s: 12.0,
    capabilities: {
      C0: {
        enabled: true,
        evidence_grade: "A",
        required_inputs: ["event_time_utc", "asset_id"],
        missing_inputs: [],
        disabled_reason_codes: [],
        coverage_pct: 100.0,
        model_status: "NOT_APPLICABLE",
        extrapolation: false
      },
      C1: {
        enabled: true,
        evidence_grade: "A",
        required_inputs: ["usable_electrical_power_or_current"],
        missing_inputs: [],
        disabled_reason_codes: [],
        coverage_pct: 100.0,
        model_status: "NOT_APPLICABLE",
        extrapolation: false
      },
      C2: {
        enabled: true,
        evidence_grade: "A",
        required_inputs: ["top_oil_temperature"],
        missing_inputs: [],
        disabled_reason_codes: [],
        coverage_pct: 100.0,
        model_status: "NOT_APPLICABLE",
        extrapolation: false
      },
      C3: {
        enabled: false,
        evidence_grade: "U",
        required_inputs: ["top_oil_temperature", "ambient_temperature", "load_driver", "promoted_thermal_model"],
        missing_inputs: ["promoted_thermal_model"],
        disabled_reason_codes: ["MODEL_NOT_PROMOTED"],
        coverage_pct: 0.0,
        model_status: "SHADOW_DESCRIPTIVE",
        extrapolation: false
      },
      C4: {
        enabled: false,
        evidence_grade: "U",
        required_inputs: ["C3_thermal_predictive", "verified_insulation_class", "hotspot_estimate"],
        missing_inputs: ["hotspot_estimate"],
        disabled_reason_codes: ["HOTSPOT_ESTIMATE_UNSUPPORTED"],
        coverage_pct: 0.0,
        model_status: "UNCALIBRATED",
        extrapolation: false
      }
    },
    schema_version: "1.0.0",
    profile_version: "1.0.0",
    model_version: "tripura_fit_20261003"
  },
  health: {
    asset_id: "tripura_dt_01",
    timestamp_utc: "2026-10-04T12:00:00Z",
    othi_score: 67,
    status: "WATCH",
    evidence_grade: "A",
    driving_domain: "thermal",
    base_penalty: 0.55,
    secondary_penalty: 0.0,
    total_penalty: 0.55,
    is_gated: false,
    gate_reason: null,
    available_domains: ["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"],
    domains: {
      thermal: {
        domain_name: "thermal",
        severity: 0.55,
        status: "WARNING",
        driving_evidence_id: "ev-20261004-001",
        evidence_count: 1,
        details: "Positive thermal CUSUM shift active (observed 74.8°C vs expected 70.5°C)"
      },
      loading: {
        domain_name: "loading",
        severity: 0.0,
        status: "NORMAL",
        driving_evidence_id: null,
        evidence_count: 0,
        details: "Loading at 78.0 kVA (0.78 p.u.), within normal nameplate limits"
      },
      phase_neutral: {
        domain_name: "phase_neutral",
        severity: 0.0,
        status: "NORMAL",
        driving_evidence_id: null,
        evidence_count: 0,
        details: "Phase current unbalance at 2.33%, neutral ratio 4.1%"
      },
      voltage_pf_freq: {
        domain_name: "voltage_pf_freq",
        severity: 0.0,
        status: "NORMAL",
        driving_evidence_id: null,
        evidence_count: 0,
        details: "Voltages balanced, PF 0.951, Frequency 50.02 Hz"
      },
      oil_protection: {
        domain_name: "oil_protection",
        severity: 0.0,
        status: "NORMAL",
        driving_evidence_id: null,
        evidence_count: 0,
        details: "Direct protection bits normal, no trip indications"
      }
    }
  },
  open_episodes: [
    {
      episode_id: "ep-20261004-001",
      asset_id: "tripura_dt_01",
      state: "WARNING",
      category: "THERMAL_DEVIATION",
      severity_score: 0.55,
      start_time_utc: "2026-10-04T11:00:00Z",
      last_seen_time_utc: "2026-10-04T12:00:00Z",
      recovery_start_time_utc: null,
      closed_time_utc: null,
      evidence_ids: ["ev-20261004-001"],
      is_monitoring_gap: false,
      primary_reason: "Persistent positive top-oil temperature residual (+4.3°C over expected grey-box state)",
      hypothesis_codes: ["POSSIBLE_COOLING_DEGRADATION"]
    }
  ],
  active_recommendations: [
    {
      recommendation_id: "rec-20261004-001",
      rule_id: "MNT-THERM-002",
      rule_version: "1.0.0",
      title: "Cooling Operation Inspection",
      priority: "P1",
      priority_label: "P1 URGENT_INSPECTION",
      action_window: "WITHIN_24H",
      advisory_wording: "Arrange prompt inspection of cooling operation and temperature sensing. Review loading under the approved operating procedure.",
      rationale: "Positive thermal CUSUM warning active with sustained residual over expected top-oil model.",
      evidence_ids: ["ev-20261004-001"],
      source_reference: "IEEE C57.91-2011 §7 / IEC 60076-7 §6",
      merge_key: "THERM_COOLING_INSPECT",
      created_at_utc: "2026-10-04T11:30:00Z",
      acknowledged: false,
      acknowledged_at_utc: null,
      acknowledged_by: null
    }
  ]
};

// Batch of sample CanonicalEvents to seed backend storage
export const SEED_TELEMETRY_EVENTS: CanonicalEvent[] = [
  {
    schema_version: "1.0.0",
    event_id: "evt-seed-001",
    asset_id: "tripura_dt_01",
    event_time_utc: "2026-10-04T11:30:00Z",
    received_time_utc: "2026-10-04T11:30:02Z",
    source: {
      system: "tripura_scada_gateway",
      adapter_id: "tripura_csv_adapter",
      source_record_id: "rec_001",
      source_uri: "tripura/raw/feed_01.csv",
      raw_sha256: "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    },
    measurements: [
      {
        signal_id: "voltage_l1_n",
        phase: "L1",
        value: 231.2,
        value_type: "float",
        unit_ucum: "V",
        original_name: "V_R",
        original_value: "231.2",
        original_unit: "V",
        quality: { severity: "GOOD", flags: [] }
      },
      {
        signal_id: "current_l1",
        phase: "L1",
        value: 114.2,
        value_type: "float",
        unit_ucum: "A",
        original_name: "I_R",
        original_value: "114.2",
        original_unit: "A",
        quality: { severity: "GOOD", flags: [] }
      },
      {
        signal_id: "top_oil_temperature",
        phase: null,
        value: 73.5,
        value_type: "float",
        unit_ucum: "Cel",
        original_name: "OTI",
        original_value: "73.5",
        original_unit: "degC",
        quality: { severity: "GOOD", flags: [] }
      },
      {
        signal_id: "ambient_temperature",
        phase: null,
        value: 33.8,
        value_type: "float",
        unit_ucum: "Cel",
        original_name: "ATI",
        original_value: "33.8",
        original_unit: "degC",
        quality: { severity: "GOOD", flags: [] }
      }
    ],
    event_quality_flags: [],
    mapping_version: "1.0.0"
  },
  {
    schema_version: "1.0.0",
    event_id: "evt-seed-002",
    asset_id: "tripura_dt_01",
    event_time_utc: "2026-10-04T11:45:00Z",
    received_time_utc: "2026-10-04T11:45:02Z",
    source: {
      system: "tripura_scada_gateway",
      adapter_id: "tripura_csv_adapter",
      source_record_id: "rec_002",
      source_uri: "tripura/raw/feed_01.csv",
      raw_sha256: "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    },
    measurements: [
      {
        signal_id: "voltage_l1_n",
        phase: "L1",
        value: 231.5,
        value_type: "float",
        unit_ucum: "V",
        original_name: "V_R",
        original_value: "231.5",
        original_unit: "V",
        quality: { severity: "GOOD", flags: [] }
      },
      {
        signal_id: "current_l1",
        phase: "L1",
        value: 115.4,
        value_type: "float",
        unit_ucum: "A",
        original_name: "I_R",
        original_value: "115.4",
        original_unit: "A",
        quality: { severity: "GOOD", flags: [] }
      },
      {
        signal_id: "top_oil_temperature",
        phase: null,
        value: 74.8,
        value_type: "float",
        unit_ucum: "Cel",
        original_name: "OTI",
        original_value: "74.8",
        original_unit: "degC",
        quality: { severity: "GOOD", flags: [] }
      },
      {
        signal_id: "ambient_temperature",
        phase: null,
        value: 34.2,
        value_type: "float",
        unit_ucum: "Cel",
        original_name: "ATI",
        original_value: "34.2",
        original_unit: "degC",
        quality: { severity: "GOOD", flags: [] }
      }
    ],
    event_quality_flags: [],
    mapping_version: "1.0.0"
  }
];
