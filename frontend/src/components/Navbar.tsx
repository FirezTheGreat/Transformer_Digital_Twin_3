import React from 'react';
import { RefreshCw, Activity } from 'lucide-react';

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
    { id: 'twin-analysis', label: 'Thermal & What-If' },
    { id: 'anomalies', label: 'Anomalies & Evidence' },
    { id: 'maintenance', label: 'Maintenance Advisories' },
    { id: 'telemetry', label: 'Electrical Telemetry' },
    { id: 'model-card', label: 'Model Card & Specs' },
    { id: 'twin-3d', label: '3D Component View' },
  ];

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        {/* Brand & Subtitle */}
        <div
          onClick={() => onTabChange('overview')}
          className="flex items-center gap-3 cursor-pointer select-none flex-shrink-0"
        >
          <div className="w-8 h-8 rounded bg-slate-900 flex items-center justify-center text-white">
            <Activity className="w-4 h-4 text-sky-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-bold text-slate-900 tracking-tight leading-none">
                GridPulse
              </span>
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-semibold border border-slate-200 leading-none">
                Digital Twin
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-normal mt-0.5 leading-none">
              Tripura 33/11kV Substation Monitoring
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden lg:flex items-center gap-1 h-full">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`h-full px-3.5 text-xs font-semibold flex items-center border-b-2 transition-colors ${
                  isActive
                    ? 'border-sky-600 text-sky-700 font-bold bg-sky-50/40'
                    : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Right Actions: System Status & Refresh */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-slate-50 border border-slate-200 text-xs text-slate-700 font-medium">
            <span
              className={`w-2 h-2 rounded-full ${
                isBackendHealthy ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
            />
            <span className="text-[11px] font-medium text-slate-600">
              {isBackendHealthy ? 'Twin Online' : 'Degraded'}
            </span>
          </div>

          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            title="Refresh Digital Twin State"
            className="p-1.5 rounded text-slate-500 hover:text-slate-800 hover:bg-slate-100 border border-slate-200 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-sky-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Mobile / Tablet Horizontal Navigation Scroll */}
      <div className="lg:hidden px-4 py-2 border-t border-slate-200 overflow-x-auto flex items-center gap-2 bg-slate-50">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`px-3 py-1.5 rounded text-xs font-medium whitespace-nowrap transition-colors ${
                isActive
                  ? 'bg-slate-900 text-white font-semibold'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
              }`}
            >
              {item.label}
            </button>
          );
        })}
      </div>
    </header>
  );
};
