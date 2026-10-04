import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

// **Las pruebas corren en hora de Chile, en todas las maquinas.** Sin esto, en
// una maquina en UTC —CI— `new Date('2026-09-02')` cae en su dia y un error de
// "un dia antes" pasa en verde; en Chile falla. Ya paso con los documentos y
// con el calendario: la prueba solo servia en el computador de quien la
// escribio. Se fija antes de que arranquen los workers, que heredan el entorno.
process.env.TZ = 'America/Santiago';

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
