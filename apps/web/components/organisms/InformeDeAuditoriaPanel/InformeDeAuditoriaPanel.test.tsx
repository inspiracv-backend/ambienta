import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { InformeDeAuditoriaPanel } from './InformeDeAuditoriaPanel';
import { CLASE_IMPRIMIENDO_DOCUMENTO } from '@/components/molecules';
import { AuditLogProvider, useAuditLog } from '@/lib/audit-log-store';
import { SessionProvider } from '@/lib/session';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { iniciarSesionComo } from '@/test/utils';
import type { Tenant } from '@ambienta/shared';
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

const EMPRESA = {
  id: 'a0000000-0000-0000-0000-000000000001',
  nombre: 'Minera Andes SpA',
  identificacion: { tipo: 'RUT', numero: '76.111.111-1' },
  plants: [],
} as unknown as Tenant;

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
  render(<InformeDeAuditoriaPanel auditId="a-1" tenant={EMPRESA} />, { wrapper });
  // Aparece dos veces: en el panel y en el documento imprimible.
  await screen.findAllByText('Gestión de residuos');
}

describe('los ceros que no son ceros', () => {
  it('sin nada evaluado dice "Sin evaluar", no 0 %', async () => {
    await montar();
    expect(screen.getAllByText('Sin evaluar').length).toBeGreaterThan(0);
    expect(screen.queryByText('0 %')).not.toBeInTheDocument();
  });

  it('sin tasa de cierre dice por qué, en vez de 0 %', async () => {
    await montar();
    expect(screen.getAllByText(/La auditoría anterior no dejó hallazgos/).length).toBeGreaterThan(0);
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

describe('una auditoría cerrada', () => {
  it('no ofrece editar el veredicto: la API lo rechaza con 409', async () => {
    // Desde el 19-sep `POST/PATCH /audits/{id}/procesos` responde 409 en una
    // auditoría cerrada. Dejar el botón sería ofrecer algo que falla siempre.
    get.mockImplementation((url: string) => {
      if (url.endsWith('/informe')) return Promise.resolve({ ...INFORME, estado: 'closed' });
      if (url.endsWith('/procesos')) return Promise.resolve(veredictos);
      return Promise.resolve([]);
    });
    await montar();

    expect(screen.queryByRole('button', { name: /veredicto/i })).not.toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it('con la auditoría abierta sí lo ofrece', async () => {
    await montar();
    expect(screen.getByRole('button', { name: /veredicto/i })).toBeInTheDocument();
  });
});

describe('el informe como documento entregable', () => {
  it('se imprime con las mismas cifras que muestra el panel', async () => {
    // Si el documento armara sus propias cifras, lo entregado a un certificador
    // y lo que muestra el sistema podrían decir cosas distintas.
    window.print = vi.fn();
    get.mockImplementation((url: string) => {
      if (url.endsWith('/informe')) {
        return Promise.resolve({
          ...INFORME,
          resumen: { ...INFORME.resumen, no_conformidades: 3, conformidad: 62.5 },
        });
      }
      if (url.endsWith('/procesos')) return Promise.resolve(veredictos);
      return Promise.resolve([]);
    });
    await montar();

    await userEvent.click(screen.getByRole('button', { name: 'Imprimir / Guardar PDF' }));

    expect(window.print).toHaveBeenCalledOnce();
    // El «62,5 %» sale dos veces: en el panel y en el documento.
    expect(screen.getAllByText('62,5 %').length).toBeGreaterThan(1);
    expect(screen.getByText(/Informe de auditoría — Auditoría interna/)).toBeTruthy();
  });

  it('sin la empresa emisora dice por que no se puede imprimir', async () => {
    // Paso de verdad el 20-sep en el navegador: la ficha no tenia la empresa
    // cargada, el boton desaparecia y la pantalla se leia como que el informe
    // no se podia emitir nunca. Callar no es lo mismo que no poder.
    iniciarSesionComo('admin_empresa');
    render(<InformeDeAuditoriaPanel auditId="a-1" />, { wrapper });
    await screen.findAllByText('Gestión de residuos');

    expect(screen.queryByRole('button', { name: 'Imprimir / Guardar PDF' })).toBeNull();
    expect(screen.getByText(/falta cargar la empresa que lo emite/)).toBeTruthy();
  });
});

describe('imprimir en la ficha es imprimir el informe', () => {
  function Historial() {
    const { entries } = useAuditLog();
    return (
      <ul aria-label="historial">
        {entries.map((e) => (
          <li key={e.id}>{e.resumen}</li>
        ))}
      </ul>
    );
  }

  async function montarConHistorial() {
    iniciarSesionComo('admin_empresa');
    render(
      <>
        <InformeDeAuditoriaPanel auditId="a-1" tenant={EMPRESA} />
        <Historial />
      </>,
      { wrapper },
    );
    await screen.findAllByText('Gestión de residuos');
  }

  it('el documento cuelga directo de <body>, que es lo que deja ocultar el resto', async () => {
    // La hoja de impresion oculta a los hermanos del documento. Anidado dentro
    // de la ficha no tendria hermanos que ocultar y el PDF saldria con toda la
    // pantalla delante, que es como salia.
    await montar();
    expect(document.querySelector('body > .solo-impresion')).not.toBeNull();
  });

  it('Ctrl+P hace lo mismo que el boton: marca la hoja y lo anota en el servidor', async () => {
    await montarConHistorial();

    // Ctrl+P no pasa por el boton: el navegador solo avisa con `beforeprint`.
    window.dispatchEvent(new Event('beforeprint'));

    expect(document.body.classList.contains(CLASE_IMPRIMIENDO_DOCUMENTO)).toBe(true);
    // **En el servidor y contra esta auditoria** (decision 9 del 21-sep): antes
    // quedaba en el historial de la sesion y se perdia al recargar.
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/emisiones/',
        expect.objectContaining({ documento: 'informe_de_auditoria', formato: 'pdf', entidad_tipo: 'audits', entidad_id: 'a-1' }),
        expect.objectContaining({ tenantId: expect.any(String) }),
      ),
    );

    window.dispatchEvent(new Event('afterprint'));
    expect(document.body.classList.contains(CLASE_IMPRIMIENDO_DOCUMENTO)).toBe(false);
  });
});

it('el pie del documento no dobla el punto despues de la hora', async () => {
  // Con reloj de 12 horas `es-CL` termina en «p. m.», y la frase agregaba el
  // suyo: «12:57:21 p. m..». Visto en el navegador el 21-sep.
  await montar();
  const pie = screen.getByText(/Documento generado por Ambienta/);
  expect(pie.textContent).not.toMatch(/\.\./);
});
