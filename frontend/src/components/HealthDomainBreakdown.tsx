import React from 'react';
import {
  Flame,
  Zap,
  Activity,
  Gauge,
  ShieldAlert,
  AlertTriangle,
} from 'lucide-react';
import { OTHIBundle, AnomalyEpisode } from '../types/contracts';

interface HealthDomainBreakdownProps {
  health: OTHIBundle | null;
  episodes: AnomalyEpisode[];
}

export const HealthDomainBreakdown: React.FC<HealthDomainBreakdownProps> = ({
  health,
  episodes,
}) => {
  const domains = health?.domains ?? {};

  const domainConfigs: Record<
    string,
    { label: string; icon: React.ReactNode; subtitle: string }
  > = {
    thermal: {
      label: 'Thermal Dynamics',
      icon: <Flame className="w-4 h-4 text-rose-500" />,
      subtitle: 'Top-oil, ambient & CUSUM residual',
    },
    loading: {
      label: 'Electrical Loading',
      icon: <Zap className="w-4 h-4 text-amber-500" />,
      subtitle: 'Apparent power & per-unit index',
    },
    phase_neutral: {
      label: 'Phase & Neutral',
      icon: <Activity className="w-4 h-4 text-[#0284c7]" />,
      subtitle: 'Current unbalance & neutral ratio',
    },
    voltage_pf_freq: {
      label: 'Voltage & Grid Quality',
      icon: <Gauge className="w-4 h-4 text-indigo-500" />,
      subtitle: 'Voltage symmetry, PF & 50Hz frequency',
    },
    oil_protection: {
      label: 'Protection & Oil Integrity',
      icon: <ShieldAlert className="w-4 h-4 text-emerald-600" />,
      subtitle: 'Discrete trips & magnetic gauge',
    },
  };

  return (
    <section className="mt-12 pb-12">
      {/* Editorial Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-8 pb-4 border-b border-[#d8e6f2]">
        <div>
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#5d768f] block mb-2">
            MULTI-DOMAIN OPERATIONAL HEALTH
          </span>
          <p className="text-sm text-[#5d768f]">
            Gated OTHI composite across 5 independent physical and electrical domains.
          </p>
        </div>
        <h3 className="mt-3 sm:mt-0 text-3xl sm:text-5xl font-normal font-editorial text-[#0e1824] tracking-tight">
          Domain breakdown.
        </h3>
      </div>

      {/* 5-Domain Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {Object.entries(domainConfigs).map(([key, cfg]) => {
          const domain = domains[key];
          const status = domain?.status ?? 'NORMAL';
          const severity = domain?.severity ?? 0.0;
          const details = domain?.details ?? 'Nominal operating state.';
          const evidenceCount = domain?.evidence_count ?? 0;

          const isWarning = status === 'WARNING';
          const isCritical = status === 'CRITICAL';
          const isWatch = status === 'WATCH';

          return (
            <div
              key={key}
              className="bg-white rounded-3xl p-6 shadow-card border border-[#d8e6f2] hover:border-[#bcd5eb] transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-[#eff5fb] border border-[#dce9f4] flex items-center justify-center">
                      {cfg.icon}
                    </div>
                    <div>
                      <h4 className="text-base font-editorial font-bold text-[#0e1824]">
                        {cfg.label}
                      </h4>
                      <p className="text-[11px] text-[#5d768f]">{cfg.subtitle}</p>
                    </div>
                  </div>

                  <span
                    className={`text-[10px] uppercase font-bold tracking-wider px-2.5 py-0.5 rounded-full ${
                      isCritical
                        ? 'bg-rose-100 text-rose-800'
                        : isWarning
                        ? 'bg-amber-100 text-amber-800'
                        : isWatch
                        ? 'bg-sky-100 text-sky-800'
                        : 'bg-emerald-100 text-emerald-800'
                    }`}
                  >
                    {status}
                  </span>
                </div>

                <p className="text-xs text-[#354e6b] leading-relaxed mt-2 min-h-[38px]">
                  {details}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-[#edf4fa] flex items-center justify-between text-xs text-[#5d768f]">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-[#0e1824]">
                    Penalty: {(severity * 100).toFixed(0)}%
                  </span>
                  <div className="w-16 h-1.5 rounded-full bg-[#e8f1f8] overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        severity > 0.5 ? 'bg-amber-500' : 'bg-emerald-500'
                      }`}
                      style={{ width: `${Math.min(severity * 100, 100)}%` }}
                    />
                  </div>
                </div>

                <span>
                  {evidenceCount} {evidenceCount === 1 ? 'evidence item' : 'evidence items'}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Active Diagnostic Episodes */}
      {episodes && episodes.length > 0 && (
        <div className="mt-10">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-[11px] font-bold tracking-[0.18em] uppercase text-[#5d768f]">
              ACTIVE DIAGNOSTIC EPISODES ({episodes.length})
            </span>
          </div>

          <div className="space-y-3">
            {episodes.map((ep) => (
              <div
                key={ep.episode_id}
                className="bg-white rounded-2xl p-5 border border-[#d8e6f2] shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="flex items-start gap-4">
                  <div className="w-9 h-9 rounded-xl bg-amber-50 border border-amber-200 text-amber-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-bold tracking-wider font-mono text-amber-800 bg-amber-100/60 px-2 py-0.5 rounded">
                        {ep.category}
                      </span>
                      <span className="text-xs text-[#5d768f]">
                        Episode: {ep.episode_id}
                      </span>
                    </div>
                    <h5 className="text-base font-editorial font-bold text-[#0e1824]">
                      {ep.primary_reason}
                    </h5>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-[#5d768f]">
                      {ep.hypothesis_codes.map((code) => (
                        <span key={code} className="bg-[#eff5fb] px-2 py-0.5 rounded text-[#2b4c6f] font-mono text-[11px]">
                          Hypothesis: {code}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="text-left md:text-right flex-shrink-0 text-xs text-[#5d768f]">
                  <div className="font-semibold text-[#0e1824]">
                    Severity: {(ep.severity_score * 100).toFixed(0)}%
                  </div>
                  <div className="text-[11px] mt-0.5">
                    First seen: {new Date(ep.start_time_utc).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};
