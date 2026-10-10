// Display context for the asset the backend is serving.

export interface AssetContext {
  isCpri: boolean;
  datasetId: string;
  datasetLabel: string;
  siteLabel: string;
  cadenceSeconds: number;
  cadenceLabel: string;
  ratedKva: number | null;
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

export function getAssetContext(assetId: string): AssetContext {
  const cleanId = (assetId || '').trim();
  if (cleanId in CPRI_ASSET_RATINGS) {
    const kva = CPRI_ASSET_RATINGS[cleanId];
    return {
      isCpri: true,
      datasetId: 'cpri_v3_0_2',
      datasetLabel: 'CPRI Synthetic Benchmark v3.0.2 — CAL partition replay',
      siteLabel: `CPRI synthetic asset (${kva} kVA, 30-min cadence)`,
      cadenceSeconds: 1800,
      cadenceLabel: '30 min',
      ratedKva: kva,
    };
  }
  return {
    isCpri: false,
    datasetId: 'tripura_dev',
    datasetLabel: 'Tripura Transformer — Development Dataset',
    siteLabel: 'Tripura 33/11kV Substation',
    cadenceSeconds: 900,
    cadenceLabel: '15 min',
    ratedKva: null,
  };
}
