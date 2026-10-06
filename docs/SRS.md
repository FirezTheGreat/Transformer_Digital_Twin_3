# Software Requirements Specification (SRS)

## POWERNext-AI Hackathon 2026 --- Track 2

### Digital Twin for Intelligent Health Monitoring and Predictive Maintenance of Distribution Transformers

**Document status:** Approved requirements baseline\
**Version:** 1.0\
**Date:** 2026-10-03\
**Team:** SKY HIGH\
**Institutional partner:** Manipal Institute of Technology, Bengaluru

------------------------------------------------------------------------

## 1. Purpose

This Software Requirements Specification defines **what the proposed
software system must provide** for the POWERNext-AI Hackathon 2026 Track
2 problem.

This document is intentionally implementation-agnostic. It defines
required capabilities, observable behavior, inputs, outputs,
constraints, quality expectations, and acceptance requirements. Specific
implementation choices such as programming languages, frameworks,
database technologies, model-fitting procedures, UI libraries, and
deployment structure belong to the implementation/MVP documentation and
are not prescribed here unless required by the frozen architecture.

The SRS is derived from:

1.  The official POWERNext-AI Hackathon 2026 Track 2 problem statement.
2.  `FINAL_ARCHITECTURE_DECISIONS.md`, which is the team's frozen
    technical architecture.
3.  The known development/reference data and declared project
    constraints.

Where the official problem statement lists an analytical capability but
the frozen architecture deliberately limits the claim, the SRS records
the **defensible product requirement and its boundary** rather than
silently promising unsupported functionality.

------------------------------------------------------------------------

# 2. Product Overview

## 2.1 Product purpose

The system shall provide a digital representation of a distribution
transformer that uses operational telemetry and asset information to:

-   monitor important electrical and thermal operating parameters;
-   maintain a current representation of transformer operating state;
-   identify abnormal operating conditions;
-   estimate an operational Transformer Health Index;
-   project expected thermal behavior over a bounded short horizon when
    sufficient evidence exists;
-   provide condition-based and predictive maintenance decision support;
-   present condition, trends, alerts, evidence, and recommendations
    through an interactive dashboard;
-   preserve sufficient provenance and audit information to reproduce
    and explain outputs.

The system is intended as a **Digital Twin prototype for condition
monitoring and predictive-maintenance decision support**, not as an
autonomous protection, control, or failure-prediction system.

## 2.2 Problem context

Distribution transformers operate under changing loading, temperature,
voltage, and environmental conditions. Fixed maintenance schedules may
not reflect actual operating condition.

The official problem statement asks for a Digital Twin prototype capable
of simulating transformer behavior using operational data, monitoring
electrical and thermal parameters, estimating transformer health,
detecting abnormal conditions, providing predictive maintenance
recommendations, and presenting results through an interactive
dashboard.

The system shall therefore connect operational observations to condition
assessment and maintenance-oriented decisions in a traceable manner.

## 2.3 Intended users

The prototype is intended for:

-   **Utility/asset operators:** monitor current condition, trends,
    alerts, and recommendations.
-   **Maintenance/engineering personnel:** investigate abnormal episodes
    and supporting evidence.
-   **Technical reviewers/judges:** inspect the Digital Twin behavior,
    methodology, validation, and provenance.
-   **Project developers:** replay datasets, validate outputs, and
    reproduce results.

The system is decision-support software. It shall not represent itself
as replacing qualified personnel or protection systems.

------------------------------------------------------------------------

# 3. Scope

## 3.1 In scope

The system shall cover:

1.  Transformer telemetry ingestion.
2.  Asset information and configuration.
3.  Data validation and quality assessment.
4.  Canonical representation of measurements.
5.  Chronological replay of historical/simulated telemetry.
6.  Stateful representation of transformer operating condition.
7.  Electrical operating-condition derivation.
8.  Thermal condition representation.
9.  Expected thermal behavior estimation where sufficient data supports
    it.
10. Short-horizon conditional thermal projection.
11. Abnormal-condition detection.
12. Persistent anomaly/episode management.
13. Operational Transformer Health Index (OTHI).
14. Thermal exposure assessment.
15. Condition-based maintenance recommendations.
16. Interactive visualization.
17. Reporting/export.
18. Provenance, versioning, reproducibility, and auditability.
19. Operator acknowledgement and inspection-outcome feedback.
20. Graceful degradation when required telemetry or model evidence is
    unavailable.

## 3.2 Explicitly bounded or excluded

The following shall **not** be represented as guaranteed system
capabilities:

