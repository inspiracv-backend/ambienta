/**
 * Las cuatro vistas que el servidor deriva (#44, #47, #48, #49).
 *
 * La API las tenía desde hace semanas y **el store no llamaba a ninguna**:
 * `/aspects/significant-untreated`, `/equipment/expiring` y
 * `/aspects/{id}/evaluate` existían sin un solo llamador, y
 * `/equipment/sin-operador` ni siquiera estaba expuesta aunque su servicio
 * estuviera escrito y probado desde el 12-ago.
 *
 * ## Lo que estas pruebas vigilan de verdad
 *
 * No es que el store las pida — eso se ve leyendo el archivo. Es **que un fallo
 * en una vista derivada no borre las matrices**, y que un cero nunca se dibuje
 * sobre una consulta que no volvió.
 *
 * | situación | lo fácil | lo correcto |
 * |---|---|---|
 * | Falla `/expiring` | las tres matrices en blanco | las matrices siguen |
 * | Falla una derivada | mostrar 0 por vencer | decir que falló |
 * | Todavía no volvió | mostrar 0 | `derivadas === null` |
 *
 * La tercera es la que importa más: un cero dibujado sobre una consulta
 * pendiente afirma "no hay nada que atender", que es la lectura más
 * tranquilizadora y la más falsa. Este proyecto ya cometió esa clase de error
 * cuatro veces con `normSemaforo(0)` y las plantas sin evaluar.
 *
 * ## Lo que este archivo NO cubre, y hay que decirlo
 *
 * El store tenía un defecto real que **ninguna prueba de acá atrapa**: borraba
 * las derivadas cuando el tenant se iba un instante. Se midió con una traza
 * dentro del efecto:
 *
 *     EFECTO tenantId=null          ← la sesión resolviéndose
 *     EFECTO tenantId=a0000000...   ← pide las tres vistas
 *     THEN   vigente=true           ← las escribe
 *     EFECTO tenantId=null          ← y las borraba
 *
 * Está arreglado —el efecto ya no borra al perder el tenant, igual que el de
 * las matrices— y se intentó cubrirlo con una prueba que limpiaba
 * `localStorage` y volvía a renderizar. **Esa prueba era vacua**: la sesión no
 * vuelve a `null` por eso, y la mutación que reintroduce el borrado seguía
 * pasando en verde. Se quitó en vez de dejarla afirmando algo que no
 * comprueba.
 *
 * Cubrirlo de verdad necesita controlar `useSession` desde fuera, que este
 * arnés no permite hoy.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { IsoProvider, useIso } from './iso-store';
import { SessionProvider } from './session';
import { ToastProvider } from './toast-store';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';
import { mockUsers } from '@/mocks/users';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
}));

const get = vi.fn();
const getPagina = vi.fn();
const post = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      getPagina: (...a: unknown[]) => getPagina(...a),
      post: (...a: unknown[]) => post(...a),
      patch: vi.fn(),
      delete: vi.fn(),
    },
  };
});

const TENANT = 'a0000000-0000-0000-0000-000000000001';

function envoltura({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>
          <IsoProvider>{children}</IsoProvider>
        </SessionProvider>
      </UsersProvider>
    </ToastProvider>
  );
}

const SIN_TRATAR = [
  {
    id: 'a-1',
    activity: 'Chancado de mineral',
    aspect: 'Emisión de material particulado',
    total_score: 64,
    facility_id: 'p-1',
  },
];

const VENCIMIENTOS = {
  equipos: [
    {
      equipment_id: 'e-1',
      facility_id: 'p-1',
      name: 'Caldera de vapor principal',
      registration_authority: 'SEC',
      registration_number: 'SEC-123',
      expires_at: '2026-09-20',
      dias_restantes: 14,
    },
  ],
  operadores: [
    {
      equipment_id: 'e-1',
      user_id: 'u-1',
      certification_class: 'Clase B',
      certification_number: 'C-9',
      expires_at: '2026-08-01',
      // Ya vencida: viene en la misma lista a propósito.
      dias_restantes: -36,
    },
  ],
  dias: 30,
  hoy: '2026-09-06',
};

const SIN_OPERADOR = [
  {
    equipment_id: 'e-2',
    facility_id: 'p-1',
    name: 'Estanque de petróleo diésel',
    equipment_type: 'estanque',
    motivo: 'certificacion_vencida',
    operadores_asignados: 1,
    ultima_certificacion: '2026-08-01',
  },
];

/** Las tres matrices responden bien; las derivadas, lo que se le pase. */
function responder(derivadas: {
  sinTratar?: unknown;
  vencimientos?: unknown;
  sinOperador?: unknown;
}) {
  getPagina.mockImplementation(() =>
    Promise.resolve({ datos: [{ id: 'x-1' }], hayMas: false }),
  );
  get.mockImplementation((ruta: string) => {
    if (ruta.includes('significant-untreated')) {
      return derivadas.sinTratar instanceof Error
        ? Promise.reject(derivadas.sinTratar)
        : Promise.resolve(derivadas.sinTratar ?? []);
    }
    if (ruta.includes('expiring')) {
      return derivadas.vencimientos instanceof Error
        ? Promise.reject(derivadas.vencimientos)
        : Promise.resolve(derivadas.vencimientos ?? { equipos: [], operadores: [], dias: 30 });
    }
    if (ruta.includes('sin-operador')) {
      return derivadas.sinOperador instanceof Error
        ? Promise.reject(derivadas.sinOperador)
        : Promise.resolve(derivadas.sinOperador ?? []);
    }
    // **`/users/` tiene que responder usuarios.** La primera version dejaba que
    // el caso por defecto devolviera la lista de plantas también para esta
    // ruta, y al resolverse `users-store` se quedaba sin encontrar al usuario
    // de la sesión: `tenantId` pasaba a `null` y el efecto de las derivadas
    // las reseteaba. Cinco pruebas fallaron acusando al store, que estaba bien.
    if (ruta.startsWith('/users/')) return Promise.resolve(mockUsers);
    // **`/tenants/` rechaza, como en la realidad.** Esa ruta responde 401
    // cuando la sesión viaja por `X-Tenant-Id` (CLAUDE.md), y el store cae a
    // `mockTenants`. Devolverle plantas en su lugar hacía que la sesión
    // perdiera su usuario a mitad de camino y que **toda escritura saliera
    // temprano sin llamar a la API**: el arnés simulaba algo que no pasa.
    if (ruta.startsWith('/tenants/')) return Promise.reject(new Error('401'));
    return Promise.resolve([{ id: 'p-1', name: 'Planta Calama' }]);
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  iniciarSesionComo('admin_empresa');
});

describe('las cuatro vistas derivadas llegan a la pantalla', () => {
  it('trae los aspectos significativos que nadie enlazó a un riesgo', async () => {
    responder({ sinTratar: SIN_TRATAR });
    const { result } = renderHook(() => useIso(), { wrapper: envoltura });

    await waitFor(() => expect(result.current.derivadas).not.toBeNull());

    expect(result.current.derivadas!.sinTratar).toHaveLength(1);
    expect(result.current.derivadas!.sinTratar[0].aspecto).toContain('material particulado');
    expect(result.current.derivadas!.sinTratar[0].puntajeTotal).toBe(64);
  });

  it('separa inscripciones de certificaciones, y lo vencido va en la misma lista', async () => {
    responder({ vencimientos: VENCIMIENTOS });
    const { result } = renderHook(() => useIso(), { wrapper: envoltura });

    await waitFor(() => expect(result.current.derivadas).not.toBeNull());
    const d = result.current.derivadas!;

    expect(d.inscripciones).toHaveLength(1);
    expect(d.certificaciones).toHaveLength(1);
    // Negativo = ya venció. Sacarlo de "por vencer" escondería lo urgente.
    expect(d.certificaciones[0].diasRestantes).toBeLessThan(0);
    expect(d.diasDeAviso).toBe(30);
  });

  it('conserva el motivo del equipo sin operador y no lo deduce', async () => {
    responder({ sinOperador: SIN_OPERADOR });
    const { result } = renderHook(() => useIso(), { wrapper: envoltura });

    await waitFor(() => expect(result.current.derivadas).not.toBeNull());

    const fila = result.current.derivadas!.sinOperador[0];
    expect(fila.motivo).toBe('certificacion_vencida');
    // Con este motivo hay gente asignada: lo que falta es renovar, no asignar.
    expect(fila.operadoresAsignados).toBe(1);
  });
});

describe('una vista derivada que falla no puede tumbar las matrices', () => {
  it('los aspectos siguen cargando aunque se caiga la de vencimientos', async () => {
    responder({ vencimientos: new Error('500 del servidor') });
    const { result } = renderHook(() => useIso(), { wrapper: envoltura });

    await waitFor(() => expect(result.current.cargando).toBe(false));

    expect(result.current.aspectos.length).toBeGreaterThan(0);
    expect(result.current.errorDeCarga).toBeNull();
  });

  it('dice que falló en vez de mostrar cero', async () => {
    responder({ sinOperador: new Error('se cayó la consulta') });
    const { result } = renderHook(() => useIso(), { wrapper: envoltura });

    await waitFor(() => expect(result.current.derivadas).not.toBeNull());

    expect(result.current.errorDerivadas).toBeTruthy();
  });

  it('que falle una no esconde a las otras dos', async () => {
    responder({ vencimientos: new Error('se cayó'), sinTratar: SIN_TRATAR });
    const { result } = renderHook(() => useIso(), { wrapper: envoltura });

    await waitFor(() => expect(result.current.derivadas).not.toBeNull());

    expect(result.current.derivadas!.sinTratar).toHaveLength(1);
    expect(result.current.derivadas!.inscripciones).toHaveLength(0);
    expect(result.current.errorDerivadas).toBeTruthy();
  });
});

describe('evaluar la significancia la decide el servidor', () => {
  it('llama al endpoint con los tres puntajes', async () => {
    responder({});
    post.mockResolvedValue({});
    const { result } = renderHook(() => useIso(), { wrapper: envoltura });
    await waitFor(() => expect(result.current.cargando).toBe(false));

    await result.current.evaluarSignificancia('a-1', {
      frequency_score: 8,
      severity_score: 7,
      legal_score: 9,
    });

    expect(post).toHaveBeenCalledWith(
      '/iso14001/aspects/a-1/evaluate',
      { frequency_score: 8, severity_score: 7, legal_score: 9 },
      expect.objectContaining({ tenantId: TENANT }),
    );
  });
});
