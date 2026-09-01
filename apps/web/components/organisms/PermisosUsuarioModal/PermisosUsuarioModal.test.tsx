import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { User } from '@ambienta/shared';
import { ToastProvider } from '@/lib/toast-store';
import { PermisosUsuarioModal } from './PermisosUsuarioModal';

/**
 * La pantalla de permisos habla el vocabulario de la API (#217, RF-12).
 *
 * ## Lo que esto impide
 *
 * Esta pantalla listaba 13 permisos escritos a mano que **no compartían ni una
 * clave** con los 39 que la guarda verifica, y no guardaba: `updatePermisos`
 * solo tocaba el estado local mientras el aviso decía *"el cambio quedó en su
 * historial"*. Marcar casillas no restringía a nadie.
 *
 * Las dos pruebas que sostienen el arreglo son
 * `pinta lo que devolvio la API` y `manda el codigo TAL CUAL`: entre las dos
 * cierran el camino por el que podría reaparecer una traducción en el medio.
 */

const get = vi.fn();
const put = vi.fn();
const del = vi.fn();

vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return {
    ...real,
    api: {
      get: (...args: unknown[]) => get(...args),
      post: vi.fn(),
      patch: vi.fn(),
      put: (...args: unknown[]) => put(...args),
      delete: (...args: unknown[]) => del(...args),
    },
  };
});

const CATALOGO = [
  { codigo: 'audit.read', modulo: 'audit', descripcion: 'Ver auditorías' },
  { codigo: 'legal_matrix.article.evaluate', modulo: 'legal_matrix', descripcion: 'Evaluar artículos' },
];

const PERMISOS = {
  user_id: 'u-1',
  permisos: [{ codigo: 'audit.read', modulo: 'audit', descripcion: 'Ver auditorías', origen: 'rol' }],
  denegados: [] as string[],
};

// Solo lo que el modal lee. El resto del tipo no participa de esta pantalla.
const USUARIA = {
  id: 'u-1',
  tenantId: 't-1',
  nombre: 'Ana Rivas',
  email: 'ana@empresa.cl',
  role: 'usuario_interno',
} as unknown as User;

function montar() {
  return render(
    <ToastProvider>
      <PermisosUsuarioModal open onOpenChange={() => {}} user={USUARIA} />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  get.mockImplementation((path: string) =>
    path === '/permissions/' ? Promise.resolve(CATALOGO) : Promise.resolve(PERMISOS),
  );
  put.mockResolvedValue(PERMISOS);
  del.mockResolvedValue(PERMISOS);
});

describe('el catálogo viene de la API', () => {
  it('pinta lo que devolvio la API, con su codigo a la vista', async () => {
    montar();

    // El texto sale de `permissions.description`, no de una lista propia.
    expect(await screen.findByText('Evaluar artículos')).toBeInTheDocument();
    // Y el código se muestra: es lo que hay que citar cuando alguien pregunta
    // por qué le llegó un 403.
    expect(screen.getByText('legal_matrix.article.evaluate')).toBeInTheDocument();
  });

  it('un permiso que la API no devolvio NO aparece', async () => {
    montar();
    await screen.findByText('Evaluar artículos');

    // Las claves del catálogo viejo no pueden reaparecer por ningún camino.
    expect(screen.queryByText(/matriz_legal/)).not.toBeInTheDocument();
    expect(screen.queryByText('Evaluar artículos de la matriz')).not.toBeInTheDocument();
  });

  it('distingue lo que da el rol de lo que no', async () => {
    montar();
    expect(await screen.findByText('Del rol')).toBeInTheDocument();
  });
});

describe('las escrituras van con el vocabulario real', () => {
  it('manda el codigo TAL CUAL, sin traducir', async () => {
    const usuario = userEvent.setup();
    montar();
    await screen.findByText('Evaluar artículos');

    await usuario.type(screen.getByLabelText(/Motivo del cambio/i), 'cubre vacaciones');
    const fila = screen.getByText('legal_matrix.article.evaluate').closest('div');
    await usuario.click(within(fila!).getByRole('button', { name: 'Conceder' }));

    await waitFor(() => expect(put).toHaveBeenCalled());
    const [ruta, cuerpo] = put.mock.calls[0] as [string, { codigo: string }];
    expect(ruta).toContain('legal_matrix.article.evaluate');
    expect(cuerpo.codigo).toBe('legal_matrix.article.evaluate');
  });

  it('sin motivo no deja conceder', async () => {
    montar();
    await screen.findByText('Evaluar artículos');

    // El backend exige el motivo: si la pantalla dejara intentarlo, el error
    // llegaría como un fallo genérico y nadie sabría que faltaba escribirlo.
    const fila = screen.getByText('legal_matrix.article.evaluate').closest('div');
    expect(within(fila!).getByRole('button', { name: 'Conceder' })).toBeDisabled();
  });
});

describe('cuando la API falla no se inventa nada', () => {
  it('no dibuja una matriz vacia, que se leeria como "no tiene permisos"', async () => {
    get.mockRejectedValue(new Error('sin red'));
    montar();

    expect(await screen.findByText('No se pudieron cargar los permisos.')).toBeInTheDocument();
    expect(screen.getByText(/Puede seguir teniéndolos todos/)).toBeInTheDocument();
    expect(screen.queryByText('Ver auditorías')).not.toBeInTheDocument();
    expect(screen.getByText('Sin datos de permisos')).toBeInTheDocument();
  });
});
