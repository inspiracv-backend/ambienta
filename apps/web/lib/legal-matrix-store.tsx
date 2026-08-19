'use client';

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { Articulo, LegalNorm, TipoDocumento } from '@ambienta/shared';
import { cuentaParaElCalculo, fusionarAttributes } from '@ambienta/shared';
import { mockLegalNorms } from '@/mocks/catalog';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { useToast } from '@/lib/toast-store';
import { api, mensajeDeError } from '@/lib/api-client';

interface LegalMatrixContextValue {
  norms: LegalNorm[];
  loading: boolean;
  updateArticulo: (normId: string, articuloId: string, updates: Partial<Articulo>) => void;
  setIncluidoEnCalculo: (normId: string, articuloId: string, incluido: boolean) => void;
  addNorm: (input: { nombre: string; tipoDocumento: TipoDocumento; fuente: 'RCA' | 'ISO'; tenantId: string; plantIds: string[] }) => void;
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
  const [norms, setNorms] = useState<LegalNorm[]>(mockLegalNorms);
  const [loading, setLoading] = useState(true);
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
        .get<Record<string, unknown>[]>('/facilities/', { tenantId: user!.tenantId })
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
    ): Promise<Map<string, Articulo[]>> {
      const mapa = new Map<string, Articulo[]>();
      const porNorma = await Promise.all(
        normas.map((n) =>
          api
            .get<Record<string, unknown>[]>(`/catalog/norms/${n.id}/articles`)
            .then((filas) => ({ norma: String(n.id), filas }))
            // Una norma sin articulado no puede tumbar la pantalla entera.
            .catch(() => ({ norma: String(n.id), filas: [] as Record<string, unknown>[] })),
        ),
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
     */
    async function evaluacionesPorArticulo(): Promise<
      Map<string, { ac: string; estado: string; forma?: string; responsableId?: string; attributes?: Record<string, unknown> }>
    > {
      const filas = await api
        .get<Record<string, unknown>[]>('/compliance/article-compliance', {
          tenantId: user!.tenantId,
        })
        .catch(() => []);
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
        .get<Record<string, unknown>[]>('/compliance/matrix-norms', {
          tenantId: user!.tenantId,
        })
        .catch(() => []);
      return new Map(
        filas.map((f) => [String(f.norm_id), String(f.id)] as [string, string]),
      );
    }

    Promise.all([
      api.get<Record<string, unknown>[]>('/catalog/norms'),
      plantasPorNorma(),
      // Las normas traen `source_id`, no el codigo. Sin esta lista no hay forma
      // de saber si una norma es de la BCN, una ISO o una RCA de la empresa.
      api.get<Record<string, unknown>[]>('/catalog/sources').catch(() => []),
    ])
      .then(async ([data, porNorma, fuentes]) => {
        if (cancelled) return;

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

        const articulosPorNorma = await articulosDeLasNormas(data, evaluaciones);
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
        }));
        if (mapped.length > 0) setNorms(mapped);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
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
   * **Esto todavía no llega a la base, pero el bloqueo se redujo a la mitad.**
   *
   * Los dos identificadores que exige `POST /catalog/norms` **ya se pueden
   * resolver**: `GET /catalog/countries` existe, y `legal_sources` sí tiene
   * códigos `ISO` y `RCA` (los siembra `db/03_seed_catalogos.sql`), así que
   * `fuente` mapea directo. La versión anterior de esta nota decía que las
   * fuentes eran solo organismos —`BCN`, `SMA`, `RETC`— y estaba equivocada.
   *
   * **El bloqueo real es otro, y es de diseño.** `legal_norms` es un catálogo
   * global **sin `tenant_id`, a propósito**: su propio comentario en el esquema
   * dice que la norma es la misma para todos los tenants y que lo que se
   * registra por empresa es la aplicabilidad y el cumplimiento.
   *
   * Una RCA **no** es la misma para todos: es de una empresa. Dejar que esta
   * pantalla escriba ahí publicaría la resolución de un cliente en el catálogo
   * que ven todos los demás. No es un `POST` que falte: hay que decidir dónde
   * vive la normativa propia de una empresa —columna `tenant_id` en
   * `legal_norms`, tabla aparte, o solo dentro de `matrix_norms`— y esa
   * decisión tiene consecuencias sobre RLS.
   */
  function addNorm(input: { nombre: string; tipoDocumento: TipoDocumento; fuente: 'RCA' | 'ISO'; tenantId: string; plantIds: string[] }) {
    const newNorm: LegalNorm = {
      id: `norm-${Date.now()}`,
      tenantId: input.tenantId,
      plantIds: input.plantIds,
      tipoDocumento: input.tipoDocumento,
      nombre: input.nombre,
      fuente: input.fuente,
      articulos: [],
    };
    setNorms((prev) => [...prev, newNorm]);

    registrar({
      entidadTipo: 'norma',
      entidadId: newNorm.id,
      entidadLabel: newNorm.nombre,
      tenantId: input.tenantId,
      accion: 'creado',
      resumen: `Agregó la norma al catálogo (${input.fuente})`,
      cambios: [
        { campo: 'Fuente', antes: null, despues: input.fuente },
        { campo: 'Plantas asignadas', antes: null, despues: String(input.plantIds.length) },
      ],
    });
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

  return (
    <LegalMatrixContext.Provider value={{ norms, loading, updateArticulo, setIncluidoEnCalculo, addNorm, setNormPlants }}>
      {children}
    </LegalMatrixContext.Provider>
  );
}

export function useLegalMatrix() {
  const ctx = useContext(LegalMatrixContext);
  if (!ctx) throw new Error('useLegalMatrix debe usarse dentro de <LegalMatrixProvider>');
  return ctx;
}
