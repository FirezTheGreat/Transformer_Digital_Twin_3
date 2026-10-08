import React, { useEffect, useState } from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

/**
 * Presentational chart primitives. These only render values they are given;
 * they never derive or fabricate data.
 */

export interface ChartTheme {
  series: [string, string, string];
  grid: string;
  axis: string;
  surface: string;
  ink: string;
  muted: string;
  warn: string;
  crit: string;
}

const readTheme = (): ChartTheme => {
  const s = getComputedStyle(document.documentElement);
  const v = (name: string, fallback: string) => s.getPropertyValue(name).trim() || fallback;
  return {
    series: [v('--chart-1', '#2f6cb3'), v('--chart-2', '#b5772c'), v('--chart-3', '#0e9180')],
    grid: v('--chart-grid', '#e2e9f1'),
    axis: v('--chart-axis', '#98a6b8'),
    surface: v('--chart-surface', '#f9fbfd'),
    ink: `rgb(${v('--ink', '20 29 43')})`,
    muted: `rgb(${v('--muted', '98 114 136')})`,
    warn: `rgb(${v('--warn', '160 112 42')})`,
    crit: `rgb(${v('--crit', '166 66 62')})`,
  };
};

/** Reads chart colours from CSS tokens and refreshes when the theme class flips. */
export const useChartTheme = (): ChartTheme => {
  const [theme, setTheme] = useState<ChartTheme>(readTheme);
  useEffect(() => {
    const observer = new MutationObserver(() => setTheme(readTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);
  return theme;
};

export interface TrendSeries {
  key: string;
  label: string;
  /** Index into the validated categorical order (0 = accent). */
  colorIndex?: 0 | 1 | 2;
}

interface TrendChartProps {
  data: Array<Record<string, string | number | null>>;
  xKey: string;
  series: TrendSeries[];
  unit?: string;
  height?: number;
  /** Soft area fill under a single series (reference "cash flow" treatment). */
  area?: boolean;
  decimals?: number;
}

export const TrendChart: React.FC<TrendChartProps> = ({
  data,
  xKey,
  series,
  unit = '',
  height = 240,
  area = false,
  decimals = 1,
}) => {
  const theme = useChartTheme();
  const gradientId = `trend-fill-${series.map((s) => s.key).join('-')}`;
  const fmt = (val: unknown) =>
    typeof val === 'number' ? `${val.toFixed(decimals)}${unit ? ` ${unit}` : ''}` : '—';

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={theme.series[0]} stopOpacity={0.22} />
              <stop offset="100%" stopColor={theme.series[0]} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke={theme.grid} />
          <XAxis
            dataKey={xKey}
            tick={{ fill: theme.axis, fontSize: 10.5 }}
            tickLine={false}
            axisLine={false}
            minTickGap={36}
            tickMargin={10}
          />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fill: theme.axis, fontSize: 10.5 }}
            tickLine={false}
            axisLine={false}
            width={48}
            tickFormatter={(v: number) => String(Number(Number(v).toFixed(1)))}
          />
          <Tooltip
            cursor={{ stroke: theme.axis, strokeWidth: 1, strokeDasharray: '3 3' }}
            formatter={(value: unknown, name: string) => [fmt(value), name]}
            labelStyle={{ color: 'rgb(var(--muted))', fontSize: 11, marginBottom: 4 }}
            itemStyle={{ color: 'rgb(var(--ink))', fontSize: 11, padding: 0 }}
          />
          {area && series.length === 1 && (
            <Area
              type="monotone"
              dataKey={series[0].key}
              stroke="none"
              fill={`url(#${gradientId})`}
              isAnimationActive={false}
              legendType="none"
              tooltipType="none"
              connectNulls
            />
          )}
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={theme.series[s.colorIndex ?? 0]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: theme.surface }}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

/** Legend chip used beside chart titles (identity is never colour-alone: always labelled). */
export const LegendItem: React.FC<{ label: string; colorIndex?: 0 | 1 | 2; color?: string; dashed?: boolean }> = ({
  label,
  colorIndex = 0,
  color,
  dashed = false,
}) => {
  const theme = useChartTheme();
  return (
    <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.09em] text-muted">
      <span
        className="inline-block w-3 h-0"
        style={{ borderTop: `2px ${dashed ? 'dashed' : 'solid'} ${color ?? theme.series[colorIndex]}` }}
      />
      {label}
    </span>
  );
};

/** Reads the first numeric measurement matching one of the signal ids (display only). */
export const readSignal = (
  measurements: Array<{ signal_id: string; value: unknown }>,
  ids: string[]
): number | null => {
  for (const id of ids) {
    const m = measurements.find((x) => x.signal_id === id);
    if (m && typeof m.value === 'number') return m.value;
  }
  return null;
};

/** Compact UTC tick label: "MM-DD HH:mm". */
export const formatUtcTick = (iso: string): string =>
  new Date(iso).toISOString().slice(5, 16).replace('T', ' ');
