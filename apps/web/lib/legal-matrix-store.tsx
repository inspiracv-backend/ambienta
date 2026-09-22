'use client';

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { Articulo, LegalNorm, TipoDocumento } from '@ambienta/shared';
import { cuentaParaElCalculo, fusionarAttributes } from '@ambienta/shared';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { useToast } from '@/lib/toast-store';
import { api, mensajeDeError } from '@/lib/api-client';

interface LegalMatrixContextValue {
  norms: LegalNorm[];
  /** Las normas que están en la matriz de la empresa (`matrix_norms`), tengan o
      no planta asignada. Ver `normasVisibles`. */
  enMatriz: Set<string>;
  loading: boolean;
  /** Por que la lista esta vacia, si es que fallo (#208). `null` = se pregunto. */
  errorDeCarga: string | null;
  updateArticulo: (normId: string, articuloId: string, updates: Partial<Articulo>) => void;
  setIncluidoEnCalculo: (normId: string, articuloId: string, incluido: boolean) => void;
  generarObligacion: (
    normId: string,
    articuloId: string,
    titulo: string,
  ) => Promise<{ id: string; code: string }>;
  /** `false` si la API rechazó el alta: la lista no se toca y la pantalla lo dice. */
  addNorm: (input: { nombre: string; tipoDocumento: TipoDocumento; fuente: 'RCA' | 'ISO'; tenantId: string; plantIds: string[] }) => Promise<boolean>;
  setNormPlants: (normId: string, plantIds: string[]) => void;
}

const LegalMatrixContext = createContext<LegalMatrixContextValue | null>(null);

const RESPUESTA_LABEL: Record<NonNullable<Articulo['respuesta']>, string> = {
  SI: 'Cumple',
  NO: 'No cumple',
  NA: 'No aplica',
  N_E: 'Sin evaluar',
};

/**
 * El tipo y la fuente venían **escritos a mano** en el mapper: toda norma se
 * mostraba como `Ley` y `RCA del tenant`, sin mirar lo que devolvía la API.
 *
 * El efecto no era cosmético. De las 8 normas sembradas, **6 son de la BCN y
 * una es ISO**, y las tres aparecían como Resolución de Calificación Ambiental
 * de la propia empresa — es decir, la Ley 19.300 figuraba como un documento
 * interno. Y el filtro por tipo de la pantalla ("Pública / ISO interna / RCA")
 * quedaba inservible, porque todo caía en la misma casilla.
 */
const TIPO_POR_NORM_TYPE: Record<string, TipoDocumento> = {
  ley: 'Ley',
  decreto_supremo: 'Decreto',
  decreto: 'Decreto',
  resolucion: 'Resolucion',
  dfl: 'DFL',
  constitucion: 'Constitucion',
  circular: 'Circular',
  ordenanza: 'Ordenanza',
  nch: 'NCh',
};

/**
 * `article_compliance.compliance_status` ↔ la respuesta de la pantalla.
 *
 * **`partial` no tiene equivalente en la interfaz**, que solo modela
 * SI / NO / NA / sin evaluar. Se lee como `NO` y no como `SI` a propósito: en
 * una matriz de cumplimiento, dar por cumplido lo que la base dice que se
 * cumple *a medias* sobreestima el porcentaje de la empresa ante un auditor.
 * La dirección conservadora es la única defendible.
 *
 * El costo está anotado porque es real: si alguien reevalúa desde la pantalla
 * un artículo que estaba en `partial`, se guarda como `non_compliant` y el
 * matiz se pierde. Recuperarlo pide una quinta opción en la interfaz.
 */
/** `legal_norms.status` → la vigencia de la pantalla. `draft` es un proyecto. */
const VIGENCIA_POR_STATUS: Record<string, NonNullable<LegalNorm['vigencia']>['estado']> = {
  vigente: 'vigente',
  parcialmente_vigente: 'parcialmente_vigente',
  derogada: 'derogada',
  draft: 'proyecto',
  desconocida: 'desconocida',
};

/** `matrix_norms.applicability` → si la norma le aplica a la empresa. */
const APLICABILIDAD_POR_VALOR: Record<string, NonNullable<NonNullable<LegalNorm['aplicabilidad']>['estado']>> = {
  applicable: 'aplica',
  not_applicable: 'no_aplica',
  pending_analysis: 'por_analizar',
};

const RESPUESTA_POR_STATUS: Record<string, Articulo['respuesta']> = {
  compliant: 'SI',
  non_compliant: 'NO',
  partial: 'NO',
  not_applicable: 'NA',
  pending: 'N_E',
};
const STATUS_POR_RESPUESTA: Record<NonNullable<Articulo['respuesta']>, string> = {
  SI: 'compliant',
  NO: 'non_compliant',
  NA: 'not_applicable',
  N_E: 'pending',
};

/**
 * `legal_sources` distingue cuatro orígenes y la interfaz solo modela tres.
 * `INTERNAL` —normativa propia de la empresa— no tiene equivalente, y hoy no
 * hay ninguna norma que lo use. Se deja caer en 'RCA', que es el origen interno
 * más cercano, y queda anotado: si alguien empieza a cargar normativa interna,
 * esto necesita una cuarta opción de verdad.
 */
