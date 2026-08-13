'use client';

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { Articulo, LegalNorm, TipoDocumento } from '@ambienta/shared';
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

    Promise.all([
      api.get<Record<string, unknown>[]>('/catalog/norms'),
      plantasPorNorma(),
    ])
      .then(([data, porNorma]) => {
        if (cancelled) return;
        const mapped: LegalNorm[] = data.map((raw) => ({
          id: String(raw.id),
          tenantId: user.tenantId!,
          plantIds: porNorma.get(String(raw.id)) ?? [],
          tipoDocumento: 'ley' as TipoDocumento,
          nombre: String(raw.title ?? raw.norm_number ?? ''),
          fuente: 'RCA' as const,
          articulos: [],
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
   * **Esto no llega a la base, y es el hueco más grande de esta pantalla.**
   *
   * La API sí tiene dónde guardarlo: `/compliance/article-compliance` con su
   * `/evaluate`. El problema es que **este store nunca carga artículos** — la
   * lectura arma cada norma con `articulos: []` y lo que se ve en pantalla sale
   * de `mockLegalNorms`. Sin artículos reales no hay `ac_id` contra el cual
   * evaluar.
   *
   * Conectarlo no es agregar un `PATCH`: hay que cargar la matriz de
   * cumplimiento de la empresa, sus normas y sus artículos, y recién ahí
   * evaluar. Es el cambio que más valor tiene pendiente en la matriz legal.
   */
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

  function setIncluidoEnCalculo(normId: string, articuloId: string, incluido: boolean) {
    updateArticulo(normId, articuloId, { incluidoEnCalculo: incluido });
  }

  /**
   * **Esto todavía no llega a la base, pero el bloqueo se redujo a la mitad.**
   *
   * `POST /catalog/norms` exige `country_id` y `source_id`.
   *
   * - `country_id` **ya se puede resolver**: `GET /catalog/countries` existe
   *   desde el 13-ago-2026.
   * - `source_id` sigue sin resolverse, y **no es que falte el endpoint**: es
   *   que la pantalla y la base hablan de cosas distintas. Acá `fuente` es
   *   `'RCA' | 'ISO'` —de dónde nace la obligación— y en la base `legal_sources`
   *   son organismos: `BCN`, `SMA`, `RETC`.
   *
   * Poner `BCN` por defecto sería lo fácil y sería falso: atribuiría a la
   * fuente oficial una norma que alguien escribió a mano. Hace falta decidir si
   * se siembra una fuente "carga manual" o si la pantalla pasa a preguntar el
   * organismo.
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
