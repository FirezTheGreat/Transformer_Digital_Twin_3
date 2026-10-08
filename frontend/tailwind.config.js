/** @type {import('tailwindcss').Config} */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Geist"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['"Geist Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
        display: ['"Bodoni Moda"', 'Didot', '"Bodoni 72"', '"Bodoni MT"', 'serif'],
      },
      colors: {
        // Semantic design tokens (switch automatically between cream light and graphite dark)
        canvas: token('canvas'),
        primary: token('primary'),
        'on-primary': token('on-primary'),
        sidebar: token('sidebar'),
        surface: token('surface'),
        'surface-2': token('surface-2'),
        'surface-3': token('surface-3'),
        line: token('line'),
        'line-strong': token('line-strong'),
        ink: token('ink'),
        'ink-2': token('ink-2'),
        muted: token('muted'),
        faint: token('faint'),
        accent: token('accent'),
        'accent-soft': token('accent-soft'),
        'accent-ink': token('accent-ink'),
        inverse: token('inverse'),
        'on-inverse': token('on-inverse'),
        ok: token('ok'),
        warn: token('warn'),
        crit: token('crit'),
        slate: {
          850: '#151f32',
          950: '#090e17',
        },
        brand: {
          50: '#f0f7ff',
          100: '#e0effe',
          500: '#0284c7',
          600: '#0369a1',
          700: '#075985',
        },
        panel: {
          bg: '#ffffff',
          subtle: '#f8fafc',
          border: '#e2e8f0',
          borderStrong: '#cbd5e1',
          textMuted: '#64748b',
        }
      },
      boxShadow: {
        'subtle': '0 1px 2px 0 rgba(20, 29, 43, 0.03)',
        'card': '0 1px 2px 0 rgba(20, 29, 43, 0.04)',
        'elevated': '0 12px 32px -12px rgba(20, 29, 43, 0.18), 0 2px 6px -2px rgba(20, 29, 43, 0.06)',
      },
      borderRadius: {
        'card': '6px',
      },
      letterSpacing: {
        eyebrow: '0.08em',
      },
    },
  },
  plugins: [],
}
