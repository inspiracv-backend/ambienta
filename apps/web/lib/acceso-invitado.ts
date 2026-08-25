/**
 * El acceso del Cliente Invitado contra la API real (RF-01, RF-02, RF-07).
 *
 * ## Por que no usa `api-client.ts`
 *
 * Ese cliente adjunta el token de Clerk a **todo** request y espera a que la
 * identidad este resuelta antes de salir. Las dos cosas estorban acá:
 *
 * - El invitado **no tiene cuenta de Clerk**, así que no hay token que esperar.
 *   En la página pública `autenticacionLista` no se cumpliría nunca y la
 *   llamada quedaría colgada sin error visible: la pantalla se vería «cargando»
 *   para siempre.
 * - Su token es de **otro emisor**. Mezclarlo con el de Clerk en el mismo
 *   cliente sería la primera grieta por donde uno termina donde no corresponde.
 *
 * Son dos caminos de identidad separados a propósito, y esa separación se
 * sostiene también en el frontend.
 *
 * ## Dónde vive el token
 *
 * En `sessionStorage` y no en `localStorage`: vale 30 días del lado del
 * servidor, pero estas credenciales se entregan **sin verificar quién las
 * recibe** y muchas veces se usan en un equipo compartido. Que se vaya al
 * cerrar la pestaña es lo correcto para este caso; quien vuelva tiene su RUT y
 * su clave para entrar otra vez, que es justamente para lo que existen.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

const CLAVE_DE_SESION = 'ambienta.invitado.token';

export interface CredencialGenerada {
  rut: string;
  clave: string;
  valido_hasta: string;
  dias_de_vigencia: number;
}

export interface SolicitudDelInvitado {
  id: string;
  ticket_number: string;
  subject: string;
  status: string;
  created_at: string;
}

export class ErrorDeAccesoInvitado extends Error {
  constructor(
    public status: number,
    mensaje: string,
  ) {
    super(mensaje);
    this.name = 'ErrorDeAccesoInvitado';
  }
}

/**
 * De qué empresa es este enlace.
 *
 * Sale de `?empresa=` en la URL, porque el requisito habla del «acceso de
 * invitado **de una empresa**» y quien nunca inició sesión no tiene otra forma
 * de decirlo. `NEXT_PUBLIC_EMPRESA_INVITADO` existe solo para que la demo
 * funcione abriendo `/acceso-invitado` a secas.
 *
 * Devuelve `null` cuando no hay ninguna de las dos, y quien llama tiene que
 * mostrar un mensaje: **generar credenciales sin saber de qué empresa no es
 * algo que se pueda adivinar con un valor por omisión**, y elegir una al azar
 * le daría a la persona acceso a una empresa que no es la suya.
 */
export function empresaDelEnlace(search?: string): string | null {
  const parametros = new URLSearchParams(
    search ?? (typeof window === 'undefined' ? '' : window.location.search),
  );
  return (
    parametros.get('empresa') ??
    process.env.NEXT_PUBLIC_EMPRESA_INVITADO ??
    null
  );
}

async function pedir<T>(
  metodo: string,
  ruta: string,
  opciones: { cuerpo?: unknown; token?: string | null } = {},
): Promise<T> {
  const cabeceras: Record<string, string> = { 'Content-Type': 'application/json' };
  if (opciones.token) cabeceras.Authorization = `Bearer ${opciones.token}`;

  const res = await fetch(`${API_BASE}${ruta}`, {
    method: metodo,
    headers: cabeceras,
    body: opciones.cuerpo ? JSON.stringify(opciones.cuerpo) : undefined,
  });

  if (!res.ok) {
    const cuerpo = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new ErrorDeAccesoInvitado(
      res.status,
      cuerpo?.detail ?? `El servidor rechazó la operación (${res.status}).`,
    );
  }
  return res.json() as Promise<T>;
}

export function generarCredenciales(empresaId: string): Promise<CredencialGenerada> {
  return pedir<CredencialGenerada>(
    'POST',
    `/acceso-invitado/${empresaId}/credenciales`,
  );
}

/** Entra y **guarda el token**. Devuelve el RUT con el que quedó la sesión. */
export async function iniciarSesion(
  empresaId: string,
  rut: string,
  clave: string,
): Promise<string> {
  const sesion = await pedir<{ token: string; rut: string }>(
    'POST',
    `/acceso-invitado/${empresaId}/sesion`,
    { cuerpo: { rut, clave } },
  );
  guardarToken(sesion.token);
  return sesion.rut;
}

export function misSolicitudes(empresaId: string): Promise<SolicitudDelInvitado[]> {
  return pedir<SolicitudDelInvitado[]>(
    'GET',
    `/acceso-invitado/${empresaId}/mis-solicitudes`,
    { token: leerToken() },
  );
}

export function guardarToken(token: string): void {
  if (typeof window !== 'undefined') window.sessionStorage.setItem(CLAVE_DE_SESION, token);
}

export function leerToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.sessionStorage.getItem(CLAVE_DE_SESION);
}

export function olvidarToken(): void {
  if (typeof window !== 'undefined') window.sessionStorage.removeItem(CLAVE_DE_SESION);
}