-   Numeric Remaining Useful Life (RUL).
-   Transformer failure probability.
-   General transformer failure prediction.
-   Complete prediction of every transformer fault mode.
-   Insulation health or whole-life asset-health assessment.
-   Automatic protection or control actions.
-   Closed-loop physical control of the transformer.
-   Standards-compliance certification.
-   Electromagnetic-field, CFD, or full physical simulation.
-   A 3D visualization presented as a physical simulation.
-   Unsupported causal root-cause claims.
-   Unvalidated AI/ML outputs presented as engineering truth.

The official problem statement lists fault prediction and RUL among
possible analytics-layer functions. This project deliberately bounds
those functions because the available evidence does not establish the
data, labels, degradation history, or physical observability required
for defensible numerical failure/RUL outputs.

------------------------------------------------------------------------

# 4. Product Goals

The system shall aim to achieve the following product goals:

### G1 --- Observability

Provide a coherent view of transformer electrical, thermal, condition,
and data-quality state.

### G2 --- Early abnormal-condition identification

Identify meaningful deviations and persistent abnormal operating
conditions while minimizing alert noise and avoiding unsupported
diagnoses.

### G3 --- Explainable condition assessment

Produce a health/condition assessment whose contributing domains and
evidence can be inspected.

### G4 --- Bounded prediction

Where supported by telemetry and validation, estimate expected top-oil
behavior and provide a bounded short-horizon projection under explicit
operating assumptions.

### G5 --- Maintenance decision support

Translate sufficiently supported conditions into prioritized, auditable
maintenance recommendations.

### G6 --- Reproducibility

Ensure that important outputs can be traced to source observations,
transformations, configuration, model versions, rules, and timestamps.

### G7 --- Graceful degradation

The system shall remain useful when individual measurements, models, or
optional capabilities are unavailable.

------------------------------------------------------------------------

# 5. Functional Requirements

## 5.1 Data Input and Ingestion

### FR-DATA-001 --- Telemetry ingestion

The system shall accept operational transformer measurements from
supported input sources such as CSV/historical datasets and a canonical
REST interface.

### FR-DATA-002 --- Extensible source support

The data layer shall permit future connection to simulated sensor feeds
and utility monitoring systems without requiring source-specific
analytics logic.

### FR-DATA-003 --- Electrical inputs

Where available, the system shall support voltage and current
measurements for transformer phases.

### FR-DATA-004 --- Thermal inputs

Where available, the system shall support oil/top-oil temperature and
ambient temperature measurements.

### FR-DATA-005 --- Loading information

The system shall support direct loading information when available and
shall support deriving a load driver from available electrical
measurements when appropriate.

### FR-DATA-006 --- Asset information

The system shall support transformer asset information including asset
identity, rating, nameplate/configuration information, and verified
operating limits where available.

### FR-DATA-007 --- Historical data

The system shall support chronological historical/simulated telemetry
for replay and analysis.

### FR-DATA-008 --- Source provenance

Each accepted measurement shall remain traceable to its source record
and source context.

### FR-DATA-009 --- Raw-data preservation

The system shall preserve the original source record independently of
cleaned or derived data.

### FR-DATA-010 --- Unknown semantics

The system shall not silently assign a unit or physical meaning to an
input whose semantics are not established.

------------------------------------------------------------------------

## 5.2 Data Quality and Validation

### FR-QUAL-001 --- Schema validation

Incoming records shall be validated against the expected data contract.

### FR-QUAL-002 --- Unit validation

The system shall validate or explicitly identify measurement units
before engineering calculations use them.

### FR-QUAL-003 --- Range/plausibility checks

The system shall identify measurements that violate configured physical
or signal plausibility constraints.

### FR-QUAL-004 --- Missingness

The system shall identify missing measurements and expose their effect
on downstream capability.

### FR-QUAL-005 --- Duplicate handling

The system shall identify exact duplicate records and prevent duplicate
processing.

### FR-QUAL-006 --- Conflicting records

The system shall identify conflicting observations representing the same
asset/signal/time context.

### FR-QUAL-007 --- Temporal ordering

The system shall preserve event-time ordering for chronological
processing.

### FR-QUAL-008 --- Late data

The system shall identify late/out-of-order events and process them
according to the system's replay/reconciliation behavior.

### FR-QUAL-009 --- No silent imputation

The system shall not silently replace missing or invalid observed values
with fabricated measurements.

### FR-QUAL-010 --- Quality visibility

Data-quality issues that materially affect an output shall be visible to
the user and included in provenance.

------------------------------------------------------------------------

# 6. Digital Twin Requirements

## 6.1 Stateful representation

### FR-TWIN-001 --- Asset state

