import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import type { Tenant } from '@ambienta/shared';
import { AspectosAmbientalesTable } from './AspectosAmbientalesTable';
import { CLASE_IMPRIMIENDO_DOCUMENTO } from '@/components/molecules';
import { AuditLogProvider } from '@/lib/audit-log-store';
import { DepartamentosProvider } from '@/lib/departamentos-store';
import { SessionProvider } from '@/lib/session';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import type { AspectoApi } from '@/lib/iso-store';
import { iniciarSesionComo } from '@/test/utils';

/**
 * La matriz de aspectos se exporta (ISO 14001 §6.1.2, tarea 73 de
 * `matrices-ambientales-iso-14001`): **lo filtrado, y diciendo el filtro**.
 * Y el filtro "No significativo" deja de incluir lo que nadie evaluó.
 */

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/aspectos-ambientales',
}));

const post = vi.fn();
vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return {
    ...real,
    api: {
      // El mapa de procesos: uno solo, para filtrar y para el formulario.
      get: vi.fn((url: string) =>
        Promise.resolve(
          url.startsWith('/processes')
            ? [{ id: 'pr1', tenant_id: 't', name: 'Chancado primario', process_type: 'operational' }]
            : [],
        ),
      ),
      post: (...a: unknown[]) => post(...a),
      patch: vi.fn(),
      delete: vi.fn(),
    },
  };
});

const editarAspecto = vi.fn();
vi.mock('@/lib/iso-store', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/iso-store')>();
  return {
    ...real,
    useIso: () => ({
      riesgos: [],
      crearAspecto: vi.fn(),
      editarAspecto: (...a: unknown[]) => editarAspecto(...a),
      borrarAspecto: vi.fn(),
      evaluarSignificancia: vi.fn(),
    }),
  };
});

const descargar = vi.fn();
vi.mock('@/lib/reports', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/reports')>();
  return { ...real, downloadTextFile: (...a: unknown[]) => descargar(...a) };
});

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <AuditLogProvider>
        <UsersProvider>
          <SessionProvider>
            <DepartamentosProvider>{children}</DepartamentosProvider>
          </SessionProvider>
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

const PLANTAS = [
  { id: 'p1', nombre: 'Planta Calama' },
  { id: 'p2', nombre: 'Faena Antofagasta' },
];

function aspecto(over: Partial<AspectoApi> & { id: string; actividad: string }): AspectoApi {
  return {
    facilityId: 'p1',
    procesoId: null,
    articleComplianceId: null,
    aspecto: 'Emisión de polvo',
    tipoImpacto: 'emision_atmosferica',
    condicionOperacion: 'normal',
    puntajeSeveridad: null,
    puntajeFrecuencia: null,
    puntajeLegal: null,
    puntajeTotal: null,
    significancia: 'pending',
    responsableId: null,
    ...over,
  };
}

const ASPECTOS = [
  aspecto({ id: 'a1', actividad: 'Chancado', significancia: 'significant', puntajeTotal: 56, procesoId: 'pr1' }),
  aspecto({ id: 'a2', actividad: 'Riego de caminos', significancia: 'not_significant', puntajeTotal: 6 }),
  aspecto({ id: 'a3', actividad: 'Bodega de aceites', facilityId: 'p2' }),
];

beforeEach(() => {
  vi.clearAllMocks();
  editarAspecto.mockResolvedValue(true);
  post.mockResolvedValue({});
  window.localStorage.clear();
  iniciarSesionComo('admin_empresa');
});

// `sinEmpresa` y no `montar(undefined)`: un `undefined` explicito activa el
// valor por defecto del parametro y la prueba montaba CON empresa.
function montar({ sinEmpresa = false }: { sinEmpresa?: boolean } = {}) {
  const tenant = sinEmpresa ? undefined : EMPRESA;
  return render(<AspectosAmbientalesTable aspectos={ASPECTOS} plants={PLANTAS} tenant={tenant} />, {
    wrapper,
  });
}

function filasDeLaTabla() {
  const tabla = screen.getByRole('table', { name: 'Aspectos ambientales identificados' });
  return within(tabla).getAllByRole('row').slice(1);
}

describe('el filtro "No significativo"', () => {
  it('no incluye lo que nadie evaluo', async () => {
    // Hasta el 21-sep excluia solo `significant`, asi que un aspecto `pending`
    // salia listado —y exportado— como "No significativo".
    montar();

    await userEvent.selectOptions(screen.getByLabelText('Significancia'), 'no');

    const filas = filasDeLaTabla();
    expect(filas).toHaveLength(1);
    expect(within(filas[0]).getByText('Riego de caminos')).toBeTruthy();
  });

  it('lo sin evaluar tiene su propio filtro', async () => {
    montar();

    await userEvent.selectOptions(screen.getByLabelText('Significancia'), 'pendiente');

    const filas = filasDeLaTabla();
    expect(filas).toHaveLength(1);
    expect(within(filas[0]).getByText('Bodega de aceites')).toBeTruthy();
  });
});

