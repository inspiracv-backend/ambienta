/**
 * De donde sale el semaforo de una declaracion (#113).
 *
 * **Este archivo no existia**, y por eso nadie noto que el criterio estaba
 * escrito dos veces y **ya separado**: el navegador avisaba a 30 dias
 * (`DIAS_PARA_AVISAR`) y el servidor a 15 (`DIAS_PROXIMO` en
 * `services/declaracion.py`). Una obligacion a 20 dias salia "por vencer" en
 * pantalla y "vigente" en cualquier otra lectura de la API — el mismo tipo de
 * desacuerdo que ya tuvo el porcentaje de cumplimiento entre la pantalla y el
 * informe.
 *
 * Ahora el criterio vive en un solo lado y el navegador lo consume. Estas
 * pruebas fijan eso: **lo que se afirma es que la pantalla obedece al
 * servidor**, no que sepa calcular tramos.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { ObligationsProvider, useObligations } from './obligations-store';
import { SessionProvider } from './session';
import { ToastProvider } from './toast-store';
import { AuditLogProvider } from './audit-log-store';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/obligaciones',
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

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <AuditLogProvider>
        <UsersProvider>
          <SessionProvider>
            <ObligationsProvider>{children}</ObligationsProvider>
          </SessionProvider>
        </UsersProvider>
      </AuditLogProvider>
    </ToastProvider>
  );
}

/** Vence dentro de 20 dias: entre los 15 del servidor y los 30 que usaba el navegador. */
const EN_20_DIAS = new Date(Date.now() + 20 * 86_400_000).toISOString();

function obligacionApi(extra: Record<string, unknown> = {}) {
  return {
    id: ID,
    tenant_id: 't-1',
    code: 'OBL-SIDREP-2026S1',
    title: 'Declaracion SIDREP',
    status: 'open',
    due_at: EN_20_DIAS,
    facility_id: 'p-1',
    ...extra,
  };
}

/** El id de la obligacion que devuelve la API en estas pruebas. */
const ID = 'ob-1';

async function montar(filas: Record<string, unknown>[]) {
  iniciarSesionComo('admin_empresa');
  get.mockImplementation((ruta: string) =>
    Promise.resolve(ruta.startsWith('/obligations') ? filas : []),
  );
  const r = renderHook(() => useObligations(), { wrapper });

  // **Se espera la fila de la API, no que la lista deje de estar vacia.**
  //
  // El store arranca con `mockObligations` —17 entradas— asi que
  // `length > 0` es cierto desde el primer render y el `waitFor` no esperaba
  // nada: las afirmaciones corrian contra los datos de ejemplo.
  //
  // En local ganaba la carrera y pasaba; **en CI no**, y ahi salio.
  await waitFor(() =>
    expect(r.result.current.obligations.some((o) => o.id === ID)).toBe(true),
  );
  return r;
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe('el semaforo lo decide el servidor', () => {
  it('usa la urgencia que llega en la respuesta', async () => {
    const { result } = await montar([obligacionApi({ urgencia: 'critica' })]);

    expect(result.current.obligations.find((o) => o.id === ID)!.estado).toBe('por_vencer');
  });

  it('a 20 dias obedece al servidor, no a su propia cuenta', async () => {
    // **El desacuerdo exacto que existia.** Con el criterio viejo del navegador
    // (30 dias) esto daba 'por_vencer'; el servidor dice 'vigente' porque su
    // tramo es de 15. Gana el servidor.
    const { result } = await montar([obligacionApi({ urgencia: 'vigente' })]);

    expect(result.current.obligations.find((o) => o.id === ID)!.estado).toBe('vigente');
  });

  it('una aceptada con plazo pasado no sale vencida', async () => {
    const { result } = await montar([
      obligacionApi({
        status: 'accepted',
        due_at: new Date(Date.now() - 30 * 86_400_000).toISOString(),
        urgencia: 'resuelta',
      }),
    ]);

    expect(result.current.obligations.find((o) => o.id === ID)!.estado).toBe('vigente');
  });

  it('rechazada gana sobre la urgencia, porque no habla del plazo', async () => {
    // "Sin evidencia" dice **que falta hacer**, no cuanto queda. Una declaracion
    // rechazada hay que rehacerla aunque el vencimiento este lejos.
    const { result } = await montar([
      obligacionApi({ status: 'rejected', urgencia: 'vigente' }),
    ]);

    expect(result.current.obligations.find((o) => o.id === ID)!.estado).toBe('sin_evidencia');
  });

  it('sin urgencia en la respuesta no inventa tramos', async () => {
    // El respaldo es deliberadamente tosco: distingue lo vencido y nada mas. Si
    // reimplementara los tramos volveria a haber dos criterios.
    const { result } = await montar([obligacionApi()]);

    expect(result.current.obligations.find((o) => o.id === ID)!.estado).toBe('vigente');
  });

  it('sin urgencia, lo vencido igual se ve vencido', async () => {
    const { result } = await montar([
      obligacionApi({ due_at: new Date(Date.now() - 86_400_000).toISOString() }),
    ]);

    expect(result.current.obligations.find((o) => o.id === ID)!.estado).toBe('vencida');
  });
});
