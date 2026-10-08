import React from 'react';
import { RefreshCw, Activity, Moon, Sun } from 'lucide-react';

interface NavbarProps {
  isBackendHealthy: boolean;
  activeTab: string;
  onTabChange: (tab: string) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
  theme?: 'light' | 'dark';
  onToggleTheme?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  isBackendHealthy,
  activeTab,
  onTabChange,
  onRefresh,
  isRefreshing,
  theme = 'light',
  onToggleTheme,
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
    <header className="sticky top-0 z-40 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        {/* Brand & Subtitle */}
        <div
          onClick={() => onTabChange('overview')}
          className="flex items-center gap-3 cursor-pointer select-none flex-shrink-0"
        >
          <div className="w-8 h-8 rounded bg-slate-900 dark:bg-slate-800 border dark:border-slate-700 flex items-center justify-center text-white">
            <Activity className="w-4 h-4 text-sky-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-bold text-slate-900 dark:text-slate-100 tracking-tight leading-none">
                GridPulse
              </span>
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-semibold border border-slate-200 dark:border-slate-700 leading-none">
                Digital Twin
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-normal mt-0.5 leading-none">
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
                    ? 'border-sky-600 dark:border-sky-400 text-sky-700 dark:text-sky-400 font-bold bg-sky-50/40 dark:bg-sky-950/30'
                    : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:border-slate-300 dark:hover:border-slate-700'
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Right Actions: Theme Toggle, System Status & Refresh */}
        <div className="flex items-center gap-2.5 flex-shrink-0">
          {onToggleTheme && (
            <button
              onClick={onToggleTheme}
              title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
              className="p-1.5 rounded text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 transition-colors"
            >
              {theme === 'dark' ? <Sun className="w-3.5 h-3.5 text-amber-400" /> : <Moon className="w-3.5 h-3.5" />}
            </button>
          )}

          <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-700 dark:text-slate-300 font-medium">
            <span
              className={`w-2 h-2 rounded-full ${
                isBackendHealthy ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
            />
            <span className="text-[11px] font-medium text-slate-600 dark:text-slate-400">
              {isBackendHealthy ? 'Twin Online' : 'Degraded'}
            </span>
          </div>

          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            title="Refresh Digital Twin State"
            className="p-1.5 rounded text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-sky-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Mobile / Tablet Horizontal Navigation Scroll */}
      <div className="lg:hidden px-4 py-2 border-t border-slate-200 dark:border-slate-800 overflow-x-auto flex items-center gap-2 bg-slate-50 dark:bg-slate-900">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`px-3 py-1.5 rounded text-xs font-medium whitespace-nowrap transition-colors ${
                isActive
                  ? 'bg-slate-900 dark:bg-slate-800 text-white font-semibold'
                  : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700'
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
