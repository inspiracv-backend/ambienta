/**
 * Si Clerk está configurado o no. Un solo lugar decide.
 *
 * Las `NEXT_PUBLIC_*` se hornean en el bundle durante el build, así que esto
 * es una comparación con `undefined`, no una consulta. Cambiar de modo exige
 * reconstruir la imagen — aceptable, porque no es un interruptor que deba
 * cambiar en producción.
 *
 * Existe como módulo propio para que middleware, provider y página de login
 * respondan lo mismo. Con la comprobación repetida en tres archivos, basta que
 * uno diverja para que el provider crea que hay Clerk y el login que no.
 */
export const CLERK_HABILITADO = Boolean(
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
);