The system shall maintain a stateful representation of the monitored
transformer.

### FR-TWIN-002 --- State synchronization

The state shall update as valid chronological observations are
processed.

### FR-TWIN-003 --- Determinism

Given the same ordered observations and the same versioned
configuration/artifacts, the resulting state and material outputs shall
be reproducible.

### FR-TWIN-004 --- Historical replay

The system shall support replaying historical telemetry through the same
state-transition logic used by the operational system.

### FR-TWIN-005 --- Checkpointing

The system shall support state checkpoints sufficient to reproduce or
restore processing.

### FR-TWIN-006 --- Provenance

State-derived outputs shall retain references to relevant observations,
transformations, and versions.

## 6.2 State representation

The system shall be capable of representing, where supported:

-   current observations;
-   electrical operating state;
-   thermal state;
-   anomaly detector state;
-   active anomaly episodes;
-   condition/health state;
-   thermal exposure;
-   maintenance/advisory state;
-   model/configuration versions;
-   operator feedback.

The system shall distinguish observed, derived, estimated, configured,
latent, and unavailable information.

------------------------------------------------------------------------

# 7. Electrical Monitoring Requirements

### FR-ELEC-001 --- Voltage monitoring

The system shall monitor available phase-to-neutral and/or
phase-to-phase voltage measurements.

### FR-ELEC-002 --- Current monitoring

The system shall monitor available phase-current measurements.

### FR-ELEC-003 --- Loading assessment

The system shall derive or consume a transformer loading indicator from
available valid electrical information.

### FR-ELEC-004 --- Power relationships

Where the required inputs exist, the system shall derive active,
reactive, apparent-power and power-factor relationships.

### FR-ELEC-005 --- Phase imbalance

Where sufficient phase measurements exist, the system shall identify
phase-current and/or voltage imbalance.

### FR-ELEC-006 --- Neutral condition

Where neutral current information exists, the system shall expose
relevant neutral-current indicators.

### FR-ELEC-007 --- Electrical consistency

Where sufficient measurements exist, the system shall identify
materially inconsistent electrical relationships.

### FR-ELEC-008 --- Missing electrical signals

The absence of an electrical signal shall reduce only the capabilities
that depend on that signal; it shall not cause unrelated functionality
to fail.

------------------------------------------------------------------------

# 8. Thermal Monitoring and Prediction Requirements

## 8.1 Thermal monitoring

### FR-THERM-001 --- Ambient monitoring

The system shall monitor ambient temperature when available.

### FR-THERM-002 --- Oil-temperature monitoring

The system shall monitor oil/top-oil temperature when available and
semantically established.

### FR-THERM-003 --- Thermal trends

The dashboard shall expose thermal trends over an appropriate selected
time window.

### FR-THERM-004 --- Thermal quality

Thermal outputs shall identify whether the underlying measurements are
observed, estimated, unavailable, stale, or otherwise quality-limited.

## 8.2 Expected thermal behavior

### FR-THERM-005 --- Expected behavior

Where sufficient valid telemetry and calibration evidence exist, the
system shall estimate expected top-oil behavior under current operating
conditions.

### FR-THERM-006 --- Thermal residual

Where an expected value exists, the system shall be capable of comparing
observed and expected thermal behavior.

### FR-THERM-007 --- Thermal projection

Where the thermal capability is promoted, the system shall provide a
bounded short-horizon conditional top-oil projection.

### FR-THERM-008 --- Scenario assumptions

Any thermal scenario projection shall clearly identify its assumed load
and ambient conditions.

### FR-THERM-009 --- Uncertainty

A promoted thermal projection shall expose an empirical uncertainty
interval and its validation coverage.

### FR-THERM-010 --- Model promotion

The system shall only expose model-dependent predictive capabilities
when the model satisfies predefined validation/promotion requirements.

### FR-THERM-011 --- Thermal fallback

If predictive thermal capability is not supported, the system shall
enter an explicit fallback mode rather than presenting an unvalidated
prediction as valid.

### FR-THERM-012 --- Fallback behavior

In fallback mode, the system may continue to provide observed thermal
trends and cautious persistence-based expected behavior, but shall not
claim causal load/ambient what-if prediction or model-dependent
predictive recommendations.

### FR-THERM-013 --- Extrapolation

The system shall identify when a requested thermal scenario is outside
the calibrated operating range.

------------------------------------------------------------------------

# 9. Abnormal Condition and Anomaly Requirements

### FR-ANOM-001 --- Data-quality abnormality

The system shall identify material data-integrity problems as distinct
from physical operating abnormalities.

### FR-ANOM-002 --- Engineering checks

