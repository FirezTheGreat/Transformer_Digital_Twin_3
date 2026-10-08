import React, { useState } from 'react';
import {
  Box,
  ArrowRight,
  AlertTriangle,
  Info,
  CheckCircle2,
  HelpCircle,
} from 'lucide-react';

import { TwinState, OTHIBundle } from '../../types/contracts';

interface Transformer3DViewProps {
  twinState: TwinState | null;
  health?: OTHIBundle | null;
  onNavigateTab?: (tab: string) => void;
}

type ComponentId = 'tank' | 'l1' | 'l2' | 'l3' | 'neutral' | 'cooling' | 'oil';

interface ComponentMeta {
  id: ComponentId;
  name: string;
  category: string;
  badgeLabel: string;
  status: 'NORMAL' | 'WATCH' | 'WARNING' | 'CRITICAL' | 'UNAVAILABLE';
  targetTab: string;
  targetTabLabel: string;
  description: string;
  metrics: {
    label: string;
    value: string;
    sublabel?: string;
    isUnavailable?: boolean;
    badge?: string;
  }[];
}

export const Transformer3DView: React.FC<Transformer3DViewProps> = ({
  twinState,
  health,
  onNavigateTab,
}) => {
  const [selectedId, setSelectedId] = useState<ComponentId>('tank');

  // Authoritative Telemetry Extraction
  const obs = twinState?.current_observations;
  const topOilObs = obs?.top_oil_temperature?.value;
  const topOilExp = twinState?.thermal_latent?.top_oil_expected_degc;
  const topOilRes =
    typeof topOilObs === 'number' && typeof topOilExp === 'number'
      ? (topOilObs - topOilExp).toFixed(1)
      : null;

  const currentL1 = obs?.current_l1?.value ?? obs?.current_i1?.value;
  const voltageL1 = obs?.voltage_l1_n?.value ?? obs?.voltage_v1?.value;
  const currentL2 = obs?.current_l2?.value ?? obs?.current_i2?.value;
  const voltageL2 = obs?.voltage_l2_n?.value ?? obs?.voltage_v2?.value;
  const currentL3 = obs?.current_l3?.value ?? obs?.current_i3?.value;
  const voltageL3 = obs?.voltage_l3_n?.value ?? obs?.voltage_v3?.value;
  const neutralCurrent = obs?.neutral_current?.value ?? obs?.current_in?.value;
  const phaseImbalancePct = twinState?.derived_electrical?.current_magnitude_imbalance_pct;

  const thermalStatus = health?.domains?.thermal?.status ?? 'WATCH';
  const phaseStatus = health?.domains?.phase_neutral?.status ?? 'NORMAL';
  const oilStatus = health?.domains?.oil_protection?.status ?? 'NORMAL';

  const timestamp = twinState?.state_time_utc
    ? new Date(twinState.state_time_utc).toUTCString()
    : 'Live Synchronized';

  // Component Definitions with Strict Data Honesty
  const components: Record<ComponentId, ComponentMeta> = {
    tank: {
      id: 'tank',
      name: 'Main Tank & Thermal Core',
      category: 'Thermal & Structural Assembly',
      badgeLabel: 'TANK / CORE',
      status: thermalStatus,
      targetTab: 'twin-analysis',
      targetTabLabel: 'View thermal evidence →',
      description:
        'Sealed welded steel enclosure containing high-permeability silicon steel core laminations and copper windings immersed in mineral insulating oil.',
      metrics: [
        {
          label: 'Observed Top-Oil Temp',
          value: typeof topOilObs === 'number' ? `${topOilObs.toFixed(1)} °C` : 'Unavailable',
          sublabel: 'PT100 probe well measurement',
          isUnavailable: typeof topOilObs !== 'number',
        },
        {
          label: 'Expected Top-Oil Temp',
          value: typeof topOilExp === 'number' ? `${topOilExp.toFixed(1)} °C` : 'Unavailable',
          sublabel: 'Calibrated first-order thermal ODE',
          isUnavailable: typeof topOilExp !== 'number',
        },
        {
          label: 'Thermal Residual (ΔT)',
          value: topOilRes !== null ? `${Number(topOilRes) >= 0 ? '+' : ''}${topOilRes} °C` : 'Unavailable',
          sublabel: 'Deviation from expected baseline',
          isUnavailable: topOilRes === null,
        },
        {
          label: 'Winding Hot-Spot (WTI)',
          value: 'Unavailable (C4 Gated)',
          sublabel: 'No direct optical fiber or qualified gradient model',
          isUnavailable: true,
        },
      ],
    },
    l1: {
      id: 'l1',
      name: 'Phase L1 HV Bushing',
      category: 'Electrical Terminal',
      badgeLabel: 'PHASE L1',
      status: phaseStatus,
      targetTab: 'telemetry',
      targetTabLabel: 'View electrical telemetry →',
      description:
        'Outdoor porcelain condenser bushing conducting Phase 1 primary grid current through the grounded tank top cover.',
      metrics: [
        {
          label: 'Phase L1 Current',
          value: typeof currentL1 === 'number' ? `${currentL1.toFixed(1)} A` : 'Unavailable',
          sublabel: 'Measured line current',
          isUnavailable: typeof currentL1 !== 'number',
        },
        {
          label: 'Phase L1-N Voltage',
          value: typeof voltageL1 === 'number' ? `${voltageL1.toFixed(1)} V` : 'Unavailable',
          sublabel: 'Phase-to-neutral voltage',
          isUnavailable: typeof voltageL1 !== 'number',
        },
        {
          label: 'Phase Imbalance',
          value: typeof phaseImbalancePct === 'number' ? `${phaseImbalancePct.toFixed(1)} %` : 'Unavailable',
          sublabel: 'NEMA current magnitude imbalance',
          isUnavailable: typeof phaseImbalancePct !== 'number',
        },
      ],
    },
    l2: {
      id: 'l2',
      name: 'Phase L2 HV Bushing',
      category: 'Electrical Terminal',
      badgeLabel: 'PHASE L2',
      status: phaseStatus,
      targetTab: 'telemetry',
      targetTabLabel: 'View electrical telemetry →',
      description:
        'Outdoor porcelain condenser bushing conducting Phase 2 primary grid current through the grounded tank top cover.',
      metrics: [
        {
          label: 'Phase L2 Current',
          value: typeof currentL2 === 'number' ? `${currentL2.toFixed(1)} A` : 'Unavailable',
          sublabel: 'Measured line current',
          isUnavailable: typeof currentL2 !== 'number',
        },
        {
          label: 'Phase L2-N Voltage',
          value: typeof voltageL2 === 'number' ? `${voltageL2.toFixed(1)} V` : 'Unavailable',
          sublabel: 'Phase-to-neutral voltage',
          isUnavailable: typeof voltageL2 !== 'number',
        },
        {
          label: 'Phase Imbalance',
          value: typeof phaseImbalancePct === 'number' ? `${phaseImbalancePct.toFixed(1)} %` : 'Unavailable',
          sublabel: 'NEMA current magnitude imbalance',
          isUnavailable: typeof phaseImbalancePct !== 'number',
        },
      ],
    },
    l3: {
      id: 'l3',
      name: 'Phase L3 HV Bushing',
      category: 'Electrical Terminal',
      badgeLabel: 'PHASE L3',
      status: phaseStatus,
      targetTab: 'telemetry',
      targetTabLabel: 'View electrical telemetry →',
      description:
        'Outdoor porcelain condenser bushing conducting Phase 3 primary grid current through the grounded tank top cover.',
      metrics: [
        {
          label: 'Phase L3 Current',
          value: typeof currentL3 === 'number' ? `${currentL3.toFixed(1)} A` : 'Unavailable',
          sublabel: 'Measured line current',
          isUnavailable: typeof currentL3 !== 'number',
        },
        {
          label: 'Phase L3-N Voltage',
          value: typeof voltageL3 === 'number' ? `${voltageL3.toFixed(1)} V` : 'Unavailable',
          sublabel: 'Phase-to-neutral voltage',
          isUnavailable: typeof voltageL3 !== 'number',
        },
        {
          label: 'Phase Imbalance',
          value: typeof phaseImbalancePct === 'number' ? `${phaseImbalancePct.toFixed(1)} %` : 'Unavailable',
          sublabel: 'NEMA current magnitude imbalance',
          isUnavailable: typeof phaseImbalancePct !== 'number',
        },
      ],
    },
    neutral: {
      id: 'neutral',
      name: 'Neutral Terminal & Return',
      category: 'Grounding & Return',
      badgeLabel: 'NEUTRAL (N)',
      status: phaseStatus,
      targetTab: 'telemetry',
      targetTabLabel: 'View electrical telemetry →',
      description:
        'Star-point neutral grounding terminal facilitating return current path and unbalance circulation to substation earth grid.',
      metrics: [
        {
          label: 'Neutral Return Current',
          value: typeof neutralCurrent === 'number' ? `${neutralCurrent.toFixed(1)} A` : 'Unavailable',
          sublabel: 'CT measured neutral conductor current',
          isUnavailable: typeof neutralCurrent !== 'number',
        },
        {
          label: 'Ground Potential',
          value: '0.0 V (Reference)',
          sublabel: 'Substation ground mat reference',
          isUnavailable: false,
        },
      ],
    },
    cooling: {
      id: 'cooling',
      name: 'Cooling Radiator Assembly',
      category: 'Dissipation System',
      badgeLabel: 'RADIATOR / ONAN',
      status: 'NORMAL',
      targetTab: 'model-card',
      targetTabLabel: 'View asset specifications →',
      description:
        'Flank-mounted pressed steel cooling fins operating in natural oil-natural air convection (ONAN) mode to dissipate core and copper losses.',
      metrics: [
        {
          label: 'Cooling Class',
          value: 'ONAN (Passive)',
          sublabel: 'Descriptive nameplate classification',
          isUnavailable: false,
        },
        {
          label: 'Dynamic Cooling State',
          value: 'Cooling state unavailable',
          sublabel: 'No telemetry installed (natural thermosiphon)',
          isUnavailable: true,
        },
        {
          label: 'Forced Fan / Pump Status',
          value: 'Not equipped (ONAN design)',
          sublabel: 'Passive convection dissipation only',
          isUnavailable: false,
        },
      ],
    },
    oil: {
      id: 'oil',
      name: 'Conservator Tank & Oil Expansion',
      category: 'Dielectric & Expansion System',
      badgeLabel: 'OIL / CONSERVATOR',
      status: oilStatus,
      targetTab: 'telemetry',
      targetTabLabel: 'View protection telemetry →',
      description:
        'Elevated cylindrical expansion drum accommodating oil volumetric expansion during thermal cycling, fitted with dehydrating silica gel breather.',
      metrics: [
        {
          label: 'Oil Level Gauge (MOG)',
          value: 'Nominal (Descriptive)',
          sublabel: 'Mechanical sight glass level indicator',
          isUnavailable: false,
        },
        {
          label: 'Buchholz / Gas Relay',
          value: 'Unavailable',
          sublabel: 'No digital gas accumulation telemetry',
          isUnavailable: true,
        },
        {
          label: 'Moisture / Breather State',
          value: 'Descriptive (Silica Breather)',
          sublabel: 'Manual periodic maintenance inspection',
          isUnavailable: false,
        },
      ],
    },
  };

  const currentComp: ComponentMeta = components[selectedId];

  // Helper status color mapping
  const getStatusBadge = (status: ComponentMeta['status']) => {
    switch (status) {
      case 'NORMAL':
        return {
          bg: 'bg-emerald-50 text-emerald-800 border-emerald-200',
          dot: 'bg-emerald-500',
          icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />,
          label: 'NORMAL',
        };
      case 'WATCH':
        return {
          bg: 'bg-amber-50 text-amber-800 border-amber-200',
          dot: 'bg-amber-500',
          icon: <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />,
          label: 'WATCH',
        };
      case 'WARNING':
        return {
          bg: 'bg-orange-50 text-orange-800 border-orange-200',
          dot: 'bg-orange-500',
          icon: <AlertTriangle className="w-3.5 h-3.5 text-orange-600" />,
          label: 'WARNING',
        };
      case 'CRITICAL':
        return {
          bg: 'bg-rose-50 text-rose-800 border-rose-200',
          dot: 'bg-rose-500',
          icon: <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />,
          label: 'CRITICAL',
        };
      case 'UNAVAILABLE':
      default:
        return {
          bg: 'bg-slate-100 text-slate-700 border-slate-200',
          dot: 'bg-slate-400',
          icon: <HelpCircle className="w-3.5 h-3.5 text-slate-500" />,
          label: 'UNAVAILABLE',
        };
    }
  };

  const statusBadge = getStatusBadge(currentComp.status);

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-subtle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                Component Navigator
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                2.5D Schematic & Telemetry Linkage
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
              Physical Component State Explorer
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Interactive physical component mapping linked directly to active telemetry vectors and diagnostic domains.
            </p>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap items-center gap-3 bg-slate-50 px-3 py-1.5 rounded border border-slate-200 text-xs self-start sm:self-auto">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
              Status:
            </span>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-slate-700 text-[11px]">Normal</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              <span className="text-slate-700 text-[11px]">Watch</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-orange-500" />
              <span className="text-slate-700 text-[11px]">Warning</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              <span className="text-slate-700 text-[11px]">Critical</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full border border-slate-400 bg-slate-200" />
              <span className="text-slate-500 text-[11px]">Unavailable</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        {/* Left/Center Column: Transformer Visualizer Canvas (8 cols) */}
        <div className="lg:col-span-8 bg-white rounded-lg p-5 shadow-subtle border border-slate-200 flex flex-col justify-between">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
            <div className="flex items-center gap-2">
              <Box className="w-4 h-4 text-sky-600" />
              <span className="text-xs font-mono font-bold text-slate-800">
                2.5D Isometric Component Layout
              </span>
            </div>
            <span className="text-[11px] font-mono text-slate-400">
              {timestamp}
            </span>
          </div>

          {/* Isometric SVG Transformer Visualizer */}
          <div className="relative w-full aspect-[16/10] min-h-[360px] bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-center p-4 overflow-hidden select-none">
            {/* Engineering Blueprint Grid */}
            <svg
              className="absolute inset-0 w-full h-full opacity-10 pointer-events-none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <defs>
                <pattern
                  id="tech-grid"
                  width="24"
                  height="24"
                  patternUnits="userSpaceOnUse"
                >
                  <path
                    d="M 24 0 L 0 0 0 24"
                    fill="none"
                    stroke="#0f172a"
                    strokeWidth="0.75"
                  />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#tech-grid)" />
            </svg>

            {/* Stylized Transformer Component SVG Model */}
            <svg
              viewBox="0 0 800 500"
              className="w-full h-full max-h-[460px] relative z-10 filter drop-shadow-md"
            >
              <defs>
                {/* Tank Gradients */}
                <linearGradient id="tankBodyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#e2ecf5" />
                  <stop offset="60%" stopColor="#cbdff0" />
                  <stop offset="100%" stopColor="#b4cfe6" />
                </linearGradient>

                <linearGradient id="tankTopGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#f0f6fc" />
                  <stop offset="100%" stopColor="#dbe8f5" />
                </linearGradient>

                {/* Radiator Fin Gradients */}
                <linearGradient id="radFinGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#bdd4e7" />
                  <stop offset="50%" stopColor="#9cbdd6" />
                  <stop offset="100%" stopColor="#82a6c2" />
                </linearGradient>

                {/* Conservator Gradients */}
                <linearGradient id="conservatorGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#f4f9fd" />
                  <stop offset="40%" stopColor="#d2e4f3" />
                  <stop offset="100%" stopColor="#a3c4df" />
                </linearGradient>

                {/* Porcelain Bushing Gradient */}
                <linearGradient id="porcelainGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#8c5837" />
                  <stop offset="50%" stopColor="#d48c5b" />
                  <stop offset="100%" stopColor="#6e4024" />
                </linearGradient>

                {/* Copper Bushing Terminal */}
                <linearGradient id="copperGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#e5a952" />
                  <stop offset="50%" stopColor="#ffd88b" />
                  <stop offset="100%" stopColor="#c78426" />
                </linearGradient>
              </defs>

              {/* 1. Base Mounting Skid / Foundation Rails */}
              <g id="base-skid">
                <rect x="230" y="415" width="340" height="24" rx="4" fill="#354e6b" stroke="#1c3c5c" strokeWidth="2" />
                <rect x="210" y="435" width="380" height="14" rx="3" fill="#1c3c5c" />
                {/* Foundation Anchor Bolts */}
                <circle cx="245" cy="442" r="3" fill="#8ca5be" />
                <circle cx="555" cy="442" r="3" fill="#8ca5be" />
              </g>

              {/* 2. Cooling Radiator Fins Assembly (Flank Mounts) */}
              <g
                id="cooling-radiator"
                onClick={() => setSelectedId('cooling')}
                className="cursor-pointer transition-all duration-200"
              >
                {/* Left Radiator Assembly */}
                <rect x="150" y="240" width="105" height="155" rx="6" fill="url(#radFinGrad)" stroke={selectedId === 'cooling' ? '#0284c7' : '#5d768f'} strokeWidth={selectedId === 'cooling' ? 3 : 1.5} />
                {/* Header Pipes */}
                <path d="M 200 240 L 255 240 M 200 395 L 255 395" stroke="#354e6b" strokeWidth="10" strokeLinecap="round" />
                {/* Individual Fin Channels */}
                {[0, 1, 2, 3, 4, 5, 6].map((i) => (
                  <rect
                    key={`l-fin-${i}`}
                    x={160 + i * 13}
                    y="248"
                    width="7"
                    height="138"
                    rx="2"
                    fill="#edf5fb"
                    stroke="#6d8ba6"
                    strokeWidth="1"
                  />
                ))}

                {/* Right Radiator Assembly */}
                <rect x="545" y="240" width="105" height="155" rx="6" fill="url(#radFinGrad)" stroke={selectedId === 'cooling' ? '#0284c7' : '#5d768f'} strokeWidth={selectedId === 'cooling' ? 3 : 1.5} />
                {/* Header Pipes */}
                <path d="M 545 240 L 600 240 M 545 395 L 600 395" stroke="#354e6b" strokeWidth="10" strokeLinecap="round" />
                {/* Individual Fin Channels */}
                {[0, 1, 2, 3, 4, 5, 6].map((i) => (
                  <rect
                    key={`r-fin-${i}`}
                    x={555 + i * 13}
                    y="248"
                    width="7"
                    height="138"
                    rx="2"
                    fill="#edf5fb"
                    stroke="#6d8ba6"
                    strokeWidth="1"
                  />
                ))}

                {/* Selected Indicator Label */}
                {selectedId === 'cooling' && (
                  <rect x="150" y="240" width="105" height="155" rx="6" fill="#0284c7" fillOpacity="0.12" />
                )}
              </g>

              {/* 3. Main Tank Body & Internal Core Outline */}
              <g
                id="main-tank"
                onClick={() => setSelectedId('tank')}
                className="cursor-pointer transition-all duration-200"
              >
                {/* Tank Body Rect */}
                <rect
                  x="250"
                  y="200"
                  width="300"
                  height="215"
                  rx="10"
                  fill="url(#tankBodyGrad)"
                  stroke={selectedId === 'tank' ? '#0284c7' : '#354e6b'}
                  strokeWidth={selectedId === 'tank' ? 3.5 : 2}
                />

                {/* Tank Cover Flange */}
                <rect
                  x="240"
                  y="190"
                  width="320"
                  height="16"
                  rx="4"
                  fill="url(#tankTopGrad)"
                  stroke={selectedId === 'tank' ? '#0284c7' : '#354e6b'}
                  strokeWidth={selectedId === 'tank' ? 3 : 1.5}
                />

                {/* Tank Stiffener Ribs & Oil Level Window */}
                <line x1="250" y1="270" x2="550" y2="270" stroke="#9bbad3" strokeWidth="2" strokeDasharray="6 4" />
                <line x1="250" y1="345" x2="550" y2="345" stroke="#9bbad3" strokeWidth="2" strokeDasharray="6 4" />

                {/* Cutaway/Indication: Active Core & Copper Winding Zone */}
                <g opacity="0.85">
                  <rect x="285" y="225" width="230" height="165" rx="6" fill="#ffffff" fillOpacity="0.4" stroke="#799db9" strokeWidth="1.5" strokeDasharray="4 3" />
                  
                  {/* Core Limbs (3-Phase Magnetic Circuit) */}
                  <rect x="305" y="245" width="46" height="125" rx="4" fill="#60829f" stroke="#354e6b" strokeWidth="1" />
                  <rect x="377" y="245" width="46" height="125" rx="4" fill="#60829f" stroke="#354e6b" strokeWidth="1" />
                  <rect x="449" y="245" width="46" height="125" rx="4" fill="#60829f" stroke="#354e6b" strokeWidth="1" />

                  {/* Copper Windings Over Limbs */}
                  <rect x="299" y="260" width="58" height="95" rx="4" fill="#d97706" fillOpacity="0.35" stroke="#b45309" strokeWidth="1.5" />
                  <rect x="371" y="260" width="58" height="95" rx="4" fill="#d97706" fillOpacity="0.35" stroke="#b45309" strokeWidth="1.5" />
                  <rect x="443" y="260" width="58" height="95" rx="4" fill="#d97706" fillOpacity="0.35" stroke="#b45309" strokeWidth="1.5" />

                  {/* Core Midpoint / Hot-Spot Probe Pocket Lineage */}
                  <circle cx="400" cy="215" r="5" fill="#f59e0b" stroke="#ffffff" strokeWidth="1.5" />
                  <text x="400" y="238" textAnchor="middle" fontSize="10" fontWeight="bold" fill="#0e1824" fontFamily="monospace">
                    {typeof topOilObs === 'number' ? `${topOilObs.toFixed(1)}°C` : 'TOP OIL'}
                  </text>
                </g>

                {/* Tank Label Plaque */}
                <rect x="350" y="375" width="100" height="24" rx="3" fill="#1c3c5c" stroke="#d2e2ef" strokeWidth="1" />
                <text x="400" y="391" textAnchor="middle" fontSize="9" fontWeight="bold" fill="#ffffff" fontFamily="monospace" letterSpacing="1">
                  MAIN OIL TANK
                </text>
              </g>

              {/* 4. Conservator Tank & Breather Pipe */}
              <g
                id="conservator-tank"
                onClick={() => setSelectedId('oil')}
                className="cursor-pointer transition-all duration-200"
              >
                {/* Connecting Standpipe & Buchholz Location */}
                <path
                  d="M 330 190 L 330 125 L 375 125"
                  fill="none"
                  stroke={selectedId === 'oil' ? '#0284c7' : '#354e6b'}
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />

                {/* Conservator Drum Body */}
                <rect
                  x="360"
                  y="85"
                  width="180"
                  height="65"
                  rx="24"
                  fill="url(#conservatorGrad)"
                  stroke={selectedId === 'oil' ? '#0284c7' : '#354e6b'}
                  strokeWidth={selectedId === 'oil' ? 3 : 1.5}
                />

                {/* Magnetic Oil Gauge (MOG) Sight Glass */}
                <circle cx="505" cy="117" r="14" fill="#ffffff" stroke="#1c3c5c" strokeWidth="2" />
                <line x1="505" y1="117" x2="513" y2="110" stroke="#0284c7" strokeWidth="2.5" strokeLinecap="round" />
                <circle cx="505" cy="117" r="3" fill="#0e1824" />

                {/* Conservator Support Bracket */}
                <line x1="510" y1="150" x2="510" y2="190" stroke="#354e6b" strokeWidth="6" strokeLinecap="round" />

                <text x="435" y="122" textAnchor="middle" fontSize="10" fontWeight="bold" fill="#1c3c5c" fontFamily="monospace">
                  CONSERVATOR
                </text>
              </g>

              {/* 5. HV Condenser Bushings (L1, L2, L3) & Neutral (N) */}

              {/* Phase L1 Bushing */}
              <g
                id="bushing-l1"
                onClick={() => setSelectedId('l1')}
                className="cursor-pointer transition-all duration-200"
              >
                {/* Base Turret */}
                <rect x="290" y="175" width="28" height="16" rx="2" fill="#9bbad3" stroke="#354e6b" strokeWidth="1" />
                {/* Porcelain Sheds */}
                <polygon points="304,110 286,130 322,130" fill="url(#porcelainGrad)" stroke="#4a2612" strokeWidth="1" />
                <polygon points="304,125 288,145 320,145" fill="url(#porcelainGrad)" stroke="#4a2612" strokeWidth="1" />
                <polygon points="304,140 290,160 318,160" fill="url(#porcelainGrad)" stroke="#4a2612" strokeWidth="1" />
                <polygon points="304,155 292,175 316,175" fill="url(#porcelainGrad)" stroke="#4a2612" strokeWidth="1" />
                {/* Copper Stem & Terminal Lug */}
                <rect x="301" y="90" width="6" height="25" fill="url(#copperGrad)" stroke="#78350f" strokeWidth="0.75" />
                <circle cx="304" cy="88" r="5" fill="#f59e0b" stroke="#78350f" strokeWidth="1" />
                {/* Selection Ring */}
                {selectedId === 'l1' && (
                  <circle cx="304" cy="88" r="12" fill="none" stroke="#0284c7" strokeWidth="2.5" strokeDasharray="3 3" />
                )}
                {/* Label Pin */}
                <rect x="289" y="60" width="30" height="18" rx="4" fill={selectedId === 'l1' ? '#0284c7' : '#1c3c5c'} />
                <text x="304" y="73" textAnchor="middle" fontSize="11" fontWeight="bold" fill="#ffffff" fontFamily="monospace">
                  L1
                </text>
              </g>

              {/* Phase L2 Bushing */}
              <g
                id="bushing-l2"
                onClick={() => setSelectedId('l2')}
                className="cursor-pointer transition-all duration-200"
              >
                {/* Base Turret */}
                <rect x="386" y="175" width="28" height="16" rx="2" fill="#9bbad3" stroke="#354e6b" strokeWidth="1" />
                {/* Porcelain Sheds */}
                <polygon points="400,110 382,130 418,130" fill="url(#porcelainGrad)" stroke="#4a2612" strokeWidth="1" />
                <polygon points="400,125 384,145 416,145" fill="url(#porcelainGrad)" stroke="#4a2612" strokeWidth="1" />
                <polygon points="400,140 386,160 414,160" fill="url(#porcelainGrad)" stroke="#4a2612" strokeWidth="1" />
                <polygon points="400,155 388,175 412,175" fill="url(#porcelainGrad)" stroke="#4a2612" strokeWidth="1" />
                {/* Copper Stem & Terminal Lug */}
                <rect x="397" y="90" width="6" height="25" fill="url(#copperGrad)" stroke="#78350f" strokeWidth="0.75" />
                <circle cx="400" cy="88" r="5" fill="#f59e0b" stroke="#78350f" strokeWidth="1" />
                {/* Selection Ring */}
                {selectedId === 'l2' && (
                  <circle cx="400" cy="88" r="12" fill="none" stroke="#0284c7" strokeWidth="2.5" strokeDasharray="3 3" />
                )}
                {/* Label Pin */}
                <rect x="385" y="60" width="30" height="18" rx="4" fill={selectedId === 'l2' ? '#0284c7' : '#1c3c5c'} />
                <text x="400" y="73" textAnchor="middle" fontSize="11" fontWeight="bold" fill="#ffffff" fontFamily="monospace">
                  L2
                </text>
              </g>

              {/* Phase L3 Bushing */}
              <g
                id="bushing-l3"
                onClick={() => setSelectedId('l3')}
                className="cursor-pointer transition-all duration-200"
              >
                {/* Base Turret */}
                <rect x="482" y="175" width="28" height="16" rx="2" fill="#9bbad3" stroke="#354e6b" strokeWidth="1" />
                {/* Porcelain Sheds */}
                <polygon points="496,110 478,130 514,130" fill="url(#porcelainGrad)" stroke="#4a2612" strokeWidth="1" />
                <polygon points="496,125 480,145 512,145" fill="url(#porcelainGrad)" stroke="#4a2612" strokeWidth="1" />
                <polygon points="496,140 482,160 510,160" fill="url(#porcelainGrad)" stroke="#4a2612" strokeWidth="1" />
                <polygon points="496,155 484,175 508,175" fill="url(#porcelainGrad)" stroke="#4a2612" strokeWidth="1" />
                {/* Copper Stem & Terminal Lug */}
                <rect x="493" y="90" width="6" height="25" fill="url(#copperGrad)" stroke="#78350f" strokeWidth="0.75" />
                <circle cx="496" cy="88" r="5" fill="#f59e0b" stroke="#78350f" strokeWidth="1" />
                {/* Selection Ring */}
                {selectedId === 'l3' && (
                  <circle cx="496" cy="88" r="12" fill="none" stroke="#0284c7" strokeWidth="2.5" strokeDasharray="3 3" />
                )}
                {/* Label Pin */}
                <rect x="481" y="60" width="30" height="18" rx="4" fill={selectedId === 'l3' ? '#0284c7' : '#1c3c5c'} />
                <text x="496" y="73" textAnchor="middle" fontSize="11" fontWeight="bold" fill="#ffffff" fontFamily="monospace">
                  L3
                </text>
              </g>

              {/* Neutral Bushing (N) */}
              <g
                id="bushing-neutral"
                onClick={() => setSelectedId('neutral')}
                className="cursor-pointer transition-all duration-200"
              >
                {/* Neutral Bushing (Smaller scale) */}
                <rect x="252" y="177" width="20" height="14" rx="2" fill="#9bbad3" stroke="#354e6b" strokeWidth="1" />
                <polygon points="262,130 250,148 274,148" fill="#52525b" stroke="#27272a" strokeWidth="1" />
                <polygon points="262,145 252,162 272,162" fill="#52525b" stroke="#27272a" strokeWidth="1" />
                <polygon points="262,160 254,177 270,177" fill="#52525b" stroke="#27272a" strokeWidth="1" />
                {/* Neutral Terminal Lug */}
                <rect x="260" y="115" width="4" height="18" fill="#e4e4e7" stroke="#3f3f46" strokeWidth="0.75" />
                <circle cx="262" cy="112" r="4" fill="#a1a1aa" stroke="#3f3f46" strokeWidth="1" />
                {/* Selection Ring */}
                {selectedId === 'neutral' && (
                  <circle cx="262" cy="112" r="10" fill="none" stroke="#0284c7" strokeWidth="2.5" strokeDasharray="3 3" />
                )}
                {/* Label Pin */}
                <rect x="250" y="85" width="24" height="18" rx="4" fill={selectedId === 'neutral' ? '#0284c7' : '#475569'} />
                <text x="262" y="98" textAnchor="middle" fontSize="10" fontWeight="bold" fill="#ffffff" fontFamily="monospace">
                  N
                </text>
              </g>
            </svg>

            {/* Interactive Component Click Tip */}
            <div className="absolute bottom-3 left-4 bg-white/90 backdrop-blur-sm px-3 py-1.5 rounded-xl border border-[#d2e2ef] shadow-sm text-[11px] text-[#5d768f] flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5 text-[#0284c7]" />
              <span>Click on any component or use the buttons below to inspect state</span>
            </div>
          </div>

          {/* Component Selection Quick Bar */}
          <div className="mt-4 pt-3 border-t border-[#eef5fa]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#5d768f] block mb-2">
              COMPONENTS
            </span>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(components) as ComponentId[]).map((id) => {
                const comp = components[id];
                const isSelected = selectedId === id;
                return (
                  <button
                    key={id}
                    onClick={() => setSelectedId(id)}
                    className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold border transition-all flex items-center gap-2 ${
                      isSelected
                        ? 'bg-[#0e1824] text-white border-[#0e1824] shadow-sm'
                        : 'bg-[#f8fbfe] text-[#354e6b] border-[#d2e2ef] hover:bg-white hover:border-[#b4cfe6]'
                    }`}
                  >
                    <span
                      className={`w-2 h-2 rounded-full ${
                        comp.status === 'NORMAL'
                          ? 'bg-emerald-500'
                          : comp.status === 'WATCH'
                          ? 'bg-amber-500'
                          : comp.status === 'WARNING'
                          ? 'bg-orange-500'
                          : comp.status === 'CRITICAL'
                          ? 'bg-rose-500'
                          : 'bg-slate-400'
                      }`}
                    />
                    {comp.badgeLabel}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Selected Component Engineering Inspector Panel (4 cols) */}
        <div className="lg:col-span-4 bg-white rounded-lg p-5 border border-slate-200 shadow-subtle flex flex-col justify-between">
          <div className="space-y-4">
            {/* Component Header & Status Banner */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
                  {currentComp.category}
                </span>
                <span
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold border ${statusBadge.bg}`}
                >
                  {statusBadge.icon}
                  <span>{statusBadge.label}</span>
                </span>
              </div>

              <h3 className="text-lg font-bold text-slate-900">
                {currentComp.name}
              </h3>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                {currentComp.description}
              </p>
            </div>

            {/* Metrics List */}
            <div className="space-y-2.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                State-Linked Telemetry
              </span>

              {currentComp.metrics.map((m, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded border text-xs ${
                    m.isUnavailable
                      ? 'bg-slate-50/50 border-slate-200'
                      : 'bg-slate-50 border-slate-200'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-slate-600 font-medium">
                      {m.label}
                    </span>
                    <span
                      className={`font-mono font-bold ${
                        m.isUnavailable
                          ? 'text-slate-400 italic text-[11px]'
                          : 'text-slate-900'
                      }`}
                    >
                      {m.value}
                    </span>
                  </div>
                  {m.sublabel && (
                    <span className="text-[10px] text-slate-400 block mt-0.5">
                      {m.sublabel}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Context Action Link (2D/3D Bridge) */}
          <div className="pt-4 mt-4 border-t border-slate-200 space-y-2">
            {onNavigateTab && (
              <button
                onClick={() => onNavigateTab(currentComp.targetTab)}
                className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded bg-slate-900 hover:bg-slate-800 text-xs font-semibold text-white transition-colors"
              >
                <span>{currentComp.targetTabLabel}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}

            <div className="text-center">
              <span className="text-[10px] text-slate-400 block">
                Telemetry synchronized from active FactBundle state vector.
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
