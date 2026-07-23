import type { Config } from 'tailwindcss';

/**
 * Paleta y tokens según "Prompts de Diseño — Ambienta v1.5" (Notion, 2026-07-23):
 * paleta verde/turquesa profesional, semáforo de urgencia siempre ícono + color + texto.
 */
const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#effcf6',
          100: '#c9f7e4',
          400: '#22b899',
          500: '#0f9d84',
          600: '#0b7d6b',
          700: '#0a6357',
          900: '#0a3f39',
        },
        accent: {
          400: '#2dd4bf',
          500: '#14b8a6',
        },
        semaforo: {
          cumple: '#1a7f4f',
          'cumple-bg': '#e6f6ec',
          parcial: '#a15c00',
          'parcial-bg': '#fdf1e0',
          'no-cumple': '#b3261e',
          'no-cumple-bg': '#fbe9e7',
          na: '#5f6368',
          'na-bg': '#f1f3f4',
        },
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        card: '0.75rem',
      },
    },
  },
  plugins: [],
};

export default config;