The system shall evaluate configured engineering conditions and
operating limits where reliable thresholds exist.

### FR-ANOM-003 --- Thermal deviation

Where a validated expected thermal value exists, the system shall
identify material deviations between observed and expected behavior.

### FR-ANOM-004 --- Persistent deviation

The system shall support identification of persistent deviations rather
than treating every isolated deviation as an incident.

### FR-ANOM-005 --- CUSUM

Where its calibration requirements are satisfied, the system shall
support two-sided cumulative residual detection.

### FR-ANOM-006 --- CUSUM disablement

The system shall disable model-dependent CUSUM escalation when its
calibration requirements cannot be established.

### FR-ANOM-007 --- Evidence categories

Anomaly evidence shall distinguish categories such as data quality,
sensor plausibility, thermal deviation, thermal limits, loading,
phase/neutral behavior, voltage/PF/frequency, and protection/oil status.

### FR-ANOM-008 --- Evidence lineage

Each material anomaly evidence item shall identify its supporting
observations and applicable configuration/model/rule versions.

### FR-ANOM-009 --- Corroboration

Critical non-protection conditions shall require appropriate independent
corroborating evidence according to the frozen architecture.

### FR-ANOM-010 --- No unsupported diagnosis

The system shall not present a hypothesis as a confirmed physical root
cause unless the evidence and source explicitly support that conclusion.

------------------------------------------------------------------------

# 10. Anomaly Episode Requirements

### FR-EPI-001 --- Episode creation

The system shall group persistent related evidence into anomaly
episodes.

### FR-EPI-002 --- Episode states

The system shall support lifecycle states for
normal/watch/warning/critical/recovering/closed behavior as defined by
the frozen architecture.

### FR-EPI-003 --- Hysteresis

The episode mechanism shall avoid unnecessary alert flapping through
persistence and recovery conditions.

### FR-EPI-004 --- Evidence history

An episode shall retain its supporting evidence timeline.

### FR-EPI-005 --- Data gaps

The system shall distinguish a data gap from a physical recovery.

### FR-EPI-006 --- Severity

Episode severity shall reflect evidence precedence and corroboration
requirements rather than a black-box confidence score.

------------------------------------------------------------------------

# 11. Transformer Health Index Requirements

### FR-HEALTH-001 --- Operational health index

The system shall provide an **Operational Transformer Health Index
(OTHI)** representing current operational condition rather than
whole-life insulation or asset health.

### FR-HEALTH-002 --- Health domains and condition families

Where evidence exists, OTHI shall consider 5 exact condition domains:
- thermal condition;
- loading;
- phase/neutral behavior;
- voltage/power-factor/frequency behavior;
- oil/protection status.

Evidence items shall declare a `condition_family`. Domain severity $s_d \in [0.0, 1.0]$ shall be evaluated as the maximum severity among eligible non-duplicative condition families in that domain. Derived representations of the same physical condition shall not sum. Secondary penalties across domains shall apply only to semantically distinct condition families.

### FR-HEALTH-003 --- Transparent aggregation (`MAX_PLUS_SECONDARY_V1`)

The health calculation shall use the versioned `MAX_PLUS_SECONDARY_V1` aggregation rule:

`Base penalty = maximum domain severity`

`Secondary penalty = 0.20 × sum of remaining non-duplicative domain severities`

`Total penalty = min(1.0, base penalty + secondary penalty)`

`OTHI = round(100 × (1 − total penalty))`

The 0.20 factor shall remain an explicit, versioned product-policy parameter, satisfying monotonicity, permutation invariance, max/tie invariance, and saturation clamping.

### FR-HEALTH-004 --- Domain independence

Individual domain severities shall remain inspectable rather than being
hidden inside an opaque composite model.

### FR-HEALTH-005 --- Evidence sufficiency, staleness, and anti-uplift

The system shall withhold a numeric OTHI when minimum evidence requirements are not satisfied ($\ge 2$ current domains or 1 decisive direct trip required).
The system shall enforce cadence-based staleness (`CURRENT`, `WARNING_STALE`/`HELD_STALE`, `HARD_STALE`) and the **Anti-Uplift Rule**: loss of observability must never improve health. If missing evidence makes the score appear healthier than the last-known abnormal condition, the system shall withhold numeric `current_othi` and expose `last_valid_othi` with staleness metadata. Categorical health-band transitions shall follow active episode persistence (direct trips immediately transition to `CRITICAL`).

### FR-HEALTH-006 --- Evidence grade

The system shall provide a deterministic evidence grade ($A, B, C, U$) associated with OTHI.

### FR-HEALTH-007 --- Data-quality treatment

