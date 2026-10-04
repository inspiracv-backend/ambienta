/**
 * Las pantallas que se ven **sin sesión**: el ingreso, el registro (solo para
 * aceptar una invitación), el acceso de Cliente Invitado y la creación de un
 * ticket (RF-02). Un solo lugar para el middleware y para el puente de Clerk.
 *
 * **Estaban escritas dos veces y una de las dos faltaba.** El middleware las
 * dejaba pasar, pero en el navegador cualquier petición a la API sin sesión
 * —la lista de usuarios se pide al montar la aplicación— respondía 401, y el
 * puente de Clerk mandaba a `/login`. Medido el 22-sep con Clerk activo:
 * `/acceso-invitado` y `/signup` rebotaban al ingreso. El invitado no podía
 * pedir su acceso, y la persona invitada no podía crear su cuenta.
 */
export const RUTAS_PUBLICAS = ['/login', '/signup', '/acceso-invitado', '/crear-ticket'] as const;

/** Si esta dirección se ve sin sesión. Por segmento: `/signups` no es `/signup`. */
export function esRutaPublica(pathname: string): boolean {
  return RUTAS_PUBLICAS.some((r) => pathname === r || pathname.startsWith(`${r}/`) || pathname.startsWith(`${r}?`));
}
