import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NuevaAuditoriaModal } from './NuevaAuditoriaModal';
import { ApiError } from '@/lib/api-client';

const get = vi.fn();
const post = vi.fn();
vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return { ...real, api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a), patch: vi.fn(), delete: vi.fn() } };
});
vi.mock('@/lib/crm-etapas-store', () => ({
  usePersonasAsignables: () => ({ personas: [{ id: 'u-1', nombre: 'Ana Pérez' }], cargando: false, fallo: false }),
}));

const T = 'a0000000-0000-0000-0000-000000000001';

beforeEach(() => {
  vi.clearAllMocks();
  get.mockResolvedValue([{ code: `AUD-${new Date().getFullYear()}-002` }]);
});

function montar(onCreada = vi.fn()) {
  render(
    <NuevaAuditoriaModal
      open
      onOpenChange={vi.fn()}
      tenantId={T}
      plantas={[{ id: 'p-1', nombre: 'Planta Calama' }]}
      onCreada={onCreada}
    />,
  );
  return onCreada;
}

describe('crear una auditoría', () => {
  it('propone el siguiente código y manda el cuerpo de la API', async () => {
    const creada = { id: 'A', code: 'x' };
    post.mockResolvedValue(creada);
    const onCreada = montar();

    const codigo = screen.getByLabelText(/Código/) as HTMLInputElement;
    await waitFor(() => expect(codigo.value).toBe(`AUD-${new Date().getFullYear()}-003`));
    await userEvent.type(screen.getByLabelText(/Título/), 'Auditoría de residuos');
    await userEvent.type(screen.getByLabelText(/Alcance/), 'Residuos peligrosos');
    await userEvent.selectOptions(screen.getByLabelText(/Planta/), 'p-1');
    await userEvent.selectOptions(screen.getByLabelText(/Auditor líder/), 'u-1');
    await userEvent.click(screen.getByRole('button', { name: 'Crear auditoría' }));

    await waitFor(() => expect(onCreada).toHaveBeenCalledWith(creada));
    const [ruta, cuerpo, opciones] = post.mock.calls[0]!;
    expect(ruta).toBe('/audits/');
    expect(cuerpo).toMatchObject({
      title: 'Auditoría de residuos',
      scope: 'Residuos peligrosos',
      audit_type: 'internal',
      facility_id: 'p-1',
      lead_auditor_user_id: 'u-1',
      planned_start: null,
    });
    expect(opciones).toEqual({ tenantId: T });
  });

  it('sin título ni alcance no manda nada', async () => {
    montar();
    await userEvent.click(screen.getByRole('button', { name: 'Crear auditoría' }));

    expect(post).not.toHaveBeenCalled();
    expect(screen.getByText('Ingresa un título.')).toBeTruthy();
    expect(screen.getByText('Describe qué se va a auditar.')).toBeTruthy();
  });

  it('un código repetido se dice con el motivo y el formulario queda', async () => {
    post.mockRejectedValue(new ApiError(409, 'Conflict', { detail: 'Ya existe una auditoria con ese codigo' }));
    const onCreada = montar();

    await userEvent.type(screen.getByLabelText(/Título/), 'Auditoría de residuos');
    await userEvent.type(screen.getByLabelText(/Alcance/), 'Residuos peligrosos');
    await userEvent.click(screen.getByRole('button', { name: 'Crear auditoría' }));

    expect((await screen.findByRole('alert')).textContent).toContain('No se creó la auditoría');
    expect(onCreada).not.toHaveBeenCalled();
    expect((screen.getByLabelText(/Título/) as HTMLInputElement).value).toBe('Auditoría de residuos');
  });
});