Poor telemetry quality shall reduce evidence confidence or withhold the
index where appropriate; it shall not automatically be interpreted as
physical transformer deterioration.

### FR-HEALTH-008 --- Driving condition

When an OTHI value is available, the system shall expose the primary
domain driving the score.

------------------------------------------------------------------------

# 12. Thermal Exposure and Ageing Requirements

### FR-AGE-001 --- Thermal exposure

Where valid temperature history exists, the system shall quantify
observable thermal exposure such as temperature peaks, time in
temperature bands ($T_o > 85^\circ\text{C}, > 95^\circ\text{C}, > 105^\circ\text{C}$), and degree-hours above configured thresholds.

### FR-AGE-002 --- Capability-specific ageing eligibility

Standards-derived thermal equivalent ageing (C4) shall be decoupled from grey-box ODE promotion (C3). A verified direct hot-spot measurement with a verified insulation profile (`CELLULOSIC_NON_THERMALLY_UPGRADED` or `CELLULOSIC_THERMALLY_UPGRADED`) shall enable relative ageing calculation ($F_{AA}$ / $V$) and equivalent ageing hours ($L_{eq}$) even if the C3 top-oil ODE is unpromoted. Model-derived hot-spot ageing shall require a promoted C3 model. Every standards-derived calculation shall record explicit standard edition metadata (e.g. IEEE Std C57.91-2011 / IEC 60076-7:2018).

### FR-AGE-003 --- WTI limitation

A winding-temperature indicator contact shall not automatically be treated as a
validated hot-spot measurement without supporting evidence.

### FR-AGE-004 --- No RUL inference

Thermal ageing calculations shall not be converted into numeric
remaining useful life or failure probabilities without a separately validated
degradation/end-of-life model and data basis.

------------------------------------------------------------------------

# 13. Maintenance Decision-Support Requirements

### FR-MNT-001 --- Recommendations

The system shall provide condition-based maintenance recommendations
derived from sufficiently supported evidence.

### FR-MNT-002 --- Rule traceability and safe advisory wording

Each recommendation shall identify the rule that generated it (`MNT-PROT-001` .. `MNT-MODEL-007`), using safe advisory wording ("review", "inspect", "investigate", not confirmed failure). Model/CUSUM-derived thermal recommendations shall be suppressed when the underlying model is unqualified. Upper uncertainty-band crossings alone shall trigger P3 monitoring rather than urgent inspection.

### FR-MNT-003 --- Evidence requirement

Each recommendation shall identify the evidence required to trigger it.

### FR-MNT-004 --- Priority

Recommendations shall have an explicit priority from the locked hierarchy (`P0 SAFETY`, `P1 URGENT_INSPECTION`, `P2 PLANNED_ACTION`, `P3 MONITOR`, `P4 DATA_OR_MODEL`).

### FR-MNT-005 --- Action window and provenance metadata

Recommendations shall communicate an appropriate qualitative action window (`IMMEDIATE`, `WITHIN_24H`, `NEXT_AUTHORIZED_MAINTENANCE_WINDOW`, `MONITOR`, `MODEL_REVIEW`) accompanied by explicit provenance metadata (`window_provenance_type` $\in$ [`APPLICABLE_STANDARD_OR_GUIDE`, `MANUFACTURER_REQUIREMENT`, `PROTECTION_OR_SITE_PROCEDURE`, `OPERATOR_POLICY`, `ENGINEERING_POLICY`, `DEMO_DEFAULT`], `window_source_reference`, `source_version`, `approved_by`, `binding_vs_advisory`).

### FR-MNT-006 --- Suppression and merging

Data-quality problems shall suppress recommendations that depend on invalid measurements (never P0 protection). Recommendations sharing a `merge_key` shall be merged preserving all supporting rule IDs and adopting the strictest compatible action window. Incompatible recommendations shall escalate to qualified human review.

### FR-MNT-007 --- Conflict handling

Conflicting recommendations shall follow deterministic precedence and
escalate to qualified human review where required.

### FR-MNT-008 --- No automatic control

Recommendations shall not directly actuate transformer protection or
control equipment.

### FR-MNT-009 --- Immutable human feedback ledger

The system shall support acknowledgement (`ACKNOWLEDGE`), dismissal (`DISMISS` with actor/reason/rationale), and inspection findings (`INSPECTION_OUTCOME`) via an append-only immutable audit ledger (`POST /v1/feedback`). Historical telemetry, evidence items, and calculated OTHI records shall never be rewritten. P0 safety recommendations cannot be silently dismissed.

### FR-MNT-010 --- Canonical API route

