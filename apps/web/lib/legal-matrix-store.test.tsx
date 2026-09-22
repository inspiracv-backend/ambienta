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
const getTodas = vi.fn();
const post = vi.fn();
const patch = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      // Los listados completos se leen con `getTodas`; aca responde lo mismo que `get`.
      getTodas: (...a: unknown[]) => getTodas(...a),
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
  // Por defecto responde lo mismo que `get`; las pruebas de listados completos lo separan.
  getTodas.mockImplementation((...a: unknown[]) => get(...a));
  post.mockResolvedValue({ id: AC });
  patch.mockResolvedValue({});
  window.localStorage.clear();
});

describe('las evaluaciones llegan todas', () => {
  it('una evaluacion que no viene en la primera pagina se ve evaluada', async () => {
    // La API corta en 100 si no se le pide otra cosa. Con `get`, la evaluacion
    // numero 101 no llegaba y el articulo se mostraba "sin evaluar" (21-sep:
    // 164 de 264 en la empresa de prueba). `get` responde aca como la primera
    // pagina de la API: sin esta evaluacion.
    const evaluacion = { id: AC, article_id: ARTICULO, compliance_status: 'compliant', attributes: {} };
    const original = getTodas.getMockImplementation()!;
    getTodas.mockImplementation((ruta: string, ...resto: unknown[]) =>
      ruta.startsWith('/compliance/article-compliance') ? Promise.resolve([evaluacion]) : original(ruta, ...resto),
    );

    const { result } = await montar([articuloApi()], []);

    expect(result.current.norms[0]!.articulos[0]!.respuesta).toBe('SI');
  });

  it('si no se pudieron leer, lo dice en vez de mostrar la matriz entera sin evaluar', async () => {
    // El respaldo vacio de antes pintaba cada articulo como "nadie lo miro".
    const original = getTodas.getMockImplementation()!;
    getTodas.mockImplementation((ruta: string, ...resto: unknown[]) =>
      ruta.startsWith('/compliance/article-compliance')
        ? Promise.reject(new ApiError(500, 'Internal Server Error', null))
        : original(ruta, ...resto),
    );
    iniciarSesionComo('admin_empresa');
    responder([articuloApi()]);

    const { result } = renderHook(() => useLegalMatrix(), { wrapper });

    await waitFor(() => expect(result.current.errorDeCarga).toBeTruthy());
    expect(result.current.norms.flatMap((n) => n.articulos).some((a) => a.respuesta === 'N_E')).toBe(false);
  });
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
    expect(get).toHaveBeenCalledWith(`/catalog/norms/${NORMA}/articles`, {
      tenantId: expect.any(String),
    });
  });

  it('el catalogo se pide con la empresa de la sesion', async () => {
    // Sin ella, en modo desarrollo respondia 401 y la matriz no cargaba. No
    // duplica las normas propias: la API filtra el catalogo a lo publico.
    await montar([articuloApi()]);
    const tenantId = (get.mock.calls.find((c) => c[0] === '/catalog/norms')?.[1] as { tenantId?: string } | undefined)
      ?.tenantId;
    expect(tenantId).toBeTruthy();
    expect(get).toHaveBeenCalledWith('/catalog/sources', { tenantId });
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
    post.mockRejectedValue(new ApiError(422, 'Unprocessable Entity', { detail: 'no corresponde a esta empresa' }));

    await expect(
      result.current.generarObligacion(NORMA, ARTICULO, 'Declaracion anual'),
    ).rejects.toBeInstanceOf(ApiError);
  });
});

/**
 * La normativa propia de la empresa (RF-10, S-12).
 *
 * Hasta el 10-sep `addNorm` **no llamaba a la API**: agregaba la norma al
 * arreglo en memoria y ahí quedaba. La pantalla decía "RCA · 0 artículo(s)" y
 * al recargar no estaba, que en un módulo de cumplimiento significa que alguien
 * cree tener registrada una resolución que el sistema no tiene.
 *
 * El bloqueo era real y dejó de serlo: `db/29` le dio `tenant_id` al catálogo
 * y `/compliance/normativa-propia` es el camino. La nota del código se quedó
 * vieja.
 */
const RCA = 'e0000000-0000-0000-0000-0000000000aa';

/** Como `responder`, pero con una RCA propia además del catálogo público. */
function responderConPropia(propias: Record<string, unknown>[] = []) {
  get.mockImplementation((ruta: string) => {
    if (ruta === '/compliance/normativa-propia/') return Promise.resolve(propias);
    if (ruta.startsWith('/compliance/normativa-propia/')) {
      return Promise.resolve([
        {
          id: 'f0000000-0000-0000-0000-0000000000aa',
          article_number: '5.2',
          heading: 'Caudal maximo',
          content: 'No podra captar mas de 30 l/s.',
          display_order: 1,
        },
      ]);
    }
    if (ruta.includes('/articles')) return Promise.resolve([]);
    if (ruta.startsWith('/compliance/article-compliance')) return Promise.resolve([]);
    if (ruta.startsWith('/compliance/matrix-norms')) return Promise.resolve([]);
    if (ruta === '/catalog/norms') {
      return Promise.resolve([{ id: NORMA, title: 'Ley 19.300', norm_type: 'ley', source_id: 1 }]);
    }
    if (ruta === '/catalog/sources') {
      return Promise.resolve([
        { id: 1, code: 'BCN_LEYCHILE' },
        { id: 3, code: 'RCA' },
      ]);
    }
    return Promise.resolve([]);
  });
}

