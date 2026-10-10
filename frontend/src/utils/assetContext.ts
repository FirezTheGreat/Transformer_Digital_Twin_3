// Display context and configuration for distribution transformer datasets and assets.

export interface AssetContext {
  isCpri: boolean;
  isCandidate: boolean;
  datasetId: string;
  datasetLabel: string;
  siteLabel: string;
  cadenceSeconds: number;
  cadenceLabel: string;
  ratedKva: number | null;
  tankType: 'CONSERVATOR' | 'SEALED_CORRUGATED' | 'UNKNOWN';
  hasOilGauge: boolean;
  hasPressureSensor: boolean;
  promotionStatus: 'PROMOTED' | 'NOT_PROMOTED' | 'UNVERIFIED';
}

export interface DatasetAssetDef {
  id: string;
  label: string;
  ratedKva: number;
  tankType: 'CONSERVATOR' | 'SEALED_CORRUGATED';
  status: 'PROMOTED' | 'NOT_PROMOTED';
  statusLabel: string;
  hasOilGauge: boolean;
  hasPressureSensor: boolean;
}

export interface DatasetOption {
  id: string;
  name: string;
  shortLabel: string;
  cadenceSeconds: number;
  cadenceLabel: string;
  defaultAssetId: string;
  description: string;
  statusBadge: string;
  assets: DatasetAssetDef[];
}

export const CPRI_ASSET_RATINGS: Record<string, number> = {
  TX_100_RES: 100.0,
  TX_160_RURAL: 160.0,
  TX_250_MIX: 250.0,
  TX_315_RES: 315.0,
  TX_400_COMM: 400.0,
  TX_500_RURAL: 500.0,
  TX_630_MIX: 630.0,
  TX_1000_COMM: 1000.0,
};

export const ALL_CPRI_ASSETS: string[] = Object.keys(CPRI_ASSET_RATINGS);

export const CANDIDATE_ASSET_DEFS: Record<string, DatasetAssetDef> = {
  'DT-01': {
    id: 'DT-01',
    label: 'DT-01 (250 kVA · Conservator)',
    ratedKva: 250.0,
    tankType: 'CONSERVATOR',
    status: 'PROMOTED',
    statusLabel: 'Promoted Candidate',
    hasOilGauge: true,
    hasPressureSensor: false,
  },
  'DT-02': {
    id: 'DT-02',
    label: 'DT-02 (500 kVA · Conservator)',
    ratedKva: 500.0,
    tankType: 'CONSERVATOR',
    status: 'NOT_PROMOTED',
    statusLabel: 'Unpromoted Candidate',
    hasOilGauge: true,
    hasPressureSensor: false,
  },
  'DT-03': {
    id: 'DT-03',
    label: 'DT-03 (250 kVA · Sealed Corr.)',
    ratedKva: 250.0,
    tankType: 'SEALED_CORRUGATED',
    status: 'NOT_PROMOTED',
    statusLabel: 'Unpromoted Candidate',
    hasOilGauge: false,
    hasPressureSensor: true,
  },
  'DT-04': {
    id: 'DT-04',
    label: 'DT-04 (160 kVA · Conservator)',
    ratedKva: 160.0,
    tankType: 'CONSERVATOR',
    status: 'NOT_PROMOTED',
    statusLabel: 'Unpromoted Candidate',
    hasOilGauge: true,
    hasPressureSensor: false,
  },
};

export const ALL_CANDIDATE_ASSETS: string[] = Object.keys(CANDIDATE_ASSET_DEFS);