The canonical recommendation endpoint shall be asset-scoped: `GET /v1/assets/{asset_id}/recommendations`.

------------------------------------------------------------------------

# 14. Dashboard Requirements

### FR-UI-001 --- Overview

The dashboard shall provide an overview of current transformer operating
condition.

### FR-UI-002 --- Loading

The dashboard shall display transformer loading or the best-supported
relative load indicator.

### FR-UI-003 --- Temperature

The dashboard shall display available ambient and oil/top-oil
temperature information.

### FR-UI-004 --- Health

The dashboard shall display OTHI when sufficient evidence exists,
including status and evidence grade.

### FR-UI-005 --- Alerts

The dashboard shall display active anomaly episodes and their severity.

### FR-UI-006 --- Recommendations

The dashboard shall display active maintenance recommendations and
action windows.

### FR-UI-007 --- Trends

The dashboard shall display relevant historical trends.

### FR-UI-008 --- Evidence

Users shall be able to inspect the evidence behind material condition
and anomaly outputs.

### FR-UI-009 --- Quality

The dashboard shall make important data-quality limitations visible.

### FR-UI-010 --- Scenario view

Where predictive thermal capability is enabled, the dashboard shall
allow users to inspect bounded conditional thermal scenarios.

### FR-UI-011 --- Degraded mode

The dashboard shall clearly communicate capability fallback/degradation,
including thermal-model fallback.

### FR-UI-012 --- 3D conditionality

If a 3D component view is implemented, it shall represent system state
and link back to the same underlying evidence. The 3D layer shall not be
a prerequisite for the core dashboard.

------------------------------------------------------------------------

# 15. Reporting Requirements

### FR-REP-001 --- Condition report

The system shall support a transformer condition report containing
condition, evidence, trends, recommendations, coverage, and limitations.

### FR-REP-002 --- Anomaly report

The system shall support an anomaly-event report containing the episode
timeline, evidence, severity transitions, recommendations, and
provenance.

### FR-REP-003 --- Data/model report

The system shall support a technical data/model report describing data
coverage, mappings, model/calibration information, capabilities,
metrics, and limitations.

### FR-REP-004 --- Export

The system shall support machine-readable JSON and CSV exports.

### FR-REP-005 --- PDF

The system shall support a deterministic PDF representation of core
condition/anomaly reporting.

### FR-REP-006 --- Consistency

Reports shall consume the same authoritative facts used by the dashboard
and shall not independently recompute health or recommendations.

### FR-REP-007 --- Provenance

Reports shall include sufficient provenance to identify the source data,
selected period, versions, and generation context.

------------------------------------------------------------------------

# 16. Explainability and Provenance Requirements

### FR-EXP-001 --- Evidence traceability

Material outputs shall be traceable to supporting source observations or
derived evidence.

### FR-EXP-002 --- Version traceability

Outputs shall identify relevant schema, configuration,
model/calibration, rule, adapter, and software versions.

### FR-EXP-003 --- Observed/derived distinction

The system shall distinguish observed measurements from derived and
estimated values.

### FR-EXP-004 --- Assumption visibility

Material assumptions shall be visible to users when they affect
interpretation.

### FR-EXP-005 --- Reproducibility

A historical output shall be reproducible using the corresponding source
data and versioned artifacts.

### FR-EXP-006 --- Optional narrative

Any future generative narrative shall operate only on validated system
facts and shall not create unsupported numerical or engineering claims.

------------------------------------------------------------------------

# 17. Feedback Requirements

### FR-FBK-001 --- Acknowledgement

Users shall be able to acknowledge an alert/recommendation.

### FR-FBK-002 --- Inspection outcome

The system shall support recording an inspection/action outcome.

### FR-FBK-003 --- Auditability

Feedback shall be retained as an event with timestamp, user/action
context, and associated episode/recommendation.

### FR-FBK-004 --- No automatic model learning

Feedback shall not silently alter production model parameters or rules.

------------------------------------------------------------------------

# 18. Non-Functional Requirements

## 18.1 Reliability

### NFR-REL-001

The system shall fail safely when required data or model capabilities
are unavailable.

### NFR-REL-002

A failure in an optional subsystem shall not make the core monitoring
interface unavailable.

### NFR-REL-003

Direct protection/critical evidence shall retain its precedence over
model-dependent evidence where configured.

## 18.2 Determinism

### NFR-DET-001

Identical ordered inputs and identical versioned artifacts shall produce
identical material outputs.

### NFR-DET-002

Tie-breaking, ordering, and aggregation behavior shall be deterministic.

## 18.3 Auditability

### NFR-AUD-001

