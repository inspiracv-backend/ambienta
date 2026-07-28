/** @type {import('next').NextConfig} */
const nextConfig = {
  // `@ambienta/shared` se publica como TypeScript fuente (sin build propio),
  // así que Next debe transpilarlo.
  transpilePackages: ['@ambienta/shared'],

  // Necesario para la imagen Docker de producción: genera `.next/standalone`
  // con solo las dependencias efectivamente usadas (imagen mucho más liviana
  // que copiar todo node_modules del monorepo).
  output: 'standalone',

  experimental: {
    // En el monorepo, el tracing de archivos debe partir desde la raíz para
    // incluir packages/shared; sin esto el standalone omite el workspace.
    // En Next 14 esta opción vive bajo `experimental` (en Next 15 pasó a raíz).
    outputFileTracingRoot: require('path').join(__dirname, '../../'),
  },
};

module.exports = nextConfig;
