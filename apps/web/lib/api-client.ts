import { CLERK_HABILITADO } from '@/lib/clerk-config';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown,
  ) {
    super(`API ${status}: ${statusText}`);
    this.name = 'ApiError';
  }
}

/**
 * Un mensaje que se le pueda mostrar a una persona.
 *
 * `detail` de FastAPI viene en dos formas distintas segun quien rechace: una
 * cadena cuando la rechaza un router, y una **lista** de errores por campo
 * cuando la rechaza la validacion de Pydantic. Leer solo la primera deja los
 * 422 —los mas frecuentes al conectar una pantalla— mostrando `[object Object]`.
 */
export function mensajeDeError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    // Ni siquiera llegamos a la API: DNS, red caida, CORS.
    return 'No se pudo contactar al servidor. Revisa tu conexion.';
  }

  const detail = (error.body as { detail?: unknown } | null)?.detail;

  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail)) {
    const campos = detail
      .map((d) => {
        const loc = Array.isArray((d as { loc?: unknown[] }).loc)
          ? (d as { loc: unknown[] }).loc.filter((p) => p !== 'body').join('.')
          : '';
        const msg = String((d as { msg?: unknown }).msg ?? '');
        return loc ? `${loc}: ${msg}` : msg;
      })
      .filter(Boolean);
    if (campos.length > 0) return campos.join(' · ');
  }

  if (error.status === 409) return 'Ya existe un registro con ese valor.';
  if (error.status === 403) return 'No tienes permiso para hacer esto.';
  return `El servidor rechazo la operacion (${error.status}).`;
}

/**
 * De donde sale el token en cada request.
 *
 * Es un **getter**, no un token. El JWT Template de Clerk emite tokens de 60
 * segundos: cualquier string capturado y pasado como parametro estaria vencido
 * a los pocos minutos de tener la pantalla abierta. `getToken()` de Clerk
 * renueva solo, asi que lo que hay que guardar es la funcion.
 *
 * Vive en el modulo y no en un contexto de React porque `api` se llama desde
 * stores que no siempre estan bajo el provider de Clerk, y porque asi las 20
 * llamadas que ya existen no tienen que enterarse de nada.
 */
type ProveedorDeToken = () => Promise<string | null>;

let proveedorDeToken: ProveedorDeToken | null = null;

/**
 * Con Clerk hay una carrera real: los stores disparan su fetch en un
 * `useEffect` y el puente registra el token en otro. Clerk arranca con
 * `isLoaded: false`, asi que el primer request saldria sin token, cobraria un
 * 401 y el store caeria a los mocks sin reintentar nunca.
 *
 * Esta promesa hace que `request()` espere a que la identidad este resuelta.
 * Sin Clerk ya nace cumplida y no cambia nada.
 */
let marcarAutenticacionLista: () => void = () => {};
const autenticacionLista: Promise<void> = CLERK_HABILITADO
  ? new Promise<void>((resolver) => {
      marcarAutenticacionLista = resolver;
    })
  : Promise.resolve();

/**
 * Deja registrado de donde sacar el token. Pasar `null` es una respuesta
 * valida y definitiva —"esta sesion no lleva token"—, no un "todavia no se":
 * tambien destraba a quien este esperando.
 */
export function registrarProveedorDeToken(proveedor: ProveedorDeToken | null) {
  proveedorDeToken = proveedor;
  marcarAutenticacionLista();
}

/** Que hacer cuando la API responde 401. Lo registra el puente de Clerk. */
let alPerderLaSesion: (() => void) | null = null;

export function registrarSesionExpirada(manejo: (() => void) | null) {
  alPerderLaSesion = manejo;
}

interface RequestOptions {
  tenantId?: string | null;
  signal?: AbortSignal;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  await autenticacionLista;

  // Prioridad: token > tenantId. Con Clerk configurado la API ignora
  // X-Tenant-Id por completo (ver apps/api/app/deps.py), asi que mandar ambos
  // seria ruido — y mandar solo el tenant da 401.
  const token = proveedorDeToken ? await proveedorDeToken() : null;
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  } else if (opts.tenantId) {
    headers['X-Tenant-Id'] = opts.tenantId;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    signal: opts.signal,
  });

  if (!res.ok) {
    // Sin reintento: si el token no sirve, pedirlo otra vez da lo mismo.
    // Clerk ya renueva por su cuenta dentro de `getToken()`.
    if (res.status === 401) alPerderLaSesion?.();
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, res.statusText, detail);
  }

  return res.json() as Promise<T>;
}

export const api = {
  get<T>(path: string, opts?: RequestOptions) {
    return request<T>('GET', path, undefined, opts);
  },
  post<T>(path: string, body: unknown, opts?: RequestOptions) {
    return request<T>('POST', path, body, opts);
  },
  patch<T>(path: string, body: unknown, opts?: RequestOptions) {
    return request<T>('PATCH', path, body, opts);
  },
  delete<T>(path: string, opts?: RequestOptions) {
    return request<T>('DELETE', path, undefined, opts);
  },
};
