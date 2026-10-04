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

let cierre: { puede: boolean; motivo: string | null } = { puede: false, motivo: 'Hay etapas sin completar: correccion.' };
let compromisos: Record<string, unknown>[] | 'falla' = [];

// Las personas a las que se puede asignar una salida.
vi.mock('@/lib/crm-etapas-store', () => ({
  usePersonasAsignables: () => ({ personas: [{ id: 'u-1', nombre: 'Ana Rojas' }], cargando: false, fallo: false }),
}));

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
  compromisos = [];
  get.mockImplementation((url: string) => {
    if (url.endsWith('/etapas')) return Promise.resolve(ETAPAS);
    if (url.endsWith('/puede-cerrarse')) return Promise.resolve(cierre);
    if (url.includes('/catalogos/severidades')) return Promise.resolve([{ code: 'major', label: 'Mayor' }]);
    if (url.includes('/catalogos/metodologias')) return Promise.resolve([]);
    if (url.includes('/compromisos')) {
      return compromisos === 'falla'
        ? Promise.reject(new ApiError(500, 'Internal Server Error', null))
        : Promise.resolve(compromisos);
    }
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

  it('si una falla, las demás se guardan igual y dice cuántas quedaron sin guardar', async () => {
    // Escenario "una parte falla y otra no" de escrituras-de-la-interfaz.
    patch.mockImplementation((url: string) =>
      url.endsWith('/e-correccion')
        ? Promise.reject(new ApiError(422, 'Unprocessable Entity', { detail: 'responsable inválido' }))
        : Promise.resolve(etapa('seguimiento', { observaciones: 'verificado en terreno' })),
    );
    await montar();

    await userEvent.type(screen.getByLabelText('Corrección Inmediata'), 'x');
    await userEvent.type(screen.getByLabelText('Evidencia Seguimiento'), 'verificado en terreno');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar etapas' }));

    expect(await screen.findByText(/No se guardaron 1 de 2 etapas: corrección/)).toBeInTheDocument();
    expect(patch).toHaveBeenCalledTimes(2);

    // Al reintentar se manda solo la que falló: la otra ya coincide con la base.
    patch.mockClear();
    patch.mockResolvedValue(etapa('correccion', { datos: { correccionInmediata: 'x', evidencia: '' } }));
    await userEvent.click(screen.getByRole('button', { name: 'Guardar etapas' }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    expect(patch.mock.calls[0][0]).toMatch(/e-correccion$/);
  });

  it('si la base rechaza, dice qué etapa no se guardó', async () => {
    patch.mockRejectedValue(new ApiError(422, 'Unprocessable Entity', { detail: 'responsable_user_id no válido' }));
    await montar();

    await userEvent.type(screen.getByLabelText('Corrección Inmediata'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar etapas' }));

    expect(await screen.findByText(/No se guardaron 1 de 1 etapas: corrección/)).toBeInTheDocument();
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

describe('las salidas comprometidas', () => {
  const compromiso = (over: Record<string, unknown> = {}) => ({
    id: 'c-1',
    nonconformity_id: 'nc-1',
    kind: 'matriz_riesgos',
    descripcion: null,
    status: 'pendiente',
    responsable_user_id: null,
    responsable_nombre: null,
    due_date: null,
    justificacion: null,
    completada_en: null,
    nonconformity_code: 'NC-1',
    nonconformity_title: 'Derrame',
    ...over,
  });

  it('se leen del servidor, no del JSON de la etapa', async () => {
    compromisos = [compromiso()];
    await montar();

    expect(await screen.findByText('Actualizar matriz de riesgos y oportunidades')).toBeTruthy();
    expect(get).toHaveBeenCalledWith('/audits/nonconformities/nc-1/compromisos', { tenantId: expect.any(String) });
  });

  it('sin responsable o sin fecha dice que asi no se cierra', async () => {
    compromisos = [compromiso()];
    await montar();

    expect(await screen.findByText(/no se le avisa a nadie/)).toBeTruthy();
  });

  it('asignar un responsable lo guarda en el servidor', async () => {
    compromisos = [compromiso()];
    patch.mockResolvedValue(compromiso({ responsable_user_id: 'u-1' }));
    await montar();

    await userEvent.selectOptions(await screen.findByLabelText('Responsable'), 'u-1');

    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith('/audits/compromisos/c-1', { responsable_user_id: 'u-1' }, { tenantId: expect.any(String) }),
    );
  });

  it('descartar sin justificacion no se manda: la API lo rechazaria', async () => {
    compromisos = [compromiso()];
    await montar();

    await userEvent.selectOptions(
      await screen.findByLabelText('Estado de Actualizar matriz de riesgos y oportunidades'),
      'descartada',
    );

    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls.at(-1)?.[1]).toEqual({ status: 'pendiente' });
  });

  it('si no se pudieron cargar, lo dice en vez de parecer que no hay ninguna', async () => {
    compromisos = 'falla';
    await montar();

    expect((await screen.findByRole('alert')).textContent).toMatch(/No se pudieron cargar las salidas/);
  });
});

