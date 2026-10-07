import React, { useState } from 'react';
import { Box, RotateCw, ZoomIn, Sparkles } from 'lucide-react';

import { TwinState } from '../../types/contracts';

interface Transformer3DViewProps {
  twinState: TwinState | null;
}

export const Transformer3DView: React.FC<Transformer3DViewProps> = ({ twinState }) => {
  const [activePin, setActivePin] = useState<string | null>('hotspot');

  const topOilObs = twinState?.current_observations?.top_oil_temperature?.value ?? 74.8;
  const currentL1 = twinState?.current_observations?.current_l1?.value ?? 115.4;

  const pins = [
    {
      id: 'hotspot',
      label: 'Winding Hot-Spot',
      coords: 'Core Midpoint (Layer 4)',
      value: 'UNAVAILABLE (Gated)',
      desc: 'C4 hot-spot estimation gated: no qualified loss-of-life or winding gradient model.',
      color: 'bg-slate-400',
    },
    {
      id: 'topoil',
      label: 'Top-Oil Pocket',
      coords: 'Tank Top Reservoir',
      value: `${topOilObs} °C`,
      desc: 'PT100 probe well measuring insulating oil before entering radiator headers.',
      color: 'bg-amber-500',
    },
    {
      id: 'bushings',
      label: 'HV Bushings',
      coords: 'Phase L1, L2, L3 Top Cover',
      value: `${currentL1} A Load`,
      desc: 'Porcelain condenser bushings interfacing external primary grid feeders.',
      color: 'bg-[#0284c7]',
    },
    {
      id: 'radiator',
      label: 'Cooling Radiator Fins',
      coords: 'Flank Assembly (ONAN)',
      value: 'Passive Circulation',
      desc: 'Natural oil-natural air convection fins dissipating transformer core and copper losses.',
      color: 'bg-emerald-500',
    },
  ];

  return (
    <div className="space-y-8">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between pb-4 border-b border-[#d8e6f2] gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-[#5d768f]">
              PHASE 8.4 (P3 STRETCH) 3D SPATIAL DIGITAL TWIN
            </span>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-[#e8f1f8] text-[#1c3c5c]">
              Three.js / React Three Fiber Ready
            </span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-[#0e1824] tracking-tight">
            3D Transformer Spatial Model.
          </h2>
          <p className="text-xs sm:text-sm text-[#5d768f] font-light mt-0.5">
            Reserved 3D container canvas for Three.js transformer model mesh with spatial telemetry pins.
          </p>
        </div>

        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white border border-[#d2e2ef] text-xs font-semibold text-[#1c3c5c] shadow-sm">
          <Sparkles className="w-3.5 h-3.5 text-[#0284c7]" />
          <span>Reserved for Your 3D Model</span>
        </div>
      </div>

      {/* Main 3D Model Canvas Workspace */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-card border border-[#d8e6f2] relative">
        <div className="flex flex-col md:flex-row items-stretch gap-6">
          {/* Main 3D Viewport Box */}
          <div className="flex-1 min-h-[420px] rounded-2xl bg-gradient-to-b from-[#f8fbfe] to-[#eaf2f9] border border-[#d2e2ef] relative flex flex-col items-center justify-center p-8 overflow-hidden">
            {/* Technical Blueprint Grid Pattern */}
            <div
              className="absolute inset-0 opacity-[0.05] pointer-events-none"
              style={{
                backgroundImage: 'radial-gradient(#0e1824 1px, transparent 1px)',
                backgroundSize: '20px 20px',
              }}
            />

            {/* Viewport Control Badges */}
            <div className="absolute top-4 left-4 flex items-center gap-2">
              <span className="bg-white/90 backdrop-blur-sm px-3 py-1 rounded-full text-[11px] font-mono font-semibold text-[#1c3c5c] border border-[#d2e2ef] shadow-sm flex items-center gap-1.5">
                <Box className="w-3 h-3 text-[#0284c7]" />
                Three.js Viewport: 1920 x 1080
              </span>
            </div>

            <div className="absolute top-4 right-4 flex items-center gap-1.5 bg-white/90 backdrop-blur-sm p-1 rounded-xl border border-[#d2e2ef] shadow-sm text-[#5d768f]">
              <button title="Rotate View" className="p-1.5 hover:text-[#0e1824] hover:bg-[#eff5fb] rounded-lg transition-colors">
                <RotateCw className="w-3.5 h-3.5" />
              </button>
              <button title="Zoom View" className="p-1.5 hover:text-[#0e1824] hover:bg-[#eff5fb] rounded-lg transition-colors">
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Transformer Schematic Silhouette Placeholder */}
            <div className="relative z-10 flex flex-col items-center text-center max-w-md">
              <div className="w-20 h-20 rounded-3xl bg-white border border-[#cbe0f1] shadow-card flex items-center justify-center text-[#0284c7] mb-4">
                <Box className="w-10 h-10 stroke-[1.5]" />
              </div>

              <h4 className="font-editorial text-2xl font-bold text-[#0e1824]">
                3D Transformer Mesh Container
              </h4>

              <p className="text-xs text-[#5d768f] mt-2 leading-relaxed">
                This space is completely reserved for your 3D transformer model (e.g., using <code className="bg-white px-1.5 py-0.5 rounded border border-[#d8e6f2]">@react-three/fiber</code> or <code className="bg-white px-1.5 py-0.5 rounded border border-[#d8e6f2]">three</code>).
                Telemetry inputs and component pins are ready to attach to 3D object vertices!
              </p>

              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {pins.map((pin) => (
                  <button
                    key={pin.id}
                    onClick={() => setActivePin(pin.id)}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all flex items-center gap-1.5 ${
                      activePin === pin.id
                        ? 'bg-[#0e1824] text-white border-[#0e1824] shadow-sm'
                        : 'bg-white text-[#354e6b] border-[#d2e2ef] hover:bg-[#eff5fb]'
                    }`}
                  >
                    <span className={`w-2 h-2 rounded-full ${pin.color}`}></span>
                    {pin.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Bottom Status Ticker */}
            <div className="absolute bottom-4 inset-x-4 flex items-center justify-between text-[11px] font-mono text-[#5d768f] bg-white/80 backdrop-blur-sm px-4 py-2 rounded-xl border border-[#d2e2ef]">
              <span>Camera: OrbitControls (Target: Core Center)</span>
              <span>Renderer: WebGL / R3F Canvas Ready</span>
            </div>
          </div>

          {/* Right: Component Telemetry Inspector Drawer */}
          <div className="w-full md:w-80 bg-[#f8fbfe] rounded-2xl p-5 border border-[#d2e2ef] flex flex-col justify-between">
            <div>
              <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#5d768f] block mb-2">
                COMPONENT INSPECTOR
              </span>

              {pins.map((pin) => {
                const isSelected = activePin === pin.id;
                return (
                  <div
                    key={pin.id}
                    onClick={() => setActivePin(pin.id)}
                    className={`p-3 rounded-xl border mb-2.5 cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-white border-[#0284c7] shadow-sm'
                        : 'bg-white/60 border-[#e2edf6] hover:bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-[#0e1824] flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${pin.color}`}></span>
                        {pin.label}
                      </span>
                      <span className="text-xs font-mono font-bold text-[#0284c7]">
                        {pin.value}
                      </span>
                    </div>
                    <p className="text-[11px] text-[#5d768f] leading-snug">
                      {pin.desc}
                    </p>
                  </div>
                );
              })}
            </div>

            <div className="pt-3 border-t border-[#d8e6f2] text-center">
              <span className="text-[11px] text-[#5d768f]">
                Integrated with <strong>TwinState</strong> observations.
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