export const DATASET_OPTIONS: Record<string, DatasetOption> = {
  cpri_v3_0_2: {
    id: 'cpri_v3_0_2',
    name: 'CPRI Synthetic Benchmark v3.0.2',
    shortLabel: 'CPRI Benchmark',
    cadenceSeconds: 1800,
    cadenceLabel: '30 min',
    defaultAssetId: 'TX_1000_COMM',
    description: 'Preserved baseline benchmark dataset and calibrated TX_1000_COMM checkpoint',
    statusBadge: 'Baseline / Rollback',
    assets: [
      { id: 'TX_1000_COMM', label: 'TX_1000_COMM (1000 kVA)', ratedKva: 1000, tankType: 'CONSERVATOR', status: 'PROMOTED', statusLabel: 'Promoted Baseline', hasOilGauge: false, hasPressureSensor: false },
      { id: 'TX_500_RURAL', label: 'TX_500_RURAL (500 kVA)', ratedKva: 500, tankType: 'CONSERVATOR', status: 'NOT_PROMOTED', statusLabel: 'Unpromoted', hasOilGauge: false, hasPressureSensor: false },
      { id: 'TX_630_MIX', label: 'TX_630_MIX (630 kVA)', ratedKva: 630, tankType: 'CONSERVATOR', status: 'NOT_PROMOTED', statusLabel: 'Unpromoted', hasOilGauge: false, hasPressureSensor: false },
      { id: 'TX_400_COMM', label: 'TX_400_COMM (400 kVA)', ratedKva: 400, tankType: 'CONSERVATOR', status: 'NOT_PROMOTED', statusLabel: 'Unpromoted', hasOilGauge: false, hasPressureSensor: false },
      { id: 'TX_315_RES', label: 'TX_315_RES (315 kVA)', ratedKva: 315, tankType: 'CONSERVATOR', status: 'NOT_PROMOTED', statusLabel: 'Unpromoted', hasOilGauge: false, hasPressureSensor: false },
      { id: 'TX_250_MIX', label: 'TX_250_MIX (250 kVA)', ratedKva: 250, tankType: 'CONSERVATOR', status: 'NOT_PROMOTED', statusLabel: 'Unpromoted', hasOilGauge: false, hasPressureSensor: false },
      { id: 'TX_160_RURAL', label: 'TX_160_RURAL (160 kVA)', ratedKva: 160, tankType: 'CONSERVATOR', status: 'NOT_PROMOTED', statusLabel: 'Unpromoted', hasOilGauge: false, hasPressureSensor: false },
      { id: 'TX_100_RES', label: 'TX_100_RES (100 kVA)', ratedKva: 100, tankType: 'CONSERVATOR', status: 'NOT_PROMOTED', statusLabel: 'Unpromoted', hasOilGauge: false, hasPressureSensor: false },
    ],
  },
  gridpulse_synthetic_v1: {
    id: 'gridpulse_synthetic_v1',
    name: 'GridPulse Synthetic Benchmark v1.0.0',
    shortLabel: 'GridPulse Synthetic',
    cadenceSeconds: 1800,
    cadenceLabel: '30 min',
    defaultAssetId: 'DT-01',
    description: 'Evaluated candidate dataset (DT-01 promoted, CAL partition replay)',
    statusBadge: 'Evaluated Candidate',
    assets: Object.values(CANDIDATE_ASSET_DEFS),
  },
};

export function getAssetContext(assetId: string): AssetContext {
  const cleanId = (assetId || '').trim();

  // GridPulse Synthetic candidate assets
  if (cleanId in CANDIDATE_ASSET_DEFS) {
    const def = CANDIDATE_ASSET_DEFS[cleanId];
    return {
      isCpri: false,
      isCandidate: true,
      datasetId: 'gridpulse_synthetic_v1',
      datasetLabel: 'GridPulse Synthetic v1.0.0 — CAL replay',
      siteLabel: `${def.id} (${def.ratedKva} kVA · ${def.tankType})`,
      cadenceSeconds: 1800,
      cadenceLabel: '30 min',
      ratedKva: def.ratedKva,
      tankType: def.tankType,
      hasOilGauge: def.hasOilGauge,
      hasPressureSensor: def.hasPressureSensor,
      promotionStatus: def.status,
    };
  }

  // CPRI Synthetic assets
  if (cleanId in CPRI_ASSET_RATINGS) {
    const kva = CPRI_ASSET_RATINGS[cleanId];
    return {
      isCpri: true,
      isCandidate: false,
      datasetId: 'cpri_v3_0_2',
      datasetLabel: 'CPRI Synthetic Benchmark v3.0.2 — CAL replay',
      siteLabel: `CPRI synthetic asset (${kva} kVA, 30-min cadence)`,
      cadenceSeconds: 1800,
      cadenceLabel: '30 min',
      ratedKva: kva,
      tankType: 'CONSERVATOR',
      hasOilGauge: false,
      hasPressureSensor: false,
      promotionStatus: cleanId === 'TX_1000_COMM' ? 'PROMOTED' : 'NOT_PROMOTED',
    };
  }

  // Fallback (e.g. Tripura or Unspecified)
  return {
    isCpri: false,
    isCandidate: false,
    datasetId: 'tripura_dev',
    datasetLabel: 'Tripura Transformer — Development Dataset',
    siteLabel: 'Tripura 33/11kV Substation',
    cadenceSeconds: 900,
    cadenceLabel: '15 min',
    ratedKva: null,
    tankType: 'CONSERVATOR',
    hasOilGauge: false,
    hasPressureSensor: false,
    promotionStatus: 'UNVERIFIED',
  };
}