const FUENTE_POR_CODIGO: Record<string, LegalNorm['fuente']> = {
  BCN_LEYCHILE: 'BCN',
  BCN: 'BCN',
  ISO: 'ISO',
  RCA: 'RCA',
  INTERNAL: 'RCA',
};

export function LegalMatrixProvider({ children }: { children: ReactNode }) {
  const [norms, setNorms] = useState<LegalNorm[]>([]);
  const [loading, setLoading] = useState(true);
  const [datosDe, setDatosDe] = useState<string | null>(null);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const registrar = useRegistrarAuditoria();
  const { user } = useSession();
  const { mostrarToast } = useToast();

  /**
   * `planta:norma` → id de la asignación que las vincula.
   *
   * En un ref y no en estado: cambiarlo no tiene que repintar nada, y ponerlo
   * en `useState` desde dentro del efecto de carga dispararía otro render por
   * cada planta.
   */
  const asignacionesRef = useRef(new Map<string, string>());

  /** `articulo` → id de su evaluacion. Vacio mientras nadie la haya evaluado. */
  const evaluacionRef = useRef(new Map<string, string>());

  /** `norma` → id de esa norma **dentro de la matriz de esta empresa**. */
  const matrizNormaRef = useRef(new Map<string, string>());
  const [enMatriz, setEnMatriz] = useState<Set<string>>(() => new Set());

  /**
   * `articulo` → los `attributes` que ya tiene guardados su evaluación.
   *
   * Hace falta para **fusionar** en vez de reemplazar: sin esto, escribir
   * `incluidoEnCalculo` borraría cualquier otra clave que otra pantalla haya
   * dejado ahí, y el destrozo solo se vería al recargar una tercera.
   */
  const attributesRef = useRef(new Map<string, Record<string, unknown>>());

  useEffect(() => {
    if (!user?.tenantId) { setLoading(false); return; }
    let cancelled = false;

    /**
     * Qué normas le aplican a cada instalación.
     *
     * `plantIds` venía siempre vacío, y la pantalla filtra las normas por
     * `plantIds.some(...)`: con la lista vacía **ninguna norma cruzaba con
     * ninguna planta** y la matriz se veía vacía aunque el catálogo cargara
     * bien.
     *
     * Se pide una vez por instalación porque las asignaciones se exponen
     * anidadas bajo su planta y no hay listado transversal. Son 3 o 4
     * peticiones para una empresa típica; si algún día un cliente tiene
     * decenas de faenas, hace falta un endpoint que las devuelva juntas.
     */
    async function plantasPorNorma(): Promise<Map<string, string[]>> {
      const mapa = new Map<string, string[]>();
      const plantas = await api
        .getTodas<Record<string, unknown>>('/facilities/', { tenantId: user!.tenantId })
        .catch(() => []);
      const asignaciones = await Promise.all(
        plantas.map((p) =>
          api
            .get<Record<string, unknown>[]>(`/facilities/${p.id}/norms`, {
              tenantId: user!.tenantId,
            })
            .then((filas) =>
              filas.map((f) => ({
                planta: String(p.id),
                norma: String(f.norm_id),
                // El id **de la asignación**, que no es el de la norma ni el de
                // la planta. Es lo único con lo que se puede borrar el vínculo
                // después: la ruta de baja se direcciona por él.
                asignacion: String(f.id),
              })),
            )
            .catch(() => []),
        ),
      );
      for (const { planta, norma, asignacion } of asignaciones.flat()) {
        mapa.set(norma, [...(mapa.get(norma) ?? []), planta]);
        asignacionesRef.current.set(`${planta}:${norma}`, asignacion);
      }
      return mapa;
    }

    /**
     * El articulado de cada norma, indexado por norma.
     *
     * Va en una peticion por norma porque el articulo cuelga de una **version**
     * de la norma, no de la norma: no hay un listado plano que se pueda pedir
     * de una vez sin decidir por cual version. El endpoint resuelve la vigente.
     *
     * La evaluacion —el SI/NO/NA de la empresa— **no viene de aca**: esto es el
     * texto de la ley, que es igual para todos. Se cruza con `evaluaciones`,
     * que si es de la empresa. Un articulo que nadie evaluo queda en `N_E` y
     * no en `NO`: no haber evaluado no es incumplir.
     */
    async function articulosDeLasNormas(
      normas: Record<string, unknown>[],
      evaluaciones: Map<
        string,
        { ac: string; estado: string; forma?: string; responsableId?: string; attributes?: Record<string, unknown> }
      >,
      /**
       * De dónde salen los artículos. Por defecto el catálogo público.
       *
       * **La normativa propia va por otra ruta a propósito.** Medido el 10-sep:
       * `/catalog/norms/{id}/articles` sí devuelve hoy el articulado de una RCA
       * a su dueña, pero **por un efecto de borde** — `get_tenant_db` recibe su
       * sesión de `get_db` y FastAPI cachea las dependencias por request, así
       * que en un router con guarda de permisos la ruta «sin empresa» corre con
       * la empresa declarada. Está documentado en `deps.py::get_db`.
       *
       * Apoyarse en eso significaría que el día que el catálogo deje de llevar
       * esa guarda, las RCAs de la pantalla se quedan sin considerandos y nadie
       * relaciona una cosa con la otra.
       */
      ruta: (id: string) => string = (id) => `/catalog/norms/${id}/articles`,
      opts?: { tenantId: string },
    ): Promise<Map<string, Articulo[]>> {
      const mapa = new Map<string, Articulo[]>();
      const porNorma = await Promise.all(
        normas.map((n) => {
          const url = ruta(String(n.id));
          // `opts` se omite del todo cuando no hay, en vez de mandar
          // `undefined`: el catálogo público se sigue pidiendo exactamente
          // igual que antes de que esta función tuviera dos caminos.
          const pedido = opts
            ? api.get<Record<string, unknown>[]>(url, opts)
            : api.get<Record<string, unknown>[]>(url);
          return pedido
            .then((filas) => ({ norma: String(n.id), filas }))
            // Una norma sin articulado no puede tumbar la pantalla entera.
            .catch(() => ({ norma: String(n.id), filas: [] as Record<string, unknown>[] }));
        }),
      );
      for (const { norma, filas } of porNorma) {
        mapa.set(
          norma,
          filas.map((f) => {
            const evaluacion = evaluaciones.get(String(f.id));
            return {
              id: String(f.id),
              normId: norma,
              numero: String(f.article_number ?? ''),
              // `heading` es el epigrafe y puede venir vacio; el texto del
              // articulo es `content`, que es NOT NULL.
              descripcion: String(f.heading || f.content || ''),
              respuesta: RESPUESTA_POR_STATUS[evaluacion?.estado ?? ''] ?? 'N_E',
              ...(evaluacion?.forma ? { formaCumplimiento: evaluacion.forma } : {}),
              ...(evaluacion?.responsableId
                ? { responsableId: evaluacion.responsableId }
                : {}),
              // **Ausente es incluido.** Tratar "no dice nada" como excluido
              // sacaria del calculo a todos los articulos que nadie toco —o sea
              // casi todos— y el porcentaje quedaria sobre un punado de filas.
              incluidoEnCalculo: cuentaParaElCalculo(evaluacion?.attributes),
            };
          }),
        );
      }
      return mapa;
    }

    /**
     * Las evaluaciones de la empresa, indexadas por artículo.
     *
     * Esto es lo que separa el texto de la ley —igual para todos— de lo que
     * esta empresa respondió sobre él. Sin este cruce los artículos se
     * mostraban todos «sin evaluar» aunque la base tuviera las respuestas
     * guardadas, que es el segundo engaño de esta pantalla: la evaluación se
     * guardaba y la pantalla seguía mostrando el valor de siempre.
     *
     * También deja el `id` de la evaluación, que es contra el que se escribe:
     * `/article-compliance` se direcciona por la evaluación, no por el
     * artículo.
     *
     * **Todas las páginas, y sin respaldo vacío** (21-sep). Con `get` llegaban
     * las primeras 100 —la API corta ahí si no se le pide otra cosa— y en la
     * empresa de prueba **164 de 264 evaluaciones** se mostraban "sin evaluar".
     * Y si la petición fallaba, el `catch` devolvía una lista vacía: la matriz
     * entera aparecía sin evaluar. Las dos cosas le dicen a la empresa que
     * nadie miró lo que sí miró; ahora un fallo se informa como tal
     * (`errorDeCarga`). Además, escribir sobre una evaluación "perdida" creaba
     * otra en vez de corregir la que existía.
     */
    async function evaluacionesPorArticulo(): Promise<
      Map<string, { ac: string; estado: string; forma?: string; responsableId?: string; attributes?: Record<string, unknown> }>
    > {
      const filas = await api.getTodas<Record<string, unknown>>('/compliance/article-compliance', {
        tenantId: user!.tenantId,
      });
      const mapa = new Map<
        string,
        { ac: string; estado: string; forma?: string; responsableId?: string; attributes?: Record<string, unknown> }
      >();
      for (const f of filas) {
        mapa.set(String(f.article_id), {
          ac: String(f.id),
          estado: String(f.compliance_status ?? ''),
          ...(f.compliance_method ? { forma: String(f.compliance_method) } : {}),
          ...(f.responsible_user_id ? { responsableId: String(f.responsible_user_id) } : {}),
          // Crudo a proposito: lo que se necesita al escribir es lo que ESTA
          // guardado, para fusionar sobre eso. Normalizarlo aca perderia las
          // claves que este esquema todavia no conoce.
          attributes: (f.attributes ?? {}) as Record<string, unknown>,
        });
        attributesRef.current.set(
          String(f.article_id),
          (f.attributes ?? {}) as Record<string, unknown>,
        );
      }
      return mapa;
    }

    /**
     * `norma` → id de esa norma dentro de la matriz de la empresa.
     *
     * Hace falta para **crear** una evaluación: `article_compliance` no cuelga
     * de la norma del catálogo sino de la fila que la incorpora a la matriz de
     * este tenant. Una norma que la empresa no incorporó a su matriz no se
     * puede evaluar, y eso es correcto: evaluar presupone haber decidido que
     * le aplica.
     */
    async function matrizPorNorma(): Promise<Map<string, string>> {
      const filas = await api
        .getTodas<Record<string, unknown>>('/compliance/matrix-norms', {
          tenantId: user!.tenantId,
        })
        .catch(() => []);
      // De paso, **si le aplica**: la sincronizacion marca `not_applicable` lo
      // que dejo de corresponderle y lo conserva. Sin leerlo, la Ley 20.920 de
      // la empresa de prueba salia "Pendiente de evaluar · 61 sin evaluar": la
      // pantalla pedia evaluar una norma que ya no le aplica (21-sep).
      for (const f of filas) {
        aplicabilidadPorNorma.set(String(f.norm_id), {
          determinadaPor: f.inclusion_source === 'automatic' ? 'automatica' : 'manual',
          estado: APLICABILIDAD_POR_VALOR[String(f.applicability ?? '')] ?? 'por_analizar',
          ...(f.applicability_reason ? { criterio: String(f.applicability_reason) } : {}),
          actividadesEconomicas: [],
          aspectoAmbientalIds: [],
        });
      }
      return new Map(
        filas.map((f) => [String(f.norm_id), String(f.id)] as [string, string]),
      );
    }

    /**
     * La normativa propia de la empresa: sus RCAs y sus ISO.
     *
     * **Va en una llamada aparte porque `/catalog/norms` no la trae.** Esa ruta
     * responde el catálogo compartido; una RCA es de una empresa (`db/29`), y
     * sin esto una RCA recién cargada **desaparecía al recargar la pantalla** —
     * el defecto de medio viaje de ida y vuelta que este repositorio ya sufrió
     * con `limiteUsuarios`.
     *
     * Si falla se devuelve vacío y el catálogo público se muestra igual: un
     * error acá no puede dejar la matriz legal entera en blanco.
     */
    async function propiasDeLaEmpresa(): Promise<Record<string, unknown>[]> {
      return api
        .get<Record<string, unknown>[]>('/compliance/normativa-propia/', {
          tenantId: user!.tenantId,
        })
        .catch(() => []);
    }

    // **Con la empresa, desde el 21-sep.** Sin ella, en modo desarrollo la
    // peticion salia sin credencial y respondia 401: la matriz no cargaba.
    // Mandarla no duplica las normas propias porque la API filtra el catalogo
    // a lo publico (`catalog.py::list_norms`); antes no lo hacia, y con Clerk
    // —donde el token siempre trae la empresa— cada RCA salia dos veces.
    const conEmpresa = { tenantId: user.tenantId! };
    const aplicabilidadPorNorma = new Map<string, NonNullable<LegalNorm['aplicabilidad']>>();
    Promise.all([
      // Todas las páginas: el catálogo crece con cada sincronización de la
      // BCN, y una norma más allá de la número 100 desaparecería de la matriz.
      api.getTodas<Record<string, unknown>>('/catalog/norms', conEmpresa),
      plantasPorNorma(),
      // Las normas traen `source_id`, no el codigo. Sin esta lista no hay forma
      // de saber si una norma es de la BCN, una ISO o una RCA de la empresa.
      api.get<Record<string, unknown>[]>('/catalog/sources', conEmpresa).catch(() => []),
      propiasDeLaEmpresa(),
    ])
      .then(async ([publicas, porNorma, fuentes, propias]) => {
        if (cancelled) return;

        // **Se concatenan y no se mezclan por id.** Las dos listas son
        // disjuntas por construcción: `listar()` filtra `tenant_id IS NOT NULL`
        // y el catálogo filtra `tenant_id IS NULL` (lo prueba
        // `test_catalogo_es_solo_lo_publico.py`).
        const data = [...publicas, ...propias];

        const [evaluaciones, porNormaMatriz] = await Promise.all([
          evaluacionesPorArticulo(),
          matrizPorNorma(),
        ]);
        if (cancelled) return;

        // Se guardan para el camino de escritura: evaluar un articulo necesita
        // el id de su evaluacion, y crearla necesita el de la norma en la
        // matriz de esta empresa.
        const ids = new Map<string, string>();
        evaluaciones.forEach((v, articulo) => ids.set(articulo, v.ac));
        evaluacionRef.current = ids;
        matrizNormaRef.current = porNormaMatriz;
        setEnMatriz(new Set(porNormaMatriz.keys()));

        // Cada grupo por su propia ruta: el catálogo público es global y la
        // normativa propia exige declarar empresa. Ver el parámetro `ruta`.
        const [articulosPublicos, articulosPropios] = await Promise.all([
          // Con la empresa por la misma razon que el listado: sin ella, en
          // desarrollo cada articulado respondia 401 y las normas llegaban vacias.
          articulosDeLasNormas(publicas, evaluaciones, undefined, conEmpresa),
          articulosDeLasNormas(
            propias,
            evaluaciones,
            (id) => `/compliance/normativa-propia/${id}/articulos`,
            { tenantId: user.tenantId! },
          ),
        ]);
        const articulosPorNorma = articulosPublicos;
        articulosPropios.forEach((v, k) => articulosPorNorma.set(k, v));
        if (cancelled) return;

        const codigoPorFuente = new Map<string, string>(
          fuentes.map((f) => [String(f.id), String(f.code ?? '')] as [string, string]),
        );

        const mapped: LegalNorm[] = data.map((raw) => ({
          id: String(raw.id),
          tenantId: user.tenantId!,
          plantIds: porNorma.get(String(raw.id)) ?? [],
          tipoDocumento: TIPO_POR_NORM_TYPE[String(raw.norm_type ?? '')] ?? 'Ley',
          nombre: String(raw.title ?? raw.norm_number ?? ''),
          fuente: FUENTE_POR_CODIGO[codigoPorFuente.get(String(raw.source_id)) ?? ''] ?? 'RCA',
          articulos: articulosPorNorma.get(String(raw.id)) ?? [],
          // Vigencia y aplicabilidad (tarea 58 de ISO). Una norma derogada o que
          // dejo de aplicar se ve distinta de una vigente que aplica.
          ...(VIGENCIA_POR_STATUS[String(raw.status ?? '')]
            ? { vigencia: { estado: VIGENCIA_POR_STATUS[String(raw.status)]! } }
            : {}),
          ...(aplicabilidadPorNorma.has(String(raw.id))
            ? { aplicabilidad: aplicabilidadPorNorma.get(String(raw.id))! }
            : {}),
        }));
        // **Se escribe siempre, incluso vacio** (#208). El `if (length > 0)`
        // de antes no distinguia dos cosas muy distintas: que la API fallara
        // —donde quedarse con lo que hay es un respaldo razonable— y que
        // respondiera **cero filas**, donde quedarse con los datos de ejemplo
        // es mostrar algo que no existe.
        //
        // El `catch` sigue conservando lo ultimo conocido, asi que trabajar sin
        // backend levantado sigue funcionando: ahi la peticion falla, no
        // devuelve vacio.
        setNorms(mapped);
      })
      .catch((e: unknown) => {
        // **Se dice que fallo.** Con la lista vacia y sin mensaje, la
        // pantalla afirma 'no hay nada' cuando la verdad es 'no se pudo
        // preguntar' — la misma mentira de #208 en su otra forma.
        setErrorDeCarga(mensajeDeError(e));
      })
      .finally(() => { if (!cancelled) { setLoading(false); setDatosDe(user?.tenantId ?? null); } });
    return () => { cancelled = true; };
  // `user` completo y no solo su tenantId: el efecto lo usa adentro para las
  // peticiones anidadas, y depender de una parte deja la otra vieja.
  }, [user]);

  /**
   * Evalúa un artículo, y **crea la evaluación si es la primera vez**.
   *
   * `/compliance/article-compliance` no se direcciona por artículo sino por su
   * evaluación: la fila cruza `matrix_norm_id` con `article_id`, y esa fila
   * puede no existir. Evaluar por primera vez es un alta y reevaluar es una
   * edición, así que la función decide cuál de las dos según lo que encontró
   * al cargar.
   *
   * Una norma que la empresa no incorporó a su matriz no se puede evaluar, y
   * eso es correcto: evaluar presupone haber decidido que le aplica. En ese
   * caso se revierte y se dice, en vez de guardar contra una matriz que no
   * existe.
   */
  function guardarEvaluacion(
    normId: string,
    articuloId: string,
    nuevo: Articulo,
    anterior: Articulo,
  ) {
    if (!user?.tenantId) return;
    const opts = { tenantId: user.tenantId };

    function revertir(queFallo: string, error: unknown) {
      setNorms((prev) =>
        prev.map((n) =>
          n.id !== normId
            ? n
            : {
                ...n,
                articulos: n.articulos.map((a) => (a.id === articuloId ? anterior : a)),
              },
        ),
      );
      mostrarToast({ tipo: 'error', mensaje: queFallo, descripcion: mensajeDeError(error) });
    }

    const estado = STATUS_POR_RESPUESTA[nuevo.respuesta];
    const yaEvaluado = evaluacionRef.current.get(articuloId);

    if (yaEvaluado) {
      // `answer` viaja por query: el endpoint lo declara como parametro suelto,
      // no dentro de un cuerpo.
      const query = new URLSearchParams({ answer: estado });
      if (nuevo.formaCumplimiento) query.set('compliance_method', nuevo.formaCumplimiento);
      if (nuevo.evidenciaUrl) query.set('evidence_url', nuevo.evidenciaUrl);
      api
        .post(`/compliance/article-compliance/${yaEvaluado}/evaluate?${query}`, {}, opts)
        .catch((error) => revertir('No se pudo guardar la evaluación', error));
      return;
    }

    const matrixNormId = matrizNormaRef.current.get(normId);
    if (!matrixNormId) {
      revertir(
        'Esta norma no está en la matriz de la empresa',
        new Error('Agregala a la matriz legal antes de evaluar sus artículos.'),
      );
      return;
    }

    api
      .post<Record<string, unknown>>(
        '/compliance/article-compliance',
        {
          matrix_norm_id: matrixNormId,
          article_id: articuloId,
          compliance_status: estado,
          ...(nuevo.formaCumplimiento ? { compliance_method: nuevo.formaCumplimiento } : {}),
          ...(nuevo.responsableId ? { responsible_user_id: nuevo.responsableId } : {}),
        },
        opts,
      )
      // Se guarda el id recién creado: la próxima edición del mismo artículo
      // tiene que ser una edición y no otra alta, que chocaría contra el
      // UNIQUE de la tabla.
      .then((creada) => evaluacionRef.current.set(articuloId, String(creada.id)))
      .catch((error) => revertir('No se pudo guardar la evaluación', error));
  }

  function updateArticulo(normId: string, articuloId: string, updates: Partial<Articulo>) {
    const norm = norms.find((n) => n.id === normId);
    const anterior = norm?.articulos.find((a) => a.id === articuloId);

    setNorms((prev) =>
      prev.map((n) =>
        n.id !== normId
          ? n
          : { ...n, articulos: n.articulos.map((a) => (a.id === articuloId ? { ...a, ...updates } : a)) },
      ),
    );

    if (!norm || !anterior) return;

    const cambios = [];
    if (updates.respuesta !== undefined && updates.respuesta !== anterior.respuesta) {
      cambios.push({
        campo: 'Evaluación',
        antes: RESPUESTA_LABEL[anterior.respuesta],
        despues: RESPUESTA_LABEL[updates.respuesta],
      });
    }
    if (updates.formaCumplimiento !== undefined && updates.formaCumplimiento !== anterior.formaCumplimiento) {
      cambios.push({
        campo: 'Forma de cumplimiento',
        antes: anterior.formaCumplimiento || null,
        despues: updates.formaCumplimiento || null,
      });
    }
    if (updates.responsableId !== undefined && updates.responsableId !== anterior.responsableId) {
      cambios.push({ campo: 'Responsable', antes: anterior.responsableId ?? null, despues: updates.responsableId ?? null });
    }
    if (updates.evidenciaUrl !== undefined && updates.evidenciaUrl !== anterior.evidenciaUrl) {
      cambios.push({ campo: 'Evidencia', antes: anterior.evidenciaUrl ?? null, despues: updates.evidenciaUrl ?? null });
    }
    if (updates.incluidoEnCalculo !== undefined && updates.incluidoEnCalculo !== anterior.incluidoEnCalculo) {
      cambios.push({
        campo: 'Entra en el % de cumplimiento',
        antes: anterior.incluidoEnCalculo ? 'Sí' : 'No',
        despues: updates.incluidoEnCalculo ? 'Sí' : 'No',
      });
    }

    if (cambios.length === 0) return;

    const evaluado = updates.respuesta !== undefined && updates.respuesta !== anterior.respuesta;

    guardarEvaluacion(normId, articuloId, { ...anterior, ...updates }, anterior);

    registrar({
      entidadTipo: 'articulo',
      entidadId: articuloId,
      entidadLabel: `${anterior.numero} — ${norm.nombre}`,
      tenantId: norm.tenantId,
      accion: evaluado ? 'evaluado' : 'actualizado',
      resumen: evaluado
        ? `Evaluó el artículo como ${RESPUESTA_LABEL[updates.respuesta!].toLowerCase()}`
        : 'Actualizó la evaluación del artículo',
      cambios,
      ...(updates.formaCumplimiento ? { motivo: updates.formaCumplimiento } : {}),
    });
  }

  /**
   * Excluir o volver a incluir un artículo del porcentaje de cumplimiento
   * (RF-24).
   *
   * Vive en `article_compliance.attributes`, que es un jsonb. Se **fusiona,
   * nunca se reemplaza**: mandar el objeto entero borraría lo que escribieron
   * otras pantallas, y el destrozo solo se vería al recargar una tercera. Es
   * exactamente el error que ya se corrigió en `tenants.settings`.
   *
   * Si el artículo nunca se evaluó no hay fila que parchear, así que la
   * primera exclusión **crea** la evaluación en estado pendiente. Excluir no es
   * evaluar: el artículo sigue sin responder, solo deja de contar.
   */
  function setIncluidoEnCalculo(normId: string, articuloId: string, incluido: boolean) {
    const anterior = norms
      .find((n) => n.id === normId)
      ?.articulos.find((a) => a.id === articuloId);
    if (!anterior) return;

    setNorms((prev) =>
      prev.map((n) =>
        n.id !== normId
          ? n
          : {
              ...n,
              articulos: n.articulos.map((a) =>
                a.id === articuloId ? { ...a, incluidoEnCalculo: incluido } : a,
              ),
            },
      ),
    );

    registrar({
      entidadTipo: 'norma',
      entidadId: normId,
      entidadLabel: norms.find((n) => n.id === normId)?.nombre ?? normId,
      tenantId: user!.tenantId!,
      accion: 'actualizado',
      resumen: incluido
        ? 'Volvió a incluir el artículo en el cálculo'
        : 'Excluyó el artículo del cálculo',
      cambios: [
        {
          campo: 'Cuenta para el porcentaje',
          antes: anterior.incluidoEnCalculo ? 'Sí' : 'No',
          despues: incluido ? 'Sí' : 'No',
        },
      ],
    });

    guardarInclusion(normId, articuloId, incluido, anterior);
  }

  function guardarInclusion(
    normId: string,
    articuloId: string,
    incluido: boolean,
    anterior: Articulo,
  ) {
    if (!user?.tenantId) return;
    const opts = { tenantId: user.tenantId };

    function revertir(error: unknown) {
      setNorms((prev) =>
        prev.map((n) =>
          n.id !== normId
            ? n
            : {
                ...n,
                articulos: n.articulos.map((a) => (a.id === articuloId ? anterior : a)),
              },
        ),
      );
      mostrarToast({
        tipo: 'error',
        mensaje: 'No se pudo cambiar si el artículo cuenta para el cálculo',
        descripcion: mensajeDeError(error),
      });
    }

    // Ausente significa incluido, así que solo se escribe la exclusión. Guardar
    // `true` en miles de artículos que nadie tocó sería ruido.
    const parche = fusionarAttributes(attributesRef.current.get(articuloId), {
      incluidoEnCalculo: incluido,
    });
    attributesRef.current.set(articuloId, parche);

    const yaEvaluado = evaluacionRef.current.get(articuloId);
    if (yaEvaluado) {
      api
        .patch(`/compliance/article-compliance/${yaEvaluado}`, { attributes: parche }, opts)
        .catch(revertir);
      return;
    }

    const matrixNormId = matrizNormaRef.current.get(normId);
    if (!matrixNormId) {
      revertir(new Error('Agregala a la matriz legal antes de configurar sus artículos.'));
      return;
    }

    api
      .post<Record<string, unknown>>(
        '/compliance/article-compliance',
        {
          matrix_norm_id: matrixNormId,
          article_id: articuloId,
          // Pendiente: excluir no es evaluar. El artículo sigue sin responder.
          compliance_status: 'pending',
          attributes: parche,
        },
        opts,
      )
      .then((creada) => {
        if (creada?.id) evaluacionRef.current.set(articuloId, String(creada.id));
      })
      .catch(revertir);
  }

  /**
   * Genera una obligacion desde un articulo de la matriz (RF-09, #110).
   *
   * **Necesita que el articulo este evaluado**, porque la obligacion se cuelga
   * de `article_compliance` y no del articulo del catalogo — que es global y no
   * sabria de que empresa ni de que planta es. Si nadie lo evaluo todavia, se
   * crea la fila de evaluacion en estado `pending`: dejar que el boton falle
   * con un error tecnico seria peor que crear el registro que igual va a hacer
   * falta.
   *
   * No es optimista a proposito. Las demas escrituras de este store pintan el
   * cambio y revierten si la API falla, porque el usuario ve el resultado en la
   * misma pantalla. Aca el resultado es **otra pantalla** —el detalle de la
   * obligacion— y navegar hacia algo que quiza no existe deja al usuario en un
   * 404 sin saber por que.
   */
  async function generarObligacion(normId: string, articuloId: string, titulo: string) {
    if (!user?.tenantId) throw new Error('Sin sesion no se puede generar una obligacion.');
    const opts = { tenantId: user.tenantId };

    let evaluacion = evaluacionRef.current.get(articuloId);

    if (!evaluacion) {
      const matrixNormId = matrizNormaRef.current.get(normId);
      if (!matrixNormId) {
        throw new Error('Agregala a la matriz legal antes de generar obligaciones.');
      }
      const creada = await api.post<Record<string, unknown>>(
        '/compliance/article-compliance',
        { matrix_norm_id: matrixNormId, article_id: articuloId, compliance_status: 'pending' },
        opts,
      );
      evaluacion = String(creada.id);
      evaluacionRef.current.set(articuloId, evaluacion);
    }

    const obligacion = await api.post<Record<string, unknown>>(
      `/compliance/article-compliance/${evaluacion}/obligations`,
      { title: titulo },
      opts,
    );
    return { id: String(obligacion.id), code: String(obligacion.code) };
  }

  /**
   * Registra una RCA o una ISO de la empresa. **Ahora sí llega a la base.**
   *
   * ## Lo que la desbloqueó, y por qué esta nota decía otra cosa
   *
   * Durante semanas acá decía que el bloqueo era de diseño: `legal_norms` es un
   * catálogo global **sin `tenant_id`**, así que escribir una RCA ahí publicaba
   * la resolución de un cliente en el catálogo que ven todos los demás. Era
   * cierto — y **dejó de serlo el 8-sep**, cuando `db/29` agregó la columna, su
   * política de RLS y `/compliance/normativa-propia`. La nota se quedó vieja y
   * nadie volvió a mirarla: el mismo patrón que este repositorio persigue.
   *
   * ## Por qué NO va a `POST /catalog/norms`
   *
   * Esa ruta escribe el catálogo compartido y exige Admin Global. Lo que decide
   * si una norma es propia es **`tenant_id` y nada más**, no la fuente: el
   * catálogo público tiene una norma archivada bajo la fuente `RCA`
   * —`RE-574/2019`, sobre reporte al RETC— que es normativa general y no el
   * permiso de nadie.
   *
   * ## Devuelve si se guardó, y no toca la lista si falló
   *
   * Pintar la norma antes de saberlo es cómo se produce una pantalla que
   * confirma un cambio que la base nunca recibió. Es lo mismo que ya pasó con
   * `limiteUsuarios`, que se "guardaba" y se deshacía al recargar.
   */
  async function addNorm(input: {
    nombre: string;
    tipoDocumento: TipoDocumento;
    fuente: 'RCA' | 'ISO';
    tenantId: string;
    plantIds: string[];
  }): Promise<boolean> {
    let creada: Record<string, unknown>;
    try {
      creada = await api.post<Record<string, unknown>>(
        '/compliance/normativa-propia/',
        {
          fuente: input.fuente,
          // El tipo de la pantalla es el vocabulario del catálogo, en
          // minúsculas: `Resolucion` -> `resolucion`, `NCh` -> `nch`. Mandarlo
          // como se ve dejaría dos escrituras distintas del mismo valor.
          norm_type: input.tipoDocumento.toLowerCase(),
          title: input.nombre,
        },
        { tenantId: input.tenantId },
      );
    } catch (error) {
      mostrarToast({
        tipo: 'error',
        mensaje: 'No se pudo registrar el documento',
        descripcion: mensajeDeError(error),
      });
      return false;
    }

    const newNorm: LegalNorm = {
      id: String(creada.id),
      tenantId: input.tenantId,
      plantIds: [],
      tipoDocumento: input.tipoDocumento,
      nombre: input.nombre,
      fuente: input.fuente,
      // **Sin artículos, y eso es verdad.** Una RCA se registra primero y sus
      // considerandos se cargan después: RF-11 deja la extracción del PDF
      // fuera, y depende de `ai-service`, que es una carpeta vacía.
      articulos: [],
    };
    setNorms((prev) => [...prev, newNorm]);

    // Las plantas se asignan después del alta porque cuelgan de la norma ya
    // creada: `setNormPlants` es el mismo camino que usa la edición.
    if (input.plantIds.length > 0) {
      setNormPlants(newNorm.id, input.plantIds);
    }

    registrar({
      entidadTipo: 'norma',
      entidadId: newNorm.id,
      entidadLabel: newNorm.nombre,
      tenantId: input.tenantId,
      accion: 'creado',
      resumen: `Registró normativa propia de la empresa (${input.fuente})`,
      cambios: [
        { campo: 'Fuente', antes: null, despues: input.fuente },
        { campo: 'Plantas asignadas', antes: null, despues: String(input.plantIds.length) },
      ],
    });
    return true;
  }

  function setNormPlants(normId: string, plantIds: string[]) {
    const anterior = norms.find((n) => n.id === normId);
    if (!anterior || JSON.stringify(anterior.plantIds) === JSON.stringify(plantIds)) return;

    const previas = anterior.plantIds;
    setNorms((prev) => prev.map((n) => (n.id === normId ? { ...n, plantIds } : n)));

    if (user?.tenantId) {
      const agregadas = plantIds.filter((p) => !previas.includes(p));
      const quitadas = previas.filter((p) => !plantIds.includes(p));

      const escrituras = [
        ...agregadas.map((plantaId) =>
          api
            .post<Record<string, unknown>>(
              `/facilities/${plantaId}/norms`,
              { norm_id: normId },
              { tenantId: user.tenantId },
            )
            // Se guarda el id de la asignación recién creada: sin él, quitar
            // esta misma planta en la siguiente edición no tendría qué borrar.
            .then((fila) => asignacionesRef.current.set(`${plantaId}:${normId}`, String(fila.id))),
        ),
        ...quitadas.map((plantaId) => {
          const asignacionId = asignacionesRef.current.get(`${plantaId}:${normId}`);
          // Sin id conocido no se inventa una ruta: la asignación pudo venir de
          // los datos de ejemplo y no existir en la base.
          if (!asignacionId) return Promise.resolve();
          return api
            .delete(`/facilities/${plantaId}/norms/${asignacionId}`, { tenantId: user.tenantId })
            .then(() => asignacionesRef.current.delete(`${plantaId}:${normId}`));
        }),
      ];

      Promise.allSettled(escrituras).then((resultados) => {
        const fallidas = resultados.filter((r) => r.status === 'rejected');
        if (fallidas.length === 0) return;
        // Se vuelve al conjunto anterior completo. A diferencia de las
        // notificaciones, acá el estado es una lista y dejarla a medias
        // mostraría una asignación que la base no tiene.
        setNorms((prev) => prev.map((n) => (n.id === normId ? { ...n, plantIds: previas } : n)));
        mostrarToast({
          tipo: 'error',
          mensaje: 'No se pudo cambiar dónde aplica la norma',
          descripcion: mensajeDeError((fallidas[0] as PromiseRejectedResult).reason),
        });
      });
    }

    registrar({
      entidadTipo: 'norma',
      entidadId: normId,
      entidadLabel: anterior.nombre,
      tenantId: anterior.tenantId,
      accion: 'asignado',
      resumen: 'Cambió las plantas donde aplica la norma',
      cambios: [
        {
          campo: 'Plantas asignadas',
          antes: String(anterior.plantIds.length),
          despues: String(plantIds.length),
        },
      ],
    });
  }

  // **Mientras no se haya preguntado POR ESTA empresa, se sigue cargando.**
  // El efecto baja `loading` a `false` cuando todavia no hay sesion, y al
  // llegar el tenant no lo vuelve a subir: quedaba una ventana con la lista
  // vacia y `loading` en `false`, y las fichas afirmaban "No encontramos esto"
  // sobre algo que si existe, durante todo el viaje de red.
  const cargandoDeVerdad = loading || (!!user?.tenantId && datosDe !== user.tenantId);

  return (
    <LegalMatrixContext.Provider value={{ norms, enMatriz, loading: cargandoDeVerdad, errorDeCarga, updateArticulo, setIncluidoEnCalculo, generarObligacion, addNorm, setNormPlants }}>
      {children}
    </LegalMatrixContext.Provider>
  );
}

export function useLegalMatrix() {
  const ctx = useContext(LegalMatrixContext);
  if (!ctx) throw new Error('useLegalMatrix debe usarse dentro de <LegalMatrixProvider>');
  return ctx;
}
