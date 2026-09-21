'use client';

import { useMemo, useState } from 'react';
import { FileSpreadsheet, FileText, Inbox, Pencil, Plus, Scale, Trash2 } from 'lucide-react';
import { FEATURE_FLAGS, type Tenant } from '@ambienta/shared';
import { Button, StatusBadge } from '@/components/atoms';
import { DocumentoImprimible, FilterBar } from '@/components/molecules';
import { ReporteImprimible } from '@/components/organisms/ReporteImprimible';
import { ConfirmarBorrado, FormularioIso, type CampoIso } from '@/components/organisms/IsoForms';
import { EvaluarSignificanciaModal } from '@/components/organisms/EvaluarSignificanciaModal';
import { useNombreDeUsuario } from '@/lib/get-user-name';
import { aspectoSinTratar, useIso, type AspectoApi, type PlantaApi } from '@/lib/iso-store';
import { CONDICION_OPERACION, TIPO_IMPACTO, etiqueta, opciones } from '@/lib/iso-vocabulario';
import { buildMatrizAspectosReport, downloadTextFile } from '@/lib/reports';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { useDepartamentos } from '@/lib/departamentos-store';

/** Las opciones del filtro de significancia. **"No significativo" no incluye lo
    sin evaluar**: hasta el 21-sep si lo incluia, y un aspecto que nadie
    evaluo salia listado —y exportado— bajo "No significativo". */
const FILTRO_SIGNIFICANCIA: Record<string, string> = {
  si: 'Significativo',
  no: 'No significativo',
  pendiente: 'Sin evaluar',
  sin_tratar: 'Significativo sin tratar',
};

/**
 * Los campos que la base guarda, y **ninguno más**.
 *
 * `packages/shared` define el aspecto con `etapaCicloVida`, el impacto como
 * texto libre y la lista de riesgos vinculados. Nada de eso existe en
 * `environmental_aspects`. Ofrecerlos sería dejar que alguien los escriba, vea
 * "guardado" y los pierda al recargar — que ya pasó en este repositorio con
 * `evidence_url` y es la forma más silenciosa de perder un dato.
 */
function campos(plants: PlantaApi[], procesos: { id: string; nombre: string }[]): CampoIso[] {
  return [
    {
      nombre: 'facility_id',
      etiqueta: 'Planta',
      tipo: 'select',
      requerido: true,
      opciones: plants.map((p) => ({ value: p.id, label: p.nombre })),
    },
    {
      // **Opcional**: un aspecto puede ser de la planta entera y no de un
      // proceso. Forzarlo inventaria una pertenencia (el mismo criterio que
      // `audit_items.process_id`, `db/26`).
      nombre: 'process_id',
      etiqueta: 'Proceso',
      tipo: 'select',
      opciones: procesos.map((p) => ({ value: p.id, label: p.nombre })),
      ayuda: 'El proceso del mapa de procesos al que pertenece la actividad.',
    },
    {
      nombre: 'activity',
      etiqueta: 'Actividad',
      tipo: 'texto',
      requerido: true,
      ayuda: 'La actividad concreta. Ej.: lavado de equipos de envasado.',
    },
    {
      nombre: 'aspect',
      etiqueta: 'Aspecto',
      tipo: 'texto',
      requerido: true,
      ayuda: 'Qué interactúa con el ambiente. Ej.: vertido de agua con detergente.',
    },
    {
      nombre: 'impact_type',
      etiqueta: 'Tipo de impacto',
      // **Texto y no desplegable.** `impact_type` es `varchar(120)` sin CHECK:
      // texto libre. Los datos que ya existen dicen "Contaminación
      // atmosférica", no `emision_atmosferica`, así que un desplegable cerrado
      // le cambiaría el valor a cualquier fila que alguien abriera a editar
      // —en silencio, y sin que la persona lo pidiera—.
      tipo: 'texto',
      requerido: true,
      ayuda: 'Ej.: contaminación atmosférica, agotamiento del recurso hídrico.',
    },
    {
      nombre: 'operating_condition',
      etiqueta: 'Condición de operación',
      tipo: 'select',
      requerido: true,
      opciones: opciones(CONDICION_OPERACION),
      ayuda: 'Un aspecto de emergencia se evalúa distinto que uno de rutina.',
    },
  ];
}