describe('normativa propia de la empresa', () => {
  it('registra la RCA en la API y no solo en la pantalla', async () => {
    iniciarSesionComo('admin_empresa');
    responderConPropia();
    post.mockResolvedValue({ id: RCA, title: 'RCA 123/2024', norm_type: 'resolucion' });

    const { result } = renderHook(() => useLegalMatrix(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    // `loading` baja antes de que haya sesion: sin esperar la carga real, el
    // alta llegaba primero y la carga inicial la pisaba (rojo en CI el 19-sep).
    await waitFor(() => expect(result.current.norms.some((n) => n.id === NORMA)).toBe(true));

    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.addNorm({
        nombre: 'RCA 123/2024',
        tipoDocumento: 'Resolucion',
        fuente: 'RCA',
        tenantId: 'a0000000-0000-0000-0000-000000000001',
        plantIds: [],
      });
    });

    expect(ok).toBe(true);
    expect(post).toHaveBeenCalledWith(
      '/compliance/normativa-propia/',
      expect.objectContaining({ fuente: 'RCA', title: 'RCA 123/2024', norm_type: 'resolucion' }),
      expect.objectContaining({ tenantId: 'a0000000-0000-0000-0000-000000000001' }),
    );
    expect(result.current.norms.some((n) => n.id === RCA)).toBe(true);
  });

  it('NO va al catalogo publico: escribirla ahi la publicaria a todas las empresas', async () => {
    iniciarSesionComo('admin_empresa');
    responderConPropia();
    post.mockResolvedValue({ id: RCA });

    const { result } = renderHook(() => useLegalMatrix(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    // `loading` baja antes de que haya sesion: sin esperar la carga real, el
    // alta llegaba primero y la carga inicial la pisaba (rojo en CI el 19-sep).
    await waitFor(() => expect(result.current.norms.some((n) => n.id === NORMA)).toBe(true));
    await act(async () => {
      await result.current.addNorm({
        nombre: 'RCA de la empresa',
        tipoDocumento: 'Resolucion',
        fuente: 'RCA',
        tenantId: 'a0000000-0000-0000-0000-000000000001',
        plantIds: [],
      });
    });

    expect(post).not.toHaveBeenCalledWith('/catalog/norms', expect.anything(), expect.anything());
  });

  it('si la API la rechaza, no aparece en la lista', async () => {
    // Pintarla igual es como se produce una pantalla que confirma un registro
    // que la base nunca recibio — el defecto de `limiteUsuarios`.
    iniciarSesionComo('admin_empresa');
    responderConPropia();
    post.mockRejectedValue(new ApiError(422, 'Unprocessable Entity', { detail: 'fuente invalida' }));

    const { result } = renderHook(() => useLegalMatrix(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    // `loading` baja antes de que haya sesion: sin esperar la carga real, el
    // alta llegaba primero y la carga inicial la pisaba (rojo en CI el 19-sep).
    await waitFor(() => expect(result.current.norms.some((n) => n.id === NORMA)).toBe(true));

    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.addNorm({
        nombre: 'RCA que no se guarda',
        tipoDocumento: 'Resolucion',
        fuente: 'RCA',
        tenantId: 'a0000000-0000-0000-0000-000000000001',
        plantIds: [],
      });
    });

    expect(ok).toBe(false);
    // Por nombre y no por largo: la lista termina de cargar despues de que
    // `loading` baja (la sesion llega un instante mas tarde), asi que contar
    // antes y despues fallaba solo con la suite completa cargada.
    expect(result.current.norms.some((n) => n.nombre === 'RCA que no se guarda')).toBe(false);
  });

  it('al recargar, la RCA sigue ahi con su articulado', async () => {
    // **El otro medio viaje.** Conectar solo la escritura deja una RCA que se
    // guarda y desaparece al recargar: `/catalog/norms` no la trae, porque es
    // el catalogo compartido.
    iniciarSesionComo('admin_empresa');
    responderConPropia([
      { id: RCA, title: 'RCA 123/2024', norm_type: 'resolucion', source_id: 3, articulos: 1 },
    ]);

    const { result } = renderHook(() => useLegalMatrix(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    // `loading` baja antes de que haya sesion: sin esperar la carga real, el
    // alta llegaba primero y la carga inicial la pisaba (rojo en CI el 19-sep).
    await waitFor(() => expect(result.current.norms.some((n) => n.id === NORMA)).toBe(true));
    await waitFor(() => expect(result.current.norms).toHaveLength(2));

    const propia = result.current.norms.find((n) => n.id === RCA);
    expect(propia).toBeDefined();
    expect(propia!.fuente).toBe('RCA');
    expect(propia!.articulos).toHaveLength(1);
    expect(propia!.articulos[0]!.numero).toBe('5.2');
  });

  it('pide el articulado propio por su ruta, no por la del catalogo', async () => {
    // Depender de `/catalog/norms/{id}/articles` para una RCA funciona hoy por
    // un efecto de borde de las dependencias de FastAPI (ver `deps.py::get_db`),
    // y se caeria en silencio el dia que el catalogo cambie de guarda.
    iniciarSesionComo('admin_empresa');
    responderConPropia([
      { id: RCA, title: 'RCA 123/2024', norm_type: 'resolucion', source_id: 3, articulos: 1 },
    ]);

    const { result } = renderHook(() => useLegalMatrix(), { wrapper });
    await waitFor(() => expect(result.current.norms).toHaveLength(2));

    expect(get).toHaveBeenCalledWith(
      `/compliance/normativa-propia/${RCA}/articulos`,
      expect.objectContaining({ tenantId: expect.any(String) }),
    );
    expect(get).not.toHaveBeenCalledWith(`/catalog/norms/${RCA}/articles`);
  });
});
