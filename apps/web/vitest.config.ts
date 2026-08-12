import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: ['**/*.test.{ts,tsx}'],
    exclude: ['node_modules', '.next'],
  },
  resolve: {
    alias: {
      // Mismos alias que tsconfig.json: '@/…' apunta a la raíz de apps/web y
      // '@ambienta/shared' al paquete compartido sin build previo.
      '@': resolve(__dirname, '.'),
      '@ambienta/shared': resolve(__dirname, '../../packages/shared/src'),
    },
  },
});
