import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CicloDeAuditoriaPanel } from './CicloDeAuditoriaPanel';
import { ApiError } from '@/lib/api-client';

/**
 * Ejecutar una auditoría desde la pantalla: lo que se manda, y lo que deja de
 * ofrecerse cuando la API ya no lo acepta.
 */

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
const del = vi.fn();
vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      post: (...a: unknown[]) => post(...a),
      patch: (...a: unknown[]) => patch(...a),
      delete: (...a: unknown[]) => del(...a),
    },
  };
});

const T = 'a0000000-0000-0000-0000-000000000001';

function auditoria(status: string) {
  return {
    id: 'A',
    code: 'AUD-2026-004',
    title: 'Auditoría de residuos',
    audit_type: 'internal',
    scope: 'Residuos peligrosos',
    facility_id: null,
    status,
    planned_start: null,
    planned_end: null,
    actual_start: null,
    actual_end: null,
  };
}

const pregunta = {
  id: 'I',
  sequence: 1,
  question: '¿Se declaran los residuos en SIDREP?',
  result: 'pending',
  notes: null,
  process_id: null,
  article_compliance_id: null,
  assessed_at: null,
};

function responder(status: string) {
  get.mockImplementation((url: string) => {
    if (url === '/audits/A') return Promise.resolve(auditoria(status));
    if (url === '/audits/A/items') return Promise.resolve([pregunta]);
    if (url === '/audits/A/coverage') {
      return Promise.resolve({ aplicables: 0, cubiertos: 0, porcentaje: null, items_sin_articulo: 1 });
    }
    return Promise.resolve([]);
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

async function montar(status: string, onEstadoCambiado = vi.fn()) {
  responder(status);
  render(<CicloDeAuditoriaPanel auditId="A" tenantId={T} procesos={[]} onEstadoCambiado={onEstadoCambiado} />);
  await screen.findByText('¿Se declaran los residuos en SIDREP?');
  return onEstadoCambiado;
}

describe('responder el checklist', () => {
  it('manda el resultado y la evidencia, y no la fecha', async () => {
    patch.mockResolvedValue({ ...pregunta, result: 'nonconform', notes: 'Sin firma', assessed_at: '2026-09-19T15:00:00Z' });
    await montar('active');

    await userEvent.selectOptions(screen.getByLabelText('Resultado de la pregunta 1'), 'nonconform');
    await userEvent.type(screen.getByLabelText('Evidencia de la pregunta 1'), 'Sin firma');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch).toHaveBeenCalledWith('/audits/A/items/I', { result: 'nonconform', notes: 'Sin firma' }, { tenantId: T });
    // Con la no conformidad guardada se ofrece registrar su hallazgo, ya ligado a la pregunta.
    const enlace = await screen.findByRole('link', { name: 'Registrar el hallazgo de esta pregunta' });
    expect(enlace.getAttribute('href')).toContain('auditItemId=I');
  });

  it('agregar manda la pregunta sin resultado', async () => {
    post.mockResolvedValue({ ...pregunta, id: 'I2', sequence: 2, question: '¿Hay bodega techada?' });
    await montar('planned');

    await userEvent.type(screen.getByLabelText('Nueva pregunta'), '¿Hay bodega techada?');
    await userEvent.click(screen.getByRole('button', { name: 'Agregar pregunta' }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith('/audits/A/items', { question: '¿Hay bodega techada?', process_id: null }, { tenantId: T });
    expect(await screen.findByText('¿Hay bodega techada?')).toBeTruthy();
  });
});

describe('avanzar la auditoría', () => {
  it('iniciar pide la transición a la API y avisa el estado confirmado', async () => {
    post.mockResolvedValue({ ...auditoria('active'), actual_start: '2026-09-19T15:00:00Z' });
    const onEstado = await montar('planned');

    await userEvent.click(screen.getByRole('button', { name: 'Iniciar la auditoría' }));

    await waitFor(() => expect(onEstado).toHaveBeenCalledWith('active'));
    expect(post).toHaveBeenCalledWith('/audits/A/advance?new_status=active', {}, { tenantId: T });
    expect(screen.getByRole('button', { name: 'Pasar a informe' })).toBeTruthy();
  });

  it('cerrar pide confirmación y avisa las preguntas sin responder', async () => {
    post.mockResolvedValue(auditoria('closed'));
    await montar('reporting');

    await userEvent.click(screen.getByRole('button', { name: 'Cerrar la auditoría' }));

    expect(post).not.toHaveBeenCalled();
    expect(screen.getByRole('alertdialog').textContent).toContain('Quedan 1 pregunta sin responder');

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/audits/A/advance?new_status=closed', {}, { tenantId: T }));
  });

  it('si la API rechaza, lo dice y no cambia el estado', async () => {
    post.mockRejectedValue(new ApiError(400, 'Bad Request', { detail: "Cannot transition from 'planned' to 'active'" }));
    const onEstado = await montar('planned');

    await userEvent.click(screen.getByRole('button', { name: 'Iniciar la auditoría' }));

    expect((await screen.findByRole('alert')).textContent).toContain('No cambió el estado');
    expect(onEstado).not.toHaveBeenCalled();
    expect(screen.getByText('Planificada')).toBeTruthy();
  });
});

describe('una auditoría cerrada', () => {
  it('no ofrece editar el checklist ni avanzar', async () => {
    await montar('closed');

    expect(screen.queryByLabelText('Resultado de la pregunta 1')).toBeNull();
    expect(screen.queryByLabelText('Nueva pregunta')).toBeNull();
    expect(screen.queryByRole('button', { name: /Cancelar|Iniciar|Cerrar|Pasar/ })).toBeNull();
    expect(screen.getByText('Sin responder')).toBeTruthy();
  });
});

describe('la cobertura', () => {
  it('sin nada aplicable no dice 0 %', async () => {
    await montar('active');
    const texto = await screen.findByText(/Cobertura:/);
    expect(texto.textContent).toContain('no hay artículos evaluados');
    expect(texto.textContent).not.toContain('0 %');
  });
});

describe('lo que la revisión del 19-sep encontró', () => {
  it('un doble clic en «Cerrar» no salta la confirmación', async () => {
    // El segundo clic cumplía `confirmando === estado` y cerraba la auditoría
    // sin que nadie leyera el aviso. Cerrar no tiene vuelta atrás.
    post.mockResolvedValue(auditoria('closed'));
    await montar('reporting');
    const boton = screen.getByRole('button', { name: 'Cerrar la auditoría' });

    await userEvent.dblClick(boton);

    expect(post).not.toHaveBeenCalled();
    expect(screen.getByRole('alertdialog')).toBeTruthy();
    expect(boton.hasAttribute('disabled')).toBe(true);
  });

  it('lo que se escribe mientras guarda no se pierde', async () => {
    let resolver: (v: unknown) => void = () => {};
    patch.mockImplementation(() => new Promise((r) => { resolver = r; }));
    await montar('active');

    await userEvent.type(screen.getByLabelText('Evidencia de la pregunta 1'), 'Falta firma');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    // Mientras viaja, el campo queda apagado: no se puede escribir sobre algo
    // que ya se mandó.
    expect((screen.getByLabelText('Evidencia de la pregunta 1') as HTMLInputElement).disabled).toBe(true);

    resolver({ ...pregunta, result: 'pending', notes: 'Falta firma' });
    await waitFor(() =>
      expect((screen.getByLabelText('Evidencia de la pregunta 1') as HTMLInputElement).disabled).toBe(false),
    );
    expect((screen.getByLabelText('Evidencia de la pregunta 1') as HTMLInputElement).value).toBe('Falta firma');
  });
});
