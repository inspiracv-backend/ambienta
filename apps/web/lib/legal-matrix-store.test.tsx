import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { LegalMatrixProvider, useLegalMatrix } from './legal-matrix-store';
import { AuditLogProvider } from './audit-log-store';
import { ToastProvider } from './toast-store';
import { SessionProvider } from './session';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/matriz-legal',
}));

// Sin respaldo de ejemplo: lo que se mida viene de la API o no viene.
vi.mock('@/mocks/catalog', () => ({ mockLegalNorms: [] }));

const get = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      patch: vi.fn(() => Promise.resolve({})),
      post: vi.fn(() => Promise.resolve({})),
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
            <LegalMatrixProvider>{children}</LegalMatrixProvider>
          </SessionProvider>
        </UsersProvider>
      </AuditLogProvider>
    </ToastProvider>
  );
}

const NORMA = 'e0000000-0000-0000-0000-000000000001';

/** Enruta cada llamada al conjunto que le corresponde. */
function responder(articulos: Record<string, unknown>[]) {
  get.mockImplementation((ruta: string) => {
    if (ruta.includes('/articles')) return Promise.resolve(articulos);
    if (ruta === '/catalog/norms') {
      return Promise.resolve([
        { id: NORMA, title: 'Ley 19.300', norm_type: 'ley', source_id: 1 },
      ]);
    }
    if (ruta === '/catalog/sources') {
      return Promise.resolve([{ id: 1, code: 'BCN_LEYCHILE' }]);
    }
    return Promise.resolve([]);
  });
}

async function montar(articulos: Record<string, unknown>[]) {
  iniciarSesionComo('admin_empresa');
  responder(articulos);
  const r = renderHook(() => useLegalMatrix(), { wrapper });
  await waitFor(() => expect(r.result.current.loading).toBe(false));
  await waitFor(() => expect(r.result.current.norms).toHaveLength(1));
  return r;
}

const articuloApi = (extra: Record<string, unknown> = {}) => ({
  id: 'f0000000-0000-0000-0000-000000000001',
  article_number: '11',
  heading: 'Estudio de impacto ambiental',
  content: 'Los proyectos enumerados requeriran un estudio...',
  display_order: 1,
  ...extra,
});

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe('carga del articulado', () => {
  it('trae los articulos de la API en vez de dejar la lista vacia', async () => {
    // El store armaba cada norma con `articulos: []`, asi que lo que se veia
    // salia de los datos de ejemplo y evaluar cumplimiento era imposible: no
    // habia articulo real contra el cual hacerlo.
    const { result } = await montar([articuloApi()]);

    expect(result.current.norms[0]!.articulos).toHaveLength(1);
    expect(result.current.norms[0]!.articulos[0]!.numero).toBe('11');
  });

  it('los pide al endpoint del articulado de esa norma', async () => {
    await montar([articuloApi()]);
    expect(get).toHaveBeenCalledWith(`/catalog/norms/${NORMA}/articles`);
  });

  it('entra sin evaluar, no como incumplido', async () => {
    // `N_E` y no `NO`: no haber evaluado un articulo no es incumplirlo, y
    // contarlo como incumplimiento hundiria el porcentaje de la empresa el dia
    // que se carga una norma nueva.
    const { result } = await montar([articuloApi()]);
    expect(result.current.norms[0]!.articulos[0]!.respuesta).toBe('N_E');
  });

  it('cae al texto del articulo cuando no tiene epigrafe', async () => {
    // `heading` es opcional en la base; `content` es NOT NULL. Sin este
    // respaldo el articulo apareceria en la lista sin nada escrito.
    const { result } = await montar([articuloApi({ heading: null })]);
    expect(result.current.norms[0]!.articulos[0]!.descripcion).toBe(
      'Los proyectos enumerados requeriran un estudio...',
    );
  });

  it('una norma sin articulado no rompe la pantalla', async () => {
    const { result } = await montar([]);
    expect(result.current.norms[0]!.articulos).toEqual([]);
    expect(result.current.norms[0]!.nombre).toBe('Ley 19.300');
  });
});
