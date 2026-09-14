import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import type { Plant } from '@ambienta/shared';
import { RegisterFindingForm } from './RegisterFindingForm';
import { AuditsProvider } from '@/lib/audits-store';
import { AuditLogProvider } from '@/lib/audit-log-store';
import { SessionProvider } from '@/lib/session';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { iniciarSesionComo } from '@/test/utils';
import { ApiError } from '@/lib/api-client';

/**
 * Registrar un hallazgo desde la pantalla (#37).
 *
 * Hasta el 13-sep no funcionaba en ningún caso: los datos del tipo no se
 * mandaban, el responsable era de ejemplo y se navegaba a un id que la base no
 * tenía.
 */

const push = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push, prefetch: vi.fn() }),
  usePathname: () => '/no-conformidades/nueva',
}));

const get = vi.fn();
const post = vi.fn();
vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return {
    ...real,
    api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a), patch: vi.fn(), delete: vi.fn() },
  };
});

vi.mock('@/mocks/audits', () => ({ mockAudits: [], mockNonConformities: [] }));

const TENANT = 'a0000000-0000-0000-0000-000000000001';
const PLANTA_ID = 'c0000000-0000-0000-0000-000000000001';
const PLANTA = { id: PLANTA_ID, nombre: 'Planta Calama', tenantId: TENANT, comuna: 'Calama', region: 'Antofagasta' } as unknown as Plant;
const PERSONA = { id: 'd0000000-0000-0000-0000-000000000001', nombre: 'Camila Rojas' };

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <AuditLogProvider>
        <UsersProvider>
          <SessionProvider>
            <AuditsProvider>{children}</AuditsProvider>
          </SessionProvider>
        </UsersProvider>
      </AuditLogProvider>
    </ToastProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  get.mockImplementation((url: string) => {
    if (url.includes('/catalogos/severidades')) return Promise.resolve([{ code: 'minor', label: 'Menor' }, { code: 'major', label: 'Mayor' }]);
    if (url.includes('/items')) return Promise.resolve([{ id: 'item-1', sequence: 1, question: '¿Hay contención?' }]);
    return Promise.resolve([]);
  });
  post.mockResolvedValue({
    id: 'e0000000-0000-0000-0000-00000000000a', tenant_id: TENANT, facility_id: PLANTA.id, code: 'NC-1',
    title: 'x', description: 'Derrame', severity: 'major', status: 'open', detected_at: '2026-09-13T12:00:00Z',
  });
});

async function montar(props: { defaultAuditId?: string } = {}) {
  iniciarSesionComo('admin_empresa');
  render(
    <RegisterFindingForm tenantId={TENANT} plants={[PLANTA]} responsableOptions={[PERSONA]} defaultPlantId={PLANTA.id} {...props} />,
    { wrapper },
  );
  await screen.findByRole('button', { name: 'Mayor' });
}

async function completarBase() {
  await userEvent.selectOptions(screen.getByLabelText(/Tipo de registro/), 'salida_no_conforme');
  await userEvent.selectOptions(screen.getByLabelText(/Tipo de detección/), 'interna');
  await userEvent.type(screen.getByLabelText(/SKU/), 'SKU-1');
  await userEvent.type(screen.getByLabelText(/Lote/), 'L-9');
  await userEvent.type(screen.getByLabelText(/Nombre del producto/), 'Aceite');
  await userEvent.type(screen.getByLabelText(/^Cantidad/), '3');
  await userEvent.type(screen.getByLabelText(/Descripción/), 'Derrame menor');
  await userEvent.selectOptions(screen.getByLabelText(/Responsable/), PERSONA.id);
}

describe('registrar', () => {
  it('manda los datos del tipo y navega al id que asignó la base', async () => {
    await montar();
    await completarBase();
    await userEvent.click(screen.getByRole('button', { name: 'Registrar mejora' }));

    await waitFor(() => expect(push).toHaveBeenCalledWith('/no-conformidades/e0000000-0000-0000-0000-00000000000a'));
    const cuerpo = post.mock.calls[0][1] as Record<string, unknown>;
    expect(cuerpo).toMatchObject({
      record_type: 'salida_no_conforme',
      detection_origin: 'interna',
      severity: 'major',
      owner_user_id: PERSONA.id,
      product_data: { sku: 'SKU-1', lote: 'L-9', nombre: 'Aceite', cantidad: '3' },
    });
  });

  it('si la base lo rechaza, lo dice y no navega', async () => {
    post.mockRejectedValue(new ApiError(422, 'Unprocessable Entity', { detail: 'owner_user_id no válido' }));
    await montar();
    await completarBase();
    await userEvent.click(screen.getByRole('button', { name: 'Registrar mejora' }));

    expect(await screen.findByText(/No se registró/)).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});

describe('origen de auditoría', () => {
  it('sin auditoría de origen no se ofrece: la API exigiría una pregunta', async () => {
    await montar();
    const opciones = Array.from((screen.getByLabelText(/Tipo de detección/) as HTMLSelectElement).options).map((o) => o.value);
    expect(opciones).not.toContain('auditoria_interna');
  });

  it('viniendo de una auditoría, pide la pregunta y la manda', async () => {
    await montar({ defaultAuditId: 'aud-1' });
    await userEvent.selectOptions(screen.getByLabelText(/Tipo de registro/), 'no_conformidad');
    await userEvent.selectOptions(await screen.findByLabelText(/Pregunta de la auditoría/), 'item-1');
    await userEvent.type(screen.getByLabelText(/Descripción/), 'Sin contención');
    await userEvent.selectOptions(screen.getByLabelText(/Responsable/), PERSONA.id);
    await userEvent.click(screen.getByRole('button', { name: 'Registrar mejora' }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1]).toMatchObject({ detection_origin: 'auditoria_interna', audit_item_id: 'item-1' });
  });
});
