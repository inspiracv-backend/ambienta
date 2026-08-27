/**
 * Que un cero de la API no se muestre como datos de ejemplo (#208).
 *
 * Tres stores que **no tenían ninguna prueba**: `gestores`, `plan-accion` y
 * `support-tickets`. Van juntos porque lo que se afirma es exactamente lo
 * mismo en los tres, y un archivo por store repetiría el andamiaje entero para
 * una prueba cada uno.
 *
 * ## El defecto
 *
 *     if (mapped.length > 0) setX(mapped);
 *
 * No distingue dos cosas muy distintas:
 *
 * - la API **falló** → conservar lo que hay es un respaldo razonable
 * - la API respondió **cero filas** → conservar los datos de ejemplo es mostrar
 *   algo que esa empresa no tiene
 *
 * En estos tres el daño es concreto: un contrato de gestor inventado, un plan
 * de acción que nadie abrió, o un ticket de soporte fantasma con el que alguien
 * va a intentar interactuar.
 *
 * ## Las dos trampas al escribir estas pruebas
 *
 * 1. **`waitFor(loading === false)` se cumple de inmediato** si el store sale
 *    temprano por falta de sesión. Hay que esperar a que la sesión cargue
 *    **y** a que la API se haya llamado.
 * 2. **`get.mockResolvedValue(x)` responde a todas las rutas**, incluida
 *    `/tenants/`, y alimenta a los otros providers con datos que no son suyos.
 *    El fallo aparece lejos. Se enruta por ruta.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { AuditLogProvider } from './audit-log-store';
import { GestoresProvider, useGestores } from './gestores-store';
import { PlanAccionProvider, usePlanAccion } from './plan-accion-store';
import { SessionProvider, useSession } from './session';
import { SupportTicketsProvider, useSupportTickets } from './support-tickets-store';
import { ToastProvider } from './toast-store';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
}));

const get = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      patch: vi.fn(),
      post: vi.fn(),
      delete: vi.fn(),
    },
  };
});

function envoltura(Provider: (p: { children: ReactNode }) => JSX.Element) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <ToastProvider>
        <AuditLogProvider>
          <UsersProvider>
            <SessionProvider>
              <Provider>{children}</Provider>
            </SessionProvider>
          </UsersProvider>
        </AuditLogProvider>
      </ToastProvider>
    );
  };
}

/**
 * Monta un store con la API respondiendo vacío **para su ruta**, y espera a que
 * de verdad la haya llamado.
 */
async function montarVacio<T>(
  Provider: (p: { children: ReactNode }) => JSX.Element,
  hook: () => T,
  ruta: string,
) {
  iniciarSesionComo('admin_empresa');
  get.mockImplementation(() => Promise.resolve([]));

  const r = renderHook(() => ({ s: useSession(), store: hook() }), {
    wrapper: envoltura(Provider),
  });

  await waitFor(() => expect(r.result.current.s.user?.tenantId).toBeTruthy());
  await waitFor(() =>
    expect(get.mock.calls.some(([p]) => String(p).startsWith(ruta))).toBe(true),
  );

  return r;
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe('gestores', () => {
  it('sin contratos en la API no se ven los de ejemplo', async () => {
    // Un contrato inventado le dice a un Gestor que administra a un cliente que
    // no es suyo.
    const r = await montarVacio(GestoresProvider, useGestores, '/contracts');

    await waitFor(() => expect(r.result.current.store.loading).toBe(false));
    expect(r.result.current.store.contratos).toHaveLength(0);
  });
});

describe('planes de acción', () => {
  it('sin planes en la API no se ven los de ejemplo', async () => {
    // Un plan inventado aparece como trabajo pendiente de alguien que nunca lo
    // abrió, y ensucia el seguimiento de los que sí existen.
    const r = await montarVacio(PlanAccionProvider, usePlanAccion, '/audits/action-plans');

    await waitFor(() => expect(r.result.current.store.loading).toBe(false));
    expect(r.result.current.store.plans).toHaveLength(0);
  });
});

describe('tickets de soporte', () => {
  it('sin tickets en la API no se ven los de ejemplo', async () => {
    // Un ticket fantasma es peor que los otros dos: alguien va a intentar
    // responderlo, y la respuesta no llega a ninguna parte.
    const r = await montarVacio(SupportTicketsProvider, useSupportTickets, '/support');

    await waitFor(() => expect(r.result.current.store.loading).toBe(false));
    expect(r.result.current.store.tickets).toHaveLength(0);
  });
});

// ── Los cuatro que ya tenían archivo de pruebas, y por qué están aquí ──────
//
// `audits`, `departamentos`, `legal-matrix` y `obligations` tienen su propio
// archivo. **Sus pruebas de #208 no pueden vivir ahí:** esos archivos stubean
// los datos de ejemplo a vacío con `vi.mock('@/mocks/...', () => ({ x: [] }))`,
// así que una prueba que afirme "no se ven los ejemplos" obtiene 0 con el
// arreglo puesto **y también sin él**.
//
// La primera versión de este trabajo las puso ahí. La mutación las delató:
// cinco de nueve sobrevivían. Aquí los mocks son los de verdad, así que la
// afirmación distingue.

import { AuditsProvider, useAudits } from './audits-store';
import { DepartamentosProvider, useDepartamentos } from './departamentos-store';
import { LegalMatrixProvider, useLegalMatrix } from './legal-matrix-store';
import { ObligationsProvider, useObligations } from './obligations-store';

describe('auditorías y no conformidades', () => {
  it('sin nada en la API no se ven las de ejemplo', async () => {
    // Una no conformidad inventada dispara un plan de acción sobre algo que no
    // ocurrió.
    const r = await montarVacio(AuditsProvider, useAudits, '/audits');

    await waitFor(() => expect(r.result.current.store.loading).toBe(false));
    expect(r.result.current.store.audits).toHaveLength(0);
    expect(r.result.current.store.nonConformities).toHaveLength(0);
  });
});

describe('departamentos', () => {
  it('sin ninguno en la API no se ven los de ejemplo', async () => {
    // RF-11 exige que todo Usuario Interno pertenezca a un departamento: uno
    // inventado deja crear usuarios contra algo que no existe.
    const r = await montarVacio(DepartamentosProvider, useDepartamentos, '/processes');

    await waitFor(() => expect(r.result.current.store.loading).toBe(false));
    expect(r.result.current.store.departamentos).toHaveLength(0);
  });
});

describe('matriz legal', () => {
  it('sin normas en la API no se ven las de ejemplo', async () => {
    // **El peor caso de todos.** Una norma inventada en la matriz de una
    // empresa es un requisito que nadie le exige, evaluado contra artículos que
    // no le aplican, y que después sale en el informe que se le entrega a un
    // fiscalizador.
    const r = await montarVacio(LegalMatrixProvider, useLegalMatrix, '/catalog/norms');

    await waitFor(() => expect(r.result.current.store.loading).toBe(false));
    expect(r.result.current.store.norms).toHaveLength(0);
  });
});

describe('obligaciones', () => {
  it('sin ninguna en la API no se ven las de ejemplo', async () => {
    // Diecisiete declaraciones inventadas, con sus vencimientos, en el
    // calendario de una empresa que no tiene ninguna.
    const r = await montarVacio(ObligationsProvider, useObligations, '/obligations');

    await waitFor(() => expect(r.result.current.store.loading).toBe(false));
    expect(r.result.current.store.obligations).toHaveLength(0);
  });
});