Material decisions shall be traceable to evidence.

### NFR-AUD-002

Raw observations shall not be overwritten by derived or cleaned values.

### NFR-AUD-003

Configuration and model versions shall be retained with outputs.

## 18.4 Performance

### NFR-PERF-001

The prototype shall support chronological replay of the selected
development dataset within a practical hackathon demonstration time.

### NFR-PERF-002

Dashboard interactions shall remain responsive for the supported
demonstration dataset.

### NFR-PERF-003

Performance optimization shall not change analytical results.

Exact performance targets shall be established during implementation
based on measured workload rather than invented before the dataset and
execution profile are known.

## 18.5 Usability

### NFR-USE-001

The dashboard shall expose the current condition, important evidence,
and recommended action without requiring the user to inspect raw data.

### NFR-USE-002

Critical visual states shall not rely on color alone.

### NFR-USE-003

Unknown, unavailable, estimated, and observed values shall be
distinguishable.

## 18.6 Extensibility

### NFR-EXT-001

The system shall separate source-specific mappings from analytics logic.

### NFR-EXT-002

The system shall permit future integration with real monitoring systems
through the canonical data contract.

### NFR-EXT-003

New supported signals shall not require rewriting unrelated analytics
modules.

## 18.7 Security and safety

### NFR-SEC-001

The prototype shall not expose endpoints that directly control
transformer protection or physical equipment.

### NFR-SEC-002

Input validation shall prevent malformed external data from entering
engineering calculations.

### NFR-SEC-003

Future live integrations shall preserve source identity and provenance.

------------------------------------------------------------------------

# 19. Capability and Graceful-Degradation Requirements

The system shall evaluate capabilities based on available evidence
rather than assuming all functions are always active.

The conceptual capability progression is:

  -----------------------------------------------------------------------
  Capability                          Requirement
  ----------------------------------- -----------------------------------
  C0 --- Data integrity               Basic data validation, provenance,
                                      ordering, and quality assessment.

  C1 --- Electrical monitoring        Valid electrical measurements and
                                      derived operating indicators.

  C2 --- Thermal descriptive          Valid ambient/oil-temperature
                                      observation and thermal trends.

  C3 --- Thermal predictive           Promoted thermal model, validated
                                      residuals, uncertainty, and
                                      short-horizon conditional
                                      projection.

  C4 --- Thermal exposure             Valid temperature exposure and,
                                      only when justified, thermal
                                      equivalent ageing.
  -----------------------------------------------------------------------

A missing capability shall not automatically disable unrelated
capabilities.

For example, inability to produce a validated thermal prediction shall
not prevent the system from showing valid electrical observations,
direct engineering-limit evidence, anomaly episodes based on direct
evidence, or an OTHI when its evidence requirements are satisfied.

------------------------------------------------------------------------

# 20. Data and Development Sources

## 20.1 Final hackathon data

The final CPRI/hackathon-provided simulated dataset and schema shall be
the target dataset for the final demonstration.

The final schema and signal semantics supplied by CPRI shall take
precedence over development assumptions.

## 20.2 Development/calibration data

The Tripura distribution-transformer monitoring dataset is the locked
development/calibration source for the prototype.

Its actual signal semantics and usable fields shall be established
through data audit before model calibration.

## 20.3 Draft condition-monitoring workbook

The supplied `Draft Data for Condition Monitoring.xlsx` shall be treated
as a supporting/reference commissioning artefact.

It shall not be treated as a telemetry training dataset unless a future
authoritative source establishes that role.

Its measurement/trip-test information may support documented
threshold/configuration references where semantics are explicitly
established.

------------------------------------------------------------------------

# 21. Validation Requirements

The system shall be validated at multiple levels.

## 21.1 Data validation

Validation shall cover:

-   schema/type errors;
-   unknown units;
-   range violations;
-   missing values;
-   duplicates;
-   conflicting duplicates;
-   timestamp irregularities;
-   gaps;
-   late events;
-   source-quality conditions.

Validation shall also demonstrate the source-adapter boundary using a
second fixture with intentionally different source field names and/or
units. The fixture shall map into the same canonical contract without
requiring downstream analytics changes. This fixture is a validation
artefact, not a claim about the final CPRI schema.

## 21.2 Model validation

Where a thermal model is promoted, validation shall establish:

-   chronological separation of development and test data;
-   no future-data leakage;
-   prediction error;
-   bias;
-   uncertainty coverage;
-   behavior across relevant operating regions;
-   behavior inside and outside the calibrated range.

## 21.3 Anomaly validation

Validation shall include controlled synthetic scenarios for:

