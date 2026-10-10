import React, { useEffect, useState } from 'react';
import { api, CpriModelEvaluation, CpriModelEvaluationRow } from '../../services/api';

interface ModelEvaluationMatrixProps {
  currentAssetId: string;
}

const GATE_LABELS: Record<string, string> = {
  mae_improvement: 'MAE',
  signed_bias: 'Bias',
  coverage_band: 'Coverage',
  identifiability: 'Ident.',
};

const MODEL_CAPS: [string, string][] = [
  ['descriptive_thermal', 'Descriptive thermal'],
  ['residual_anomaly_evidence', 'Residual anomaly'],
  ['forecasting', 'Forecast'],
  ['what_if', 'What-if'],
];

const num = (v: number | null | undefined, d = 2): string => (v == null ? '—' : v.toFixed(d));

const Flag: React.FC<{ ok: boolean | null | undefined; title?: string }> = ({ ok, title }) => (
  <span title={title} className={`chip font-mono ${ok ? 'chip-ok' : ok === false ? 'chip-warn' : ''}`}>
    {ok ? 'PASS' : ok === false ? 'FAIL' : '—'}
  </span>
);

const Row: React.FC<{ row: CpriModelEvaluationRow; isCurrent: boolean }> = ({ row, isCurrent }) => {
  const m = row.metrics;
  return (
    <tr className={`border-t border-line align-top ${isCurrent ? 'bg-surface-2' : ''}`}>
      <td className="py-2 pr-3 font-mono text-ink whitespace-nowrap">
        {row.asset_id}
        {isCurrent && <span className="block text-[10px] text-muted">live asset</span>}
      </td>
      <td className="py-2 pr-3 font-mono whitespace-nowrap">
        {row.promotion_status}
        <span className="block text-[10px] text-muted">
          {row.fit_status === 'NOT_FITTED' ? 'not fitted' : `sha ${row.artifact_sha256?.slice(0, 10)}`} · TEST {row.test_partition.toLowerCase()}
        </span>
      </td>
      <td className="py-2 pr-3 font-mono whitespace-nowrap">
        {m ? `${num(m.mae_2h_degc, 3)} / ${num(m.persistence_mae_2h_degc, 3)}` : '—'}
        {m && <span className="block text-[10px] text-muted">{num(m.mae_improvement_pct, 1)}% better</span>}
      </td>
      <td className="py-2 pr-3 font-mono whitespace-nowrap">
        {m ? `${num(m.signed_bias_degc, 3)} / ${num(m.persistence_signed_bias_degc, 3)}` : '—'}
      </td>
      <td className="py-2 pr-3 font-mono whitespace-nowrap">
        {m ? `${num(m.marginal_coverage_90_pct, 1)}% / ${num(m.path_coverage_90_pct, 1)}%` : '—'}
      </td>
      <td className="py-2 pr-3">
        <div className="flex flex-wrap gap-1">
          {Object.entries(GATE_LABELS).map(([k, label]) => (
            <span key={k} className="inline-flex items-center gap-1 text-[10px]">
              {label} <Flag ok={row.gates ? row.gates[k] : null} />
            </span>
          ))}
        </div>
      </td>
      <td className="py-2">
        <div className="flex flex-wrap gap-1">
          {MODEL_CAPS.map(([k, label]) => {
            const cap = row.capabilities[k];
            return (
              <span
                key={k}
                title={cap?.reason}
                className={`chip text-[10px] ${cap?.available ? 'chip-ok' : ''}`}
              >
                {label}: {cap?.available ? 'on' : 'gated'}
              </span>
            );
          })}
        </div>
      </td>
    </tr>
  );
};

export const ModelEvaluationMatrix: React.FC<ModelEvaluationMatrixProps> = ({ currentAssetId }) => {
  const isCandidateAsset = currentAssetId.startsWith('DT-');
  const [selectedDataset, setSelectedDataset] = useState<'cpri_v3_0_2' | 'gridpulse_synthetic_v1'>(
    isCandidateAsset ? 'gridpulse_synthetic_v1' : 'cpri_v3_0_2'
  );
  const [data, setData] = useState<CpriModelEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isCandidateAsset) {
      setSelectedDataset('gridpulse_synthetic_v1');
    } else {
      setSelectedDataset('cpri_v3_0_2');
    }
  }, [currentAssetId, isCandidateAsset]);

  useEffect(() => {
    setError(null);
    setData(null);
    const fetcher =
      selectedDataset === 'gridpulse_synthetic_v1'
        ? api.getCandidateModelEvaluation()
        : api.getCpriModelEvaluation();

    fetcher
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Request failed'));
  }, [selectedDataset]);

  return (
    <section className="card p-6 mt-8 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
        <span className="eyebrow block">
          {selectedDataset === 'gridpulse_synthetic_v1'
            ? 'GridPulse Synthetic v1.0.0 · Candidate evaluation matrix'
            : 'CPRI v3.0.2 · Baseline thermal model evaluation'}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSelectedDataset('cpri_v3_0_2')}
            className={`btn text-xs py-1 px-3 ${
              selectedDataset === 'cpri_v3_0_2' ? 'btn-primary' : 'btn-ghost'
            }`}
          >
            CPRI Benchmark (8 Assets)
          </button>
          <button
            onClick={() => setSelectedDataset('gridpulse_synthetic_v1')}
            className={`btn text-xs py-1 px-3 ${
              selectedDataset === 'gridpulse_synthetic_v1' ? 'btn-primary' : 'btn-ghost'
            }`}
          >
            GridPulse Candidates (4 Assets)
          </button>
        </div>
      </div>
      <h2 className="section-title">Model Qualification &amp; Capability Matrix</h2>
      <p className="text-muted mt-2 max-w-3xl leading-relaxed">
        Each asset is fitted independently on FIT, uncertainty-calibrated on CAL, frozen and hashed, then evaluated once on its
        TEST partition. Monitoring, anomaly detection, OTHI and rule-based maintenance advisories are operational for every asset
        from measured telemetry; forecasting and what-if require a qualified model.
      </p>
      {error && <p className="text-warn mt-3">Evaluation matrix unavailable: {error}</p>}
      {!data && !error && <p className="text-muted mt-3">Loading evaluation records…</p>}
      {data && (
        <>
          <div className="overflow-x-auto mt-4">
            <table className="w-full text-left">
              <thead className="text-muted">
                <tr>
                  <th className="pb-2 pr-3 font-medium">Asset</th>
                  <th className="pb-2 pr-3 font-medium">Status</th>
                  <th className="pb-2 pr-3 font-medium">2-h MAE model / persist. (°C)</th>
                  <th className="pb-2 pr-3 font-medium">Signed bias model / persist. (°C)</th>
                  <th className="pb-2 pr-3 font-medium">90% coverage marginal / path</th>
                  <th className="pb-2 pr-3 font-medium">Gates</th>
                  <th className="pb-2 font-medium">Model-dependent capabilities</th>
                </tr>
              </thead>
              <tbody>
                {data.assets.map((row) => (
                  <Row key={row.asset_id} row={row} isCurrent={row.asset_id === currentAssetId} />
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-4 text-[11px] text-muted space-y-0.5">
            {Object.entries(data.promotion_policy).map(([k, v]) => (
              <li key={k}>
                <span className="font-mono text-ink-2">{GATE_LABELS[k] ?? k}</span>: {v}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
};
