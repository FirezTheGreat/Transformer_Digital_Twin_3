/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Newsreader"', '"Instrument Serif"', 'Georgia', 'serif'],
        editorial: ['"Newsreader"', '"Instrument Serif"', 'Georgia', 'serif'],
        display: ['"Newsreader"', '"Instrument Serif"', 'Georgia', 'serif'],
        sans: ['"Plus Jakarta Sans"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        ink: {
          950: '#070d16',
          900: '#0e1824',
          800: '#19283a',
          700: '#253a52',
          600: '#354e6b',
        },
        skybg: {
          50: '#f8fbfe',
          100: '#eff5fb',
          150: '#e5f0f8',
          200: '#dceaf5',
          300: '#c5dded',
          400: '#9bc4e2',
        },
        ice: {
          surface: '#ffffff',
          tint: '#e7f1f9',
          border: '#d4e3f0',
          borderStrong: '#c2d7e8',
          textMuted: '#5d768f',
        }
      },
      boxShadow: {
        'card': '0 8px 30px -8px rgba(35, 75, 115, 0.07), 0 2px 6px rgba(35, 75, 115, 0.03)',
        'card-hover': '0 16px 40px -10px rgba(35, 75, 115, 0.12), 0 4px 10px rgba(35, 75, 115, 0.05)',
        'pill': '0 4px 12px rgba(14, 24, 36, 0.1)',
      }
    },
  },
  plugins: [],
}
