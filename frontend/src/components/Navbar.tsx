import React from 'react';
import { RefreshCw, Box } from 'lucide-react';

interface NavbarProps {
  isBackendHealthy: boolean;
  activeTab: string;
  onTabChange: (tab: string) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  isBackendHealthy,
  activeTab,
  onTabChange,
  onRefresh,
  isRefreshing,
}) => {
  const navItems = [
    { id: 'overview', label: 'Overview' },
    { id: 'twin-analysis', label: 'Twin Analysis' },
    { id: 'anomalies', label: 'Anomalies & CUSUM' },
    { id: 'maintenance', label: 'Maintenance' },
    { id: 'telemetry', label: 'Telemetry & Tiers' },
    { id: 'model-card', label: 'Model Card' },
    { id: 'twin-3d', label: '3D Twin', icon: <Box className="w-3.5 h-3.5" /> },
  ];

  return (
    <header className="sticky top-0 z-40 bg-[#eff5fb]/95 backdrop-blur-md border-b border-[#d8e6f2] transition-colors">
      <div className="max-w-7xl mx-auto px-6 h-18 py-3 flex items-center justify-between gap-6">
        {/* Brand: GridPulse with sleek modern electrical mark */}
        <div
          onClick={() => onTabChange('overview')}
          className="flex items-center gap-3.5 cursor-pointer group flex-shrink-0"
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#0b1320] via-[#16253b] to-[#0a111c] border border-slate-700/60 flex items-center justify-center text-white shadow-md shadow-sky-950/15 group-hover:scale-105 transition-all duration-200 relative overflow-hidden">
            {/* Subtle internal glow */}
            <div className="absolute inset-0 bg-gradient-to-tr from-sky-500/20 to-transparent pointer-events-none" />
            <svg
              viewBox="0 0 24 24"
              className="w-5 h-5 text-sky-400 fill-none stroke-current stroke-[2.2] stroke-linecap-round stroke-linejoin-round relative z-10 transition-transform group-hover:rotate-6"
            >
              <path d="M3 12h3.5l2.5-6 4 12 3-7.5 2 3.5h3" />
            </svg>
          </div>

          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="text-xl font-extrabold tracking-tight text-[#0e1824] font-sans leading-none">
                Grid<span className="text-[#0284c7]">Pulse</span>
              </span>
              <span className="text-[10px] tracking-wider uppercase font-bold px-2 py-0.5 rounded-full bg-sky-100 text-[#0369a1] border border-sky-200/60 leading-none">
                Live Twin
              </span>
            </div>
            <p className="text-[11px] font-medium text-[#627d98] tracking-wide mt-1 leading-none font-sans">
              Distribution Substation Intelligence
            </p>
          </div>
        </div>

        {/* Center Nav Links: Unified Segmented Dock */}
        <nav className="hidden lg:flex items-center bg-[#e2edf6]/80 p-1 rounded-full border border-[#cfdfed] shadow-inner">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`h-8 px-3.5 rounded-full text-xs font-semibold transition-all flex items-center gap-1.5 whitespace-nowrap ${
                  isActive
                    ? 'bg-white text-[#0e1824] shadow-sm'
                    : 'text-[#486581] hover:text-[#0e1824] hover:bg-white/60'
                }`}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Right Actions: Symmetrical, aligned cluster */}
        <div className="flex items-center gap-2.5 flex-shrink-0">
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            title="Refresh Digital Twin State"
            className="w-9 h-9 rounded-full bg-white hover:bg-[#e2edf6] text-[#486581] hover:text-[#0e1824] border border-[#cde0ee] shadow-sm flex items-center justify-center transition-all active:scale-95"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-[#0284c7]' : ''}`} />
          </button>

          {/* System status pill */}
          <div className="inline-flex items-center gap-2 px-3.5 h-9 rounded-full bg-white border border-[#cde0ee] shadow-sm text-xs font-semibold text-[#0e1824]">
            <span
              className={`w-2 h-2 rounded-full ${
                isBackendHealthy
                  ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)] animate-pulse'
                  : 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.7)]'
              }`}
            />
            <span className="tracking-tight">{isBackendHealthy ? 'Twin Synced' : 'Degraded'}</span>
          </div>
        </div>
      </div>

      {/* Sub-navigation bar for tablet & mobile */}
      <div className="lg:hidden px-6 py-2.5 border-t border-[#d8e6f2] overflow-x-auto flex items-center gap-1.5 bg-[#eff5fb]">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-1 ${
                isActive
                  ? 'bg-white text-[#0e1824] shadow-sm'
                  : 'text-[#486581] hover:text-[#0e1824] hover:bg-white/50'
              }`}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    </header>
  );
};
