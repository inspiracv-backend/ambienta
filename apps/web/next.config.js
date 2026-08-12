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

  webpack: (config, { webpack, dev }) => {
    // Fuera de desarrollo, el DevRoleSwitcher se sustituye por un componente
    // vacío. Es la única forma fiable de mantenerlo fuera del bundle: un
    // `if (process.env.NODE_ENV === 'production') return null` dentro del
    // componente impide que renderice, pero webpack igual compila el módulo
    // completo — verificado buscando sus textos en `.next` tras un build.
    // Al reemplazar el módulo, la herramienta y los usuarios mock que muestra
    // no llegan a producción ni siquiera como código muerto.
    if (!dev) {
      config.plugins.push(
        new webpack.NormalModuleReplacementPlugin(
          /components[\\/]organisms[\\/]DevRoleSwitcher([\\/]|$)/,
          require('path').resolve(__dirname, 'lib/dev-role-switcher.noop.tsx'),
        ),
      );
    }
    return config;
  },
};

module.exports = nextConfig;
