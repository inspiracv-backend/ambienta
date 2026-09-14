import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { EtapasMejoraPanel } from './EtapasMejoraPanel';
import { AuditLogProvider } from '@/lib/audit-log-store';
import { SessionProvider } from '@/lib/session';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { iniciarSesionComo } from '@/test/utils';
import { ApiError } from '@/lib/api-client';

/**
 * El panel contra la tabla tipada (#27).
 *
 * Hasta el 13-sep guardaba en el JSONB que el cierre no mira, y la eficacia que
 * habilitaba el cierre salía de lo escrito en el formulario: marcar "SI" sin
 * guardar habilitaba un cierre que la API después rechazaba.
 */

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/no-conformidades/nc-1',
}));

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();

vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      post: (...a: unknown[]) => post(...a),
      patch: (...a: unknown[]) => patch(...a),
      delete: vi.fn(),
    },
  };
});

function etapa(kind: string, over: Record<string, unknown> = {}) {
  return {
    id: `e-${kind}`, kind, responsable_user_id: null, metodologia_id: null, fecha_ejecucion: null,
    due_date: null, completada_en: null, eficaz: null, causa_se_repitio: null, cumplio_proposito: null,
    requiere_actualizar_riesgos: null, requiere_cambios_sgc: null, observaciones: null,
    evidencia_urls: [], datos: {}, ...over,
  };
}

const ETAPAS = ['registro', 'correccion', 'analisis_causa', 'accion_correctiva', 'seguimiento'].map((k) =>
  k === 'registro' ? etapa(k, { fecha_ejecucion: '2026-09-01', completada_en: '2026-09-01T12:00:00Z' }) : etapa(k),
);

let cierre = { puede: false, motivo: 'Hay etapas sin completar: correccion.' };

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <AuditLogProvider>
        <UsersProvider>
          <SessionProvider>{children}</SessionProvider>
        </UsersProvider>
      </AuditLogProvider>
    </ToastProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  cierre = { puede: false, motivo: 'Hay etapas sin completar: correccion.' };
  get.mockImplementation((url: string) => {
    if (url.endsWith('/etapas')) return Promise.resolve(ETAPAS);
    if (url.endsWith('/puede-cerrarse')) return Promise.resolve(cierre);
    if (url.includes('/catalogos/severidades')) return Promise.resolve([{ code: 'major', label: 'Mayor' }]);
    if (url.includes('/catalogos/metodologias')) return Promise.resolve([]);
    return Promise.resolve([]);
  });
});

async function montar(onCierreChange = vi.fn()) {
  iniciarSesionComo('admin_empresa');
  render(<EtapasMejoraPanel ncId="nc-1" responsableOptions={[]} onCierreChange={onCierreChange} />, { wrapper });
  await screen.findByText('Etapa de Corrección', { exact: false });
  return onCierreChange;
}

describe('el cierre lo decide el servidor', () => {
  it('marcar SI sin guardar no habilita el cierre', async () => {
    const onCierre = await montar();
    await waitFor(() => expect(onCierre).toHaveBeenCalled());
    onCierre.mockClear();

    await userEvent.selectOptions(screen.getByLabelText('Eficacia'), 'SI');

    expect(onCierre).not.toHaveBeenCalled();
    expect(patch).not.toHaveBeenCalled();
  });

  it('después de guardar se vuelve a preguntar', async () => {
    patch.mockImplementation((_url: string, cuerpo: Record<string, unknown>) =>
      Promise.resolve(etapa('seguimiento', { eficaz: cuerpo.eficaz })),
    );
    const onCierre = await montar();
    await waitFor(() => expect(onCierre).toHaveBeenCalled());
    cierre = { puede: true, motivo: null };

    await userEvent.selectOptions(screen.getByLabelText('Eficacia'), 'SI');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar etapas' }));

    await waitFor(() => expect(onCierre).toHaveBeenLastCalledWith({ puede: true, motivo: null }));
  });
});

describe('guardar', () => {
  it('manda solo la etapa que cambió, a la tabla tipada', async () => {
    patch.mockResolvedValue(etapa('correccion', { datos: { correccionInmediata: 'Se aisló el derrame' } }));
    await montar();

    await userEvent.type(screen.getByLabelText('Corrección Inmediata'), 'Se aisló el derrame');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar etapas' }));

    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    const [url, cuerpo] = patch.mock.calls[0];
    expect(url).toBe('/audits/nonconformities/nc-1/etapas/e-correccion');
    expect(cuerpo).not.toHaveProperty('improvement_stages');
  });

  it('si la base rechaza, dice qué etapa no se guardó', async () => {
    patch.mockRejectedValue(new ApiError(422, 'Unprocessable Entity', { detail: 'responsable_user_id no válido' }));
    await montar();

    await userEvent.type(screen.getByLabelText('Corrección Inmediata'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar etapas' }));

    expect(await screen.findByText(/No se guardó la etapa de corrección/)).toBeInTheDocument();
    expect(screen.queryByText('Etapas guardadas.')).not.toBeInTheDocument();
  });
});

describe('la severidad', () => {
  it('sale del catálogo de la empresa, no de "Alta/Media/Baja"', async () => {
    await montar();
    const select = screen.getByLabelText('Tipo de Severidad') as HTMLSelectElement;
    const opciones = Array.from(select.options).map((o) => o.text);
    expect(opciones).toContain('Mayor');
    expect(opciones).not.toContain('Alta');
  });
});