-   sensor spikes;
-   stuck values;
-   slow bias;
-   unit/scale errors;
-   timestamp problems;
-   gaps;
-   duplicate/conflicting data;
-   persistent thermal residual shifts;
-   loading changes;
-   phase imbalance;
-   direct protection/status events.

Synthetic scenarios shall validate logic and sensitivity and shall not
be presented as evidence of real-world fault-detection accuracy.

## 21.4 End-to-end validation

The system shall validate:

`source data → canonical data → quality → features → state → evidence → episode → OTHI → maintenance → FactBundle → dashboard/report`

The same authoritative facts shall remain consistent across outputs.

------------------------------------------------------------------------

# 22. Requirements Traceability

The principal requirements trace to the official problem statement as
follows:

  -----------------------------------------------------------------------
  Problem-statement requirement       SRS coverage
  ----------------------------------- -----------------------------------
  Simulate transformer behavior using FR-TWIN, FR-THERM
  operational data                    

  Monitor voltage                     FR-ELEC-001

  Monitor current                     FR-ELEC-002

  Monitor loading                     FR-ELEC-003

  Monitor oil temperature             FR-THERM-002

  Monitor ambient temperature         FR-THERM-001

  Estimate transformer health         FR-HEALTH

  Detect abnormal conditions          FR-ANOM, FR-EPI

  Generate alerts                     FR-ANOM, FR-EPI, FR-UI-005

  Predictive maintenance              FR-MNT
  recommendations                     

  Interactive dashboard               FR-UI

  Health score visualization          FR-UI-004

  Trend analysis                      FR-UI-007, FR-REP

  Performance reports                 FR-REP

  Downloadable summaries              FR-REP-004/005

  Extendability to real               FR-DATA-002, FR-EXT
  sensors/utility systems             

  Technical documentation             Project deliverable requirement

  Source code and execution           Project deliverable requirement
  instructions                        

  Live/recorded demonstration         Project deliverable requirement
  -----------------------------------------------------------------------

The problem statement also lists AI/ML models, fault prediction, and RUL
as possible architecture/analytics functions. The project records an
explicit boundary around these capabilities rather than treating their
mention as a requirement to produce unsupported outputs.

------------------------------------------------------------------------

# 23. Constraints and Assumptions

## 23.1 Constraints

-   The prototype is developed within the hackathon timeline.
-   The final CPRI dataset/schema may differ from the development
    dataset.
-   Transformer-specific metadata may be incomplete.
-   Sensor semantics and units may require verification.
-   Historical data quality may be imperfect.
-   Validation labels for real faults may be scarce or absent.
-   Physical closed-loop control is outside project scope.

## 23.2 Assumptions

The following are assumptions only until verified:

-   Required electrical and thermal measurements exist in sufficient
    quantity for their respective capabilities.
-   Transformer rating and operating limits can be established where
    absolute loading/threshold claims require them.
-   Temperature signals can be assigned physical meaning only after
    source/schema verification.
-   A predictive thermal model may or may not pass its promotion
    criteria.
-   Optional capabilities may therefore be unavailable in the final
    demonstration.

Assumptions shall never be presented as measured facts.

------------------------------------------------------------------------

# 24. Acceptance Summary

The SRS is satisfied when the final prototype demonstrates, within the
supported data and capability gates:

1.  Valid transformer telemetry ingestion.
2.  Source-adapter validation using an alternate schema fixture with different field names and/or units, producing the same canonical contract without downstream changes.
3.  Explicit data-quality handling.
4.  Stateful chronological Digital Twin behavior.
5.  Electrical and thermal monitoring.
6.  Operational health assessment where evidence permits.
7.  Abnormal-condition detection and persistent episodes.
8.  Conditional short-horizon thermal projection when the model is
    promoted.
9.  Explicit thermal fallback when it is not.
10. Traceable maintenance recommendations.
11. Interactive dashboard, including critical-state accessibility and
    explicit observed/estimated/unavailable distinctions.
12. Reproducible reports/exports.
13. Evidence and provenance for material outputs.
14. Graceful degradation when data/capabilities are missing.
15. No unsupported claims of RUL, failure probability, or autonomous
    control.

------------------------------------------------------------------------

# 25. Relationship to the Next Document

This SRS defines **what the product must do and the boundaries within
which it must operate**.

The next document, `MVP.md`, shall define **which subset of these
requirements is implemented for the hackathon, the concrete user
journey, implementation priorities, required modules, demo path, and
definition of MVP completion**.

The MVP document shall not silently change the requirements or frozen
architecture. Any genuine scope change shall be explicitly identified
and reviewed.
