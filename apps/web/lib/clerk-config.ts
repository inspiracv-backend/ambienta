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

/**
 * Nombre del JWT Template que inyecta `tenant_id`.
 *
 * **Hay que pedirlo por nombre.** `getToken()` a secas devuelve el token de
 * sesion estandar, que NO lleva claims personalizados: verificado contra la
 * instancia real, sus claims son `azp, exp, fva, iat, iss, nbf, sid, sts,
 * sub, v` y ninguno es `tenant_id`. Solo `getToken({ template })` lo trae, y
 * sin ese claim `get_tenant_id()` rechaza el request con 401.
 *
 * Que el template se llame `default` no lo vuelve el predeterminado: es solo
 * su nombre. Configurable por si el equipo lo renombra.
 */
export const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? 'default';
