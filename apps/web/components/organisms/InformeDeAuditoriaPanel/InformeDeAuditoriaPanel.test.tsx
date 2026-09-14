import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { InformeDeAuditoriaPanel } from './InformeDeAuditoriaPanel';
import { AuditLogProvider } from '@/lib/audit-log-store';
import { SessionProvider } from '@/lib/session';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { iniciarSesionComo } from '@/test/utils';
import { porcentaje } from '@/lib/informe-auditoria';

/** El informe de auditoría (RF-101, #42): lo que dice, y que no acusa con ceros. */

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/auditorias/a-1',
}));

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return {
    ...real,
    api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a), patch: (...a: unknown[]) => patch(...a), delete: vi.fn() },
  };
});

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

const INFORME = {
  audit_id: 'a-1', codigo: 'AUD-2026-002', titulo: 'Auditoría interna', estado: 'active',
  resumen: { procesos_auditados: 1, items_sin_proceso: 0, no_conformidades: 0, observaciones: 0, oportunidades_de_mejora: 0, conformidad: null },
  matriz: [{
    proceso_id: 'p-1', proceso_nombre: 'Gestión de residuos', clausulas_auditadas: ['8.1'], items: 0,
    items_conformes: 0, items_no_conformes: 0, hallazgos: [], clasificacion: 'no_auditado', conclusion: null, evidencia_revisada: null,
  }],
  tasa_de_cierre_del_ciclo_anterior: null,
  motivo_sin_tasa: 'La auditoría anterior no dejó hallazgos.',
  auditoria_anterior_id: 'a-0',
};

let veredictos: { id: string; process_id: string }[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  veredictos = [];
  get.mockImplementation((url: string) => {
    if (url.endsWith('/informe')) return Promise.resolve(INFORME);
    if (url.endsWith('/procesos')) return Promise.resolve(veredictos);
    return Promise.resolve([]);
  });
  post.mockResolvedValue({});
  patch.mockResolvedValue({});
});

async function montar() {
  iniciarSesionComo('admin_empresa');
  render(<InformeDeAuditoriaPanel auditId="a-1" />, { wrapper });
  await screen.findByText('Gestión de residuos');
}

describe('los ceros que no son ceros', () => {
  it('sin nada evaluado dice "Sin evaluar", no 0 %', async () => {
    await montar();
    expect(screen.getByText('Sin evaluar')).toBeInTheDocument();
    expect(screen.queryByText('0 %')).not.toBeInTheDocument();
  });

  it('sin tasa de cierre dice por qué, en vez de 0 %', async () => {
    await montar();
    expect(screen.getByText(/La auditoría anterior no dejó hallazgos/)).toBeInTheDocument();
  });

  it('la API ya manda porcentajes: 1 es 1 %, no 100 %', () => {
    expect(porcentaje(1)).toBe('1 %');
    expect(porcentaje(87.5)).toBe('87,5 %');
  });
});

describe('el veredicto del proceso', () => {
  it('sin veredicto previo, se crea', async () => {
    await montar();
    await userEvent.click(screen.getByRole('button', { name: 'Dejar veredicto' }));
    await userEvent.selectOptions(screen.getByLabelText('Veredicto'), 'conforme');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar veredicto' }));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    const [url, cuerpo] = post.mock.calls[0];
    expect(url).toBe('/audits/a-1/procesos');
    expect(cuerpo).toMatchObject({ process_id: 'p-1', classification: 'conforme', conclusion: null });
    expect(patch).not.toHaveBeenCalled();
  });

  it('con veredicto previo, se edita en vez de chocar con el 409', async () => {
    veredictos = [{ id: 'v-9', process_id: 'p-1' }];
    await montar();
    await userEvent.click(screen.getByRole('button', { name: 'Dejar veredicto' }));
    await userEvent.click(screen.getByRole('button', { name: 'Guardar veredicto' }));

    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    expect(patch.mock.calls[0][0]).toBe('/audits/a-1/procesos/v-9');
    expect(post).not.toHaveBeenCalled();
  });
});
