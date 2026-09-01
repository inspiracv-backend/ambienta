/**
 * Que una lista cortada se note (#167).
 *
 * La API acota cada listado y avisa por la cabecera `X-Has-More`. Sin leerla,
 * el corte es **invisible**: una empresa con 640 aspectos ve 500 y nada se lo
 * dice. Es lo que la issue llama "más engañoso que no paginar" — una lista
 * cortada se ve exactamente igual que una completa, así que nadie la reporta.
 *
 * En una matriz de aspectos el daño es concreto: quien la revisa cree que
 * revisó todo, y el pedazo que falta es justo el que un auditor va a pedir.
 *
 * Estas pruebas afirman sobre lo que el store **expone**, que es lo que las
 * tres pantallas ISO muestran.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { IsoProvider, useIso } from './iso-store';
import { SessionProvider } from './session';
import { ToastProvider } from './toast-store';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
}));

const get = vi.fn();
const getPagina = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      getPagina: (...a: unknown[]) => getPagina(...a),
      post: vi.fn(),
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

/** `hayMas` por ruta: lo que la cabecera `X-Has-More` habría dicho. */
function responder(hayMas: { aspects?: boolean; risks?: boolean; equipment?: boolean }) {
  getPagina.mockImplementation((ruta: string) => {
    const cual = ruta.includes('aspects')
      ? 'aspects'
      : ruta.includes('risks')
        ? 'risks'
        : 'equipment';
    return Promise.resolve({
      datos: [{ id: `${cual}-1` }],
      hayMas: Boolean(hayMas[cual as keyof typeof hayMas]),
    });
  });
  // `/facilities/` sigue por `get`: no necesita saber si vino cortado.
  get.mockResolvedValue([{ id: 'p-1', name: 'Planta Calama' }]);
}

beforeEach(() => {
  window.localStorage.clear();
  get.mockReset();
  getPagina.mockReset();
  iniciarSesionComo('admin_empresa');
  responder({});
});

async function montar() {
  const r = renderHook(() => useIso(), { wrapper: envoltura });
  await waitFor(() => expect(r.result.current.cargando).toBe(false));
  return r;
}

describe('cuando la API dice que cortó', () => {
  it('el store nombra QUÉ listado vino cortado', async () => {
    // Nombrarlo importa: "hay más registros" sin decir de qué obliga a
    // revisar las tres pantallas para encontrar cuál.
    responder({ aspects: true });
    const { result } = await montar();

    expect(result.current.truncado).toEqual(['aspectos ambientales']);
  });

  it('nombra los tres cuando los tres se cortaron', async () => {
    responder({ aspects: true, risks: true, equipment: true });
    const { result } = await montar();

    expect(result.current.truncado).toEqual([
      'aspectos ambientales',
      'riesgos y oportunidades',
      'equipos regulados',
    ]);
  });

  it('solo el que se cortó, no los que no', async () => {
    responder({ risks: true });
    const { result } = await montar();

    expect(result.current.truncado).toEqual(['riesgos y oportunidades']);
  });
});

describe('cuando no cortó', () => {
  it('no hay nada que avisar', async () => {
    // La otra mitad: un aviso que sale siempre no informa, y quien lo ve
    // todos los días deja de leerlo.
    const { result } = await montar();

    expect(result.current.truncado).toEqual([]);
  });

  it('y los datos se cargan igual', async () => {
    const { result } = await montar();

    expect(result.current.aspectos).toHaveLength(1);
    expect(result.current.riesgos).toHaveLength(1);
    expect(result.current.equipos).toHaveLength(1);
  });
});

describe('la petición', () => {
  it('los tres listados se piden con `getPagina`, no con `get`', async () => {
    // Con `get` la cabecera se pierde antes de llegar acá, y el corte vuelve
    // a ser invisible sin que nada falle.
    await montar();

    const rutas = getPagina.mock.calls.map((c) => String(c[0]));
    expect(rutas.some((r) => r.includes('/iso14001/aspects'))).toBe(true);
    expect(rutas.some((r) => r.includes('/iso14001/risks'))).toBe(true);
    expect(rutas.some((r) => r.includes('/iso14001/equipment'))).toBe(true);
  });

  it('se sigue pidiendo dentro del tope del servidor', async () => {
    // 500 es el máximo que la API acepta (#167). Pedir más da 422 y las tres
    // pantallas quedarían vacías con un error que no dice nada útil.
    await montar();

    for (const [ruta] of getPagina.mock.calls) {
      const pedido = Number(new URL(String(ruta), 'http://x').searchParams.get('limit'));
      expect(pedido).toBeLessThanOrEqual(500);
    }
  });
});
