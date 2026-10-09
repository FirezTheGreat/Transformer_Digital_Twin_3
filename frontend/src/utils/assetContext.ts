// Display context for the asset the backend is serving (set via the backend's DEFAULT_ASSET_ID).

export interface AssetContext {
  isCpri: boolean;
  datasetId: string;
  datasetLabel: string;
  siteLabel: string;
}

const CPRI_ASSETS = new Set([
  'TX_100_RES',
  'TX_160_RURAL',
  'TX_250_MIX',
  'TX_315_RES',
  'TX_400_COMM',
  'TX_500_RURAL',
  'TX_630_MIX',
  'TX_1000_COMM',
]);

export function getAssetContext(assetId: string): AssetContext {
  if (CPRI_ASSETS.has(assetId)) {
    return {
      isCpri: true,
      datasetId: 'cpri_v3_0_2',
      datasetLabel: 'CPRI Synthetic Benchmark v3.0.2 — CAL partition replay',
      siteLabel: 'CPRI synthetic asset (30-min cadence)',
    };
  }
  return {
    isCpri: false,
    datasetId: 'tripura_dev',
    datasetLabel: 'Tripura Transformer — Development Dataset',
    siteLabel: 'Tripura 33/11kV Substation',
  };
}