describe('exportar la matriz', () => {
  it('el CSV lleva lo filtrado, no la matriz entera', async () => {
    montar();
    await userEvent.selectOptions(screen.getByLabelText('Planta'), 'p2');

    await userEvent.click(screen.getByRole('button', { name: 'Exportar CSV' }));

    expect(descargar).toHaveBeenCalledOnce();
    const [nombre, csv] = descargar.mock.calls[0] as [string, string];
    expect(nombre).toMatch(/^matriz-aspectos-\d{4}-\d{2}-\d{2}\.csv$/);
    expect(csv).toContain('Bodega de aceites');
    expect(csv).not.toContain('Chancado');
    // Y queda anotado en el servidor, con el filtro (RNF-26).
    expect(post).toHaveBeenCalledWith(
      '/emisiones/',
      expect.objectContaining({ documento: 'matriz_de_aspectos', formato: 'csv', filas: 1 }),
      expect.anything(),
    );
    expect((post.mock.calls[0][1] as { filtros: string[] }).filtros[0]).toMatch(/^Filtrado: Planta: Faena Antofagasta/);
  });

  it('el documento cuelga de <body> y dice el filtro aplicado', async () => {
    montar();
    await userEvent.selectOptions(screen.getByLabelText('Planta'), 'p2');

    const documento = document.querySelector('body > .solo-impresion');
    expect(documento).not.toBeNull();
    expect(documento?.textContent).toContain('Matriz de aspectos e impactos ambientales');
    expect(documento?.textContent).toContain('Filtrado: Planta: Faena Antofagasta');
    expect(documento?.textContent).toContain('Muestra 1 de los 3 aspectos');
    expect(documento?.textContent).not.toContain('Chancado');
  });

  it('imprimir en esta pantalla es imprimir la matriz, tambien con Ctrl+P', () => {
    montar();

    window.dispatchEvent(new Event('beforeprint'));
    expect(document.body.classList.contains(CLASE_IMPRIMIENDO_DOCUMENTO)).toBe(true);
    window.dispatchEvent(new Event('afterprint'));
    expect(document.body.classList.contains(CLASE_IMPRIMIENDO_DOCUMENTO)).toBe(false);
  });

  it('sin la empresa emisora no hay PDF, y lo dice; el CSV sigue', () => {
    montar({ sinEmpresa: true });

    expect(screen.getByRole('button', { name: 'Exportar PDF' })).toBeDisabled();
    expect(screen.getByText(/falta cargar la empresa que emite el documento/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Exportar CSV' })).toBeEnabled();
    expect(document.querySelector('body > .solo-impresion')).toBeNull();
  });

  it('con un filtro que no deja nada, no se exporta un documento vacio', async () => {
    montar();
    await userEvent.selectOptions(screen.getByLabelText('Condición'), 'emergencia');

    expect(screen.getByRole('button', { name: 'Exportar PDF' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Exportar CSV' })).toBeDisabled();
  });
});

describe('la matriz por proceso', () => {
  it('muestra el proceso de cada aspecto, y lo sin proceso lo dice', async () => {
    montar();

    await screen.findAllByText('Chancado primario');
    const filas = filasDeLaTabla();
    expect(within(filas[0]).getByText('Chancado primario')).toBeTruthy();
    expect(within(filas[1]).getByText('Sin proceso')).toBeTruthy();
  });

  it('filtra por proceso', async () => {
    montar();
    await screen.findAllByText('Chancado primario');

    await userEvent.selectOptions(screen.getByLabelText('Proceso'), 'pr1');

    const filas = filasDeLaTabla();
    expect(filas).toHaveLength(1);
    expect(within(filas[0]).getByText('Chancado')).toBeTruthy();
  });

  it('filtra lo que no tiene proceso', async () => {
    montar();
    await screen.findAllByText('Chancado primario');

    await userEvent.selectOptions(screen.getByLabelText('Proceso'), 'ninguno');

    expect(filasDeLaTabla()).toHaveLength(2);
  });

  it('editar conserva el proceso: el formulario lo manda', async () => {
    // El formulario manda todos sus campos. Sin `process_id` entre los valores
    // iniciales, guardar cualquier cambio lo habria dejado en null.
    montar();
    await screen.findAllByText('Chancado primario');

    await userEvent.click(screen.getByRole('button', { name: 'Editar Chancado' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Guardar' }));

    expect(editarAspecto).toHaveBeenCalledOnce();
    expect(editarAspecto.mock.calls[0][1]).toMatchObject({ process_id: 'pr1' });
  });
});