interface Props {
  aspectos: AspectoApi[];
  /** Las plantas **de la API**, con su id real. Ver `plantas` en `iso-store`. */
  plants: PlantaApi[];
  /** La empresa que emite la matriz exportada. Sin ella no hay PDF: un documento
      sin quien lo emite no sirve para entregar. */
  tenant?: Tenant;
}

/**
 * Matriz de aspectos ambientales (ISO 14001 §6.1.2).
 *
 * ## Lo que esta pantalla no hacía
 *
 * Leía `mocks/` **directamente**, sin una sola llamada a la API. Filtrabas
 * datos de ejemplo y no había forma de crear, editar ni borrar nada — mientras
 * la API tenía CRUD completo desde hacía tiempo.
 *
 * ## El filtro que importa
 *
 * "Sin tratar" es un aspecto **significativo** que no está ligado a ningún
 * requisito legal ni a ningún riesgo. Es el hallazgo más común en una auditoría
 * de 14001: la empresa identificó el problema y no hizo nada. Por eso es un
 * filtro y no una columna — se busca, no se mira de pasada.
 */
export function AspectosAmbientalesTable({ aspectos, plants, tenant }: Props) {
  // Nombres de las personas reales; antes todo responsable salía «Sin asignar».
  const getUserName = useNombreDeUsuario();
  // El guard de la flag va DESPUES de los hooks: React exige que todo hook se
  // llame en el mismo orden en cada render, y un `return` antes los vuelve
  // condicionales.
  const [plantaFiltro, setPlantaFiltro] = useState('todas');
  const [condicionFiltro, setCondicionFiltro] = useState('todas');
  const [procesoFiltro, setProcesoFiltro] = useState('todos');
  const [significativoFiltro, setSignificativoFiltro] = useState('todos');
  const [editando, setEditando] = useState<AspectoApi | null>(null);
  const [creando, setCreando] = useState(false);
  const [borrando, setBorrando] = useState<AspectoApi | null>(null);
  const [evaluando, setEvaluando] = useState<AspectoApi | null>(null);

  const { riesgos, crearAspecto, editarAspecto, borrarAspecto } = useIso();
  const { departamentos: procesos } = useDepartamentos();
  const nombreDeProceso = (id: string | null) =>
    // Un proceso que no esta en la lista —retirado, o de un mapa que no cargo—
    // se muestra con su id: escondido tras un guion pareceria "sin proceso".
    id === null ? null : (procesos.find((p) => p.id === id)?.nombre ?? id);

  const filtered = useMemo(
    () =>
      aspectos.filter((a) => {
        if (plantaFiltro !== 'todas' && a.facilityId !== plantaFiltro) return false;
        if (condicionFiltro !== 'todas' && a.condicionOperacion !== condicionFiltro) return false;
        if (procesoFiltro === 'ninguno' && a.procesoId !== null) return false;
        if (procesoFiltro !== 'todos' && procesoFiltro !== 'ninguno' && a.procesoId !== procesoFiltro)
          return false;
        if (significativoFiltro === 'si' && a.significancia !== 'significant') return false;
        if (significativoFiltro === 'no' && a.significancia !== 'not_significant') return false;
        if (significativoFiltro === 'pendiente' && a.significancia !== 'pending') return false;
        if (significativoFiltro === 'sin_tratar' && !aspectoSinTratar(a, riesgos)) return false;
        return true;
      }),
    [aspectos, riesgos, plantaFiltro, condicionFiltro, procesoFiltro, significativoFiltro],
  );

  const { user } = useSession();
  const registrar = useRegistrarAuditoria();

  // **Se exporta lo que se ve**, filtros incluidos, y el documento los nombra.
  const reporte = useMemo(() => {
    const filtros = [
      plantaFiltro !== 'todas' &&
        `Planta: ${plants.find((p) => p.id === plantaFiltro)?.nombre ?? plantaFiltro}`,
      procesoFiltro !== 'todos' &&
        `Proceso: ${
          procesoFiltro === 'ninguno'
            ? 'Sin proceso'
            : (procesos.find((p) => p.id === procesoFiltro)?.nombre ?? procesoFiltro)
        }`,
      condicionFiltro !== 'todas' && `Condición: ${etiqueta(CONDICION_OPERACION, condicionFiltro)}`,
      significativoFiltro !== 'todos' &&
        `Significancia: ${FILTRO_SIGNIFICANCIA[significativoFiltro] ?? significativoFiltro}`,
    ].filter((f): f is string => typeof f === 'string');
    return buildMatrizAspectosReport(filtered, {
      plantas: plants,
      procesos,
      riesgos,
      nombreDe: getUserName,
      filtros,
      total: aspectos.length,
    });
  }, [filtered, plants, procesos, riesgos, getUserName, plantaFiltro, condicionFiltro, procesoFiltro, significativoFiltro, aspectos.length]);

  function anotar(resumen: string) {
    if (!tenant) return;
    // Historial de esta sesion, no del servidor: ver `audit-log-store`.
    registrar({
      entidadTipo: 'tenant',
      entidadId: tenant.id,
      entidadLabel: tenant.nombre,
      tenantId: tenant.id,
      accion: 'exportado',
      resumen,
      cambios: [],
    });
  }

  function exportarCsv() {
    const fecha = new Date().toISOString().slice(0, 10);
    downloadTextFile(`matriz-aspectos-${fecha}.csv`, reporte.csv, 'text/csv;charset=utf-8');
    anotar(`Exportó la matriz de aspectos en CSV (${reporte.rows.length} aspectos)`);
  }

  const puedeImprimir = Boolean(tenant && user) && !reporte.empty;

  if (!FEATURE_FLAGS.matricesIso) return null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <FilterBar
          filters={[
            {
              id: 'filtro-planta-asp',
              label: 'Planta',
              value: plantaFiltro,
              onChange: setPlantaFiltro,
              options: [
                { value: 'todas', label: 'Todas las plantas' },
                ...plants.map((p) => ({ value: p.id, label: p.nombre })),
              ],
            },
            {
              id: 'filtro-proceso-asp',
              label: 'Proceso',
              value: procesoFiltro,
              onChange: setProcesoFiltro,
              options: [
                { value: 'todos', label: 'Todos los procesos' },
                ...procesos.map((p) => ({ value: p.id, label: p.nombre })),
                { value: 'ninguno', label: 'Sin proceso' },
              ],
            },
            {
              id: 'filtro-condicion',
              label: 'Condición',
              value: condicionFiltro,
              onChange: setCondicionFiltro,
              options: [{ value: 'todas', label: 'Todas' }, ...opciones(CONDICION_OPERACION)],
            },
            {
              id: 'filtro-significativo',
              label: 'Significancia',
              value: significativoFiltro,
              onChange: setSignificativoFiltro,
              options: [{ value: 'todos', label: 'Todos' }, ...opciones(FILTRO_SIGNIFICANCIA)],
            },
          ]}
        />
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => window.print()}
            disabled={!puedeImprimir}
            title={
              reporte.empty
                ? 'No hay aspectos que exportar con estos filtros.'
                : !tenant
                  ? 'Falta cargar la empresa que emite el documento.'
                  : undefined
            }
            icon={<FileText className="h-4 w-4" aria-hidden />}
          >
            Exportar PDF
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={exportarCsv}
            disabled={reporte.empty}
            icon={<FileSpreadsheet className="h-4 w-4" aria-hidden />}
          >
            Exportar CSV
          </Button>
          <Button
            onClick={() => setCreando(true)}
            icon={<Plus className="h-4 w-4" aria-hidden />}
          >
            Nuevo aspecto
          </Button>
        </div>
      </div>
      {!tenant && !reporte.empty && (
        // **Se dice por que no hay PDF**, en vez de dejar un boton apagado sin
        // explicacion (la misma leccion del informe de auditoria).
        <p className="text-xs text-slate-500">
          Para exportar en PDF falta cargar la empresa que emite el documento. El CSV sí está disponible.
        </p>
      )}
      {puedeImprimir && tenant && user && (
        <DocumentoImprimible
          onAntesDeImprimir={() =>
            anotar(`Abrió la impresión de la matriz de aspectos (${reporte.rows.length} aspectos)`)
          }
        >
          <ReporteImprimible
            tenant={tenant}
            usuario={user}
            reporte={reporte}
            subtitulo="ISO 14001 §6.1.2"
          />
        </DocumentoImprimible>
      )}

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 py-12 text-center text-slate-500">
          <Inbox className="h-8 w-8 text-slate-400" aria-hidden />
          {aspectos.length === 0 ? (
            <>
              <p className="text-sm font-medium text-slate-700">
                Todavía no hay aspectos identificados
              </p>
              <p className="text-sm">
                Nada de lo que veas acá es de ejemplo: si está en la tabla, está en la
                empresa.
              </p>
            </>
          ) : (
            <p className="text-sm">No hay aspectos que coincidan con los filtros.</p>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Aspectos ambientales identificados</caption>
            <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Proceso</th>
                <th className="px-4 py-3">Actividad</th>
                <th className="px-4 py-3">Aspecto</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Condición</th>
                <th className="px-4 py-3">Puntaje</th>
                <th className="px-4 py-3">Significativo</th>
                <th className="px-4 py-3">Responsable</th>
                <th className="px-4 py-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-slate-600">
                    {nombreDeProceso(a.procesoId) ?? <span className="text-slate-400">Sin proceso</span>}
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-900">{a.actividad}</td>
                  <td className="px-4 py-3 text-slate-700">{a.aspecto}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {etiqueta(TIPO_IMPACTO, a.tipoImpacto)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={
                        a.condicionOperacion === 'emergencia'
                          ? 'text-red-700'
                          : a.condicionOperacion === 'anormal'
                            ? 'text-amber-700'
                            : 'text-slate-600'
                      }
                    >
                      {etiqueta(CONDICION_OPERACION, a.condicionOperacion)}
                    </span>
                  </td>
                  <td className="px-4 py-3 tabular-nums text-slate-600">
                    {/* `null` es "sin evaluar", no cero. Un cero acá diría que
                        se evaluó y salió sin importancia, que es lo contrario. */}
                    {a.puntajeTotal ?? <span className="text-slate-400">Sin evaluar</span>}
                  </td>
                  <td className="px-4 py-3">
                    {a.significancia === 'significant' ? (
                      <div className="flex flex-wrap items-center gap-1.5">
                        <StatusBadge status="no_cumple" label="Significativo" />
                        {aspectoSinTratar(a, riesgos) && (
                          <span className="rounded-full bg-semaforo-parcial-bg px-2 py-0.5 text-xs font-medium text-semaforo-parcial">
                            Sin tratar
                          </span>
                        )}
                      </div>
                    ) : a.significancia === 'pending' ? (
                      <StatusBadge status="pendiente" label="Sin evaluar" />
                    ) : (
                      <StatusBadge status="cumple" label="No significativo" />
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {a.responsableId ? getUserName(a.responsableId) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`Evaluar significancia de ${a.actividad}`}
                        onClick={() => setEvaluando(a)}
                        icon={<Scale className="h-4 w-4" aria-hidden />}
                      >
                        Evaluar
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`Editar ${a.actividad}`}
                        onClick={() => setEditando(a)}
                        icon={<Pencil className="h-4 w-4" aria-hidden />}
                      >
                        Editar
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`Eliminar ${a.actividad}`}
                        onClick={() => setBorrando(a)}
                        icon={<Trash2 className="h-4 w-4" aria-hidden />}
                      >
                        Eliminar
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <FormularioIso
        open={creando}
        onOpenChange={setCreando}
        titulo="Nuevo aspecto ambiental"
        descripcion="La significancia la calcula el servidor con los puntajes y el umbral de la empresa."
        campos={campos(plants, procesos)}
        onGuardar={crearAspecto}
      />

      <FormularioIso
        open={editando !== null}
        onOpenChange={(v) => !v && setEditando(null)}
        titulo="Editar aspecto ambiental"
        campos={campos(plants, procesos)}
        valores={
          editando && {
            facility_id: editando.facilityId,
            process_id: editando.procesoId,
            activity: editando.actividad,
            aspect: editando.aspecto,
            impact_type: editando.tipoImpacto,
            operating_condition: editando.condicionOperacion,
          }
        }
        onGuardar={(d) => (editando ? editarAspecto(editando.id, d) : Promise.resolve(false))}
      />

      <EvaluarSignificanciaModal aspecto={evaluando} onOpenChange={() => setEvaluando(null)} />

      <ConfirmarBorrado
        open={borrando !== null}
        onOpenChange={(v) => !v && setBorrando(null)}
        queSeBorra={borrando ? `${borrando.actividad} — ${borrando.aspecto}` : ''}
        advertencia="Los riesgos que lo referencian quedarán sin su aspecto de origen."
        onConfirmar={() => (borrando ? borrarAspecto(borrando.id) : Promise.resolve(false))}
      />
    </div>
  );
}
