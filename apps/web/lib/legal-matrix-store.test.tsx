import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { LegalMatrixProvider, useLegalMatrix } from './legal-matrix-store';
import { AuditLogProvider } from './audit-log-store';
import { ToastProvider } from './toast-store';
import { SessionProvider } from './session';
import { UsersProvider } from './users-store';
import { ApiError } from './api-client';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/matriz-legal',
}));

// Sin respaldo de ejemplo: lo que se mida viene de la API o no viene.
vi.mock('@/mocks/catalog', () => ({ mockLegalNorms: [] }));

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      patch: (...a: unknown[]) => patch(...a),
      post: (...a: unknown[]) => post(...a),
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

const ARTICULO = 'f0000000-0000-0000-0000-000000000001';
const MATRIX_NORM = 'a1000000-0000-0000-0000-000000000001';
const AC = 'ac000000-0000-0000-0000-000000000001';

/** Enruta cada llamada al conjunto que le corresponde. */
function responder(
  articulos: Record<string, unknown>[],
  evaluaciones: Record<string, unknown>[] = [],
  matrixNorms: Record<string, unknown>[] = [{ id: MATRIX_NORM, norm_id: NORMA }],
) {
  get.mockImplementation((ruta: string) => {
    if (ruta.includes('/articles')) return Promise.resolve(articulos);
    if (ruta.startsWith('/compliance/article-compliance')) return Promise.resolve(evaluaciones);
    if (ruta.startsWith('/compliance/matrix-norms')) return Promise.resolve(matrixNorms);
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

async function montar(
  articulos: Record<string, unknown>[],
  evaluaciones: Record<string, unknown>[] = [],
  matrixNorms?: Record<string, unknown>[],
) {
  iniciarSesionComo('admin_empresa');
  responder(articulos, evaluaciones, matrixNorms);
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
  post.mockResolvedValue({ id: AC });
  patch.mockResolvedValue({});
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

describe('cruce con la evaluación de la empresa', () => {
  it('muestra la respuesta guardada en vez de dejar todo sin evaluar', async () => {
    // El segundo engaño de esta pantalla: la evaluación se guardaba en
    // `article_compliance` y la lectura no la miraba, así que al recargar todo
    // volvía a "sin evaluar".
    const { result } = await montar(
      [articuloApi()],
      [{ id: AC, article_id: ARTICULO, compliance_status: 'compliant' }],
    );

    expect(result.current.norms[0]!.articulos[0]!.respuesta).toBe('SI');
  });

  it('lee `partial` como NO cumple, nunca como cumple', async () => {
    /**
     * La interfaz no modela cumplimiento parcial. Darlo por cumplido
     * sobreestimaría el porcentaje de la empresa ante un auditor, así que la
     * dirección conservadora es la única defendible.
     */
    const { result } = await montar(
      [articuloApi()],
      [{ id: AC, article_id: ARTICULO, compliance_status: 'partial' }],
    );

    expect(result.current.norms[0]!.articulos[0]!.respuesta).toBe('NO');
  });

  it('evaluar por primera vez crea la fila, no la edita', async () => {
    // Sin evaluación previa no hay `ac_id` contra el cual hacer PATCH: la
    // primera evaluación es un alta.
    const { result } = await montar([articuloApi()], []);

    act(() => result.current.updateArticulo(NORMA, ARTICULO, { respuesta: 'SI' }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    const [ruta, cuerpo] = post.mock.calls[0]!;
    expect(ruta).toBe('/compliance/article-compliance');
    expect((cuerpo as Record<string, unknown>).matrix_norm_id).toBe(MATRIX_NORM);
    expect((cuerpo as Record<string, unknown>).compliance_status).toBe('compliant');
  });

  it('reevaluar usa /evaluate sobre la evaluación existente', async () => {
    const { result } = await montar(
      [articuloApi()],
      [{ id: AC, article_id: ARTICULO, compliance_status: 'pending' }],
    );

    act(() => result.current.updateArticulo(NORMA, ARTICULO, { respuesta: 'NO' }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(String(post.mock.calls[0]![0])).toContain(
      `/compliance/article-compliance/${AC}/evaluate`,
    );
    expect(String(post.mock.calls[0]![0])).toContain('answer=non_compliant');
  });

  it('avisa en vez de guardar si la norma no está en la matriz de la empresa', async () => {
    // Evaluar presupone haber decidido que la norma aplica. Guardar sin fila en
    // la matriz apuntaría a una relación que no existe.
    const { result } = await montar([articuloApi()], [], []);

    act(() => result.current.updateArticulo(NORMA, ARTICULO, { respuesta: 'SI' }));

    await waitFor(() => expect(result.current.norms[0]!.articulos[0]!.respuesta).toBe('N_E'));
    expect(post).not.toHaveBeenCalled();
  });

  it('revierte y avisa cuando la API rechaza la evaluación', async () => {
    const { result } = await montar([articuloApi()], []);
    post.mockRejectedValue(new Error('rechazado'));

    act(() => result.current.updateArticulo(NORMA, ARTICULO, { respuesta: 'SI' }));

    await waitFor(() => expect(result.current.norms[0]!.articulos[0]!.respuesta).toBe('N_E'));
  });
});


describe('qué artículos cuentan para el porcentaje (RF-24)', () => {
  it('un artículo sin nada guardado cuenta', async () => {
    /**
     * **Ausente es incluido.** Tratar "no dice nada" como excluido sacaría del
     * cálculo a todos los artículos que nadie tocó —o sea casi todos— y el
     * porcentaje quedaría calculado sobre un puñado de filas.
     */
    const { result } = await montar([articuloApi()], []);

    expect(result.current.norms[0]!.articulos[0]!.incluidoEnCalculo).toBe(true);
  });

  it('lee la exclusión guardada en `attributes`', async () => {
    const { result } = await montar(
      [articuloApi()],
      [
        {
          id: AC,
          article_id: ARTICULO,
          compliance_status: 'pending',
          attributes: { incluidoEnCalculo: false },
        },
      ],
    );

    expect(result.current.norms[0]!.articulos[0]!.incluidoEnCalculo).toBe(false);
  });

  it('excluir lo manda a la API, no se queda en pantalla', async () => {
    const { result } = await montar(
      [articuloApi()],
      [{ id: AC, article_id: ARTICULO, compliance_status: 'pending', attributes: {} }],
    );

    act(() => result.current.setIncluidoEnCalculo(NORMA, ARTICULO, false));

    await waitFor(() => expect(patch).toHaveBeenCalled());
    const [ruta, cuerpo] = patch.mock.calls[0]!;
    expect(ruta).toBe(`/compliance/article-compliance/${AC}`);
    expect((cuerpo as { attributes: Record<string, unknown> }).attributes.incluidoEnCalculo).toBe(
      false,
    );
  });

  it('fusiona con lo que ya estaba, no lo reemplaza', async () => {
    /**
     * `attributes` es un jsonb compartido. Mandar el objeto entero borraría lo
     * que escribieron otras pantallas, y el destrozo solo se vería al recargar
     * una tercera. Es el error que ya se corrigió en `tenants.settings`.
     */
    const { result } = await montar(
      [articuloApi()],
      [
        {
          id: AC,
          article_id: ARTICULO,
          compliance_status: 'pending',
          attributes: { motivoExclusion: 'no aplica a esta faena' },
        },
      ],
    );

    act(() => result.current.setIncluidoEnCalculo(NORMA, ARTICULO, false));

    await waitFor(() => expect(patch).toHaveBeenCalled());
    const enviado = (patch.mock.calls[0]![1] as { attributes: Record<string, unknown> })
      .attributes;
    expect(enviado.incluidoEnCalculo).toBe(false);
    expect(enviado.motivoExclusion).toBe('no aplica a esta faena');
  });

  it('sin evaluación previa la crea, en estado pendiente', async () => {
    /** Excluir no es evaluar: el artículo sigue sin responder. */
    const { result } = await montar([articuloApi()], []);

    act(() => result.current.setIncluidoEnCalculo(NORMA, ARTICULO, false));

    await waitFor(() => expect(post).toHaveBeenCalled());
    const cuerpo = post.mock.calls[0]![1] as Record<string, unknown>;
    expect(cuerpo.compliance_status).toBe('pending');
    expect((cuerpo.attributes as Record<string, unknown>).incluidoEnCalculo).toBe(false);
  });

  it('revierte y avisa cuando la API rechaza', async () => {
    const { result } = await montar(
      [articuloApi()],
      [{ id: AC, article_id: ARTICULO, compliance_status: 'pending', attributes: {} }],
    );
    patch.mockRejectedValue(
      new ApiError(422, 'Unprocessable Entity', { detail: 'jsonb invalido' }),
    );

    act(() => result.current.setIncluidoEnCalculo(NORMA, ARTICULO, false));

    await waitFor(() => expect(result.current.norms[0]!.articulos[0]!.incluidoEnCalculo).toBe(true));
  });
});

describe('generar una obligacion desde un articulo (RF-09, #110)', () => {
  const OBLIGACION = 'ob000000-0000-0000-0000-000000000001';

  it('la cuelga de la evaluacion, no del articulo del catalogo', async () => {
    // **La decision del vinculo, verificada donde se aplica.** El articulo del
    // catalogo es global —lo comparten todas las empresas— asi que una
    // obligacion colgada de el no diria de quien es. Se cuelga de
    // `article_compliance`, que si es de esta empresa y esta planta.
    const { result } = await montar([articuloApi()], [{ id: AC, article_id: ARTICULO }]);
    post.mockResolvedValue({ id: OBLIGACION, code: 'MTZ-0001' });

    await act(async () => {
      await result.current.generarObligacion(NORMA, ARTICULO, 'Declaracion anual');
    });

    expect(post).toHaveBeenCalledWith(
      `/compliance/article-compliance/${AC}/obligations`,
      { title: 'Declaracion anual' },
      expect.anything(),
    );
  });

  it('si el articulo no estaba evaluado, crea la evaluacion primero', async () => {
    // Sin esto el boton falla con un error tecnico sobre una fila que el
    // usuario no sabe que existe. La evaluacion nace en `pending`: generar una
    // obligacion no es responder el articulo.
    const { result } = await montar([articuloApi()], []);
    post
      .mockResolvedValueOnce({ id: AC })
      .mockResolvedValueOnce({ id: OBLIGACION, code: 'MTZ-0001' });

    await act(async () => {
      await result.current.generarObligacion(NORMA, ARTICULO, 'Declaracion anual');
    });

    expect(post).toHaveBeenNthCalledWith(
      1,
      '/compliance/article-compliance',
      expect.objectContaining({ matrix_norm_id: MATRIX_NORM, compliance_status: 'pending' }),
      expect.anything(),
    );
    expect(post).toHaveBeenNthCalledWith(
      2,
      `/compliance/article-compliance/${AC}/obligations`,
      expect.anything(),
      expect.anything(),
    );
  });

  it('no inventa nada si la norma no esta en la matriz de la empresa', async () => {
    // Sin `matrix_norm_id` no hay de donde colgar la evaluacion. Antes de esta
    // guarda saldria un 422 de la API con un mensaje que no dice que hacer.
    const { result } = await montar([articuloApi()], [], []);

    await expect(
      result.current.generarObligacion(NORMA, ARTICULO, 'Declaracion anual'),
    ).rejects.toThrow(/matriz legal/i);
    expect(post).not.toHaveBeenCalled();
  });

  it('propaga el fallo en vez de decir que se creo', async () => {
    // **Lo contrario de las demas escrituras de este store, y a proposito.**
    // Las otras son optimistas porque el resultado se ve en la misma pantalla;
    // aca el resultado es navegar a otra, y navegar hacia algo que no se creo
    // deja al usuario en un 404 sin explicacion.
    const { result } = await montar([articuloApi()], [{ id: AC, article_id: ARTICULO }]);
    post.mockRejectedValue(new ApiError(422, 'no corresponde a esta empresa'));

    await expect(
      result.current.generarObligacion(NORMA, ARTICULO, 'Declaracion anual'),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
