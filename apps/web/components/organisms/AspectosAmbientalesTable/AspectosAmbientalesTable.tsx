'use client';

import { useMemo, useState } from 'react';
import { Inbox, Pencil, Plus, Trash2 } from 'lucide-react';
import { FEATURE_FLAGS } from '@ambienta/shared';
import { Button, StatusBadge } from '@/components/atoms';
import { FilterBar } from '@/components/molecules';
import { ConfirmarBorrado, FormularioIso, type CampoIso } from '@/components/organisms/IsoForms';
import { getUserName } from '@/lib/get-user-name';
import { aspectoSinTratar, useIso, type AspectoApi, type PlantaApi } from '@/lib/iso-store';

const CONDICION_LABEL: Record<string, string> = {
  normal: 'Normal',
  anormal: 'Anormal',
  emergencia: 'Emergencia',
};

/**
 * Traducciones de los tipos que vienen en clave.
 *
 * `impact_type` es texto libre en la base, así que la mayoría llega ya
 * legible. Esto sólo traduce los valores en clave que puedan quedar de los
 * datos de ejemplo; lo que no reconoce **se muestra crudo**, que es lo que
 * hace que alguien lo note.
 */
const TIPO_LABEL: Record<string, string> = {
  emision_atmosferica: 'Emisión atmosférica',
  vertido_agua: 'Vertido al agua',
  residuo_solido: 'Residuo sólido',
  residuo_peligroso: 'Residuo peligroso',
  consumo_agua: 'Consumo de agua',
  consumo_energia: 'Consumo de energía',
  ruido: 'Ruido',
  contaminacion_suelo: 'Contaminación de suelo',
  biodiversidad: 'Biodiversidad',
  gases_efecto_invernadero: 'GEI',
  otro: 'Otro',
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
function campos(plants: PlantaApi[]): CampoIso[] {
  return [
    {
      nombre: 'facility_id',
      etiqueta: 'Planta',
      tipo: 'select',
      requerido: true,
      opciones: plants.map((p) => ({ value: p.id, label: p.nombre })),
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
      opciones: Object.entries(CONDICION_LABEL).map(([value, label]) => ({ value, label })),
      ayuda: 'Un aspecto de emergencia se evalúa distinto que uno de rutina.',
    },
    {
      nombre: 'severity_score',
      etiqueta: 'Severidad',
      tipo: 'numero',
      min: 1,
      max: 10,
      ayuda: 'De 1 a 10. La base lo exige en ese rango.',
    },
    { nombre: 'frequency_score', etiqueta: 'Frecuencia', tipo: 'numero', min: 1, max: 10 },
    { nombre: 'legal_score', etiqueta: 'Requisito legal', tipo: 'numero', min: 1, max: 10 },
  ];
}

interface Props {
  aspectos: AspectoApi[];
  /** Las plantas **de la API**, con su id real. Ver `plantas` en `iso-store`. */
  plants: PlantaApi[];
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
export function AspectosAmbientalesTable({ aspectos, plants }: Props) {
  // El guard de la flag va DESPUES de los hooks: React exige que todo hook se
  // llame en el mismo orden en cada render, y un `return` antes los vuelve
  // condicionales.
  const [plantaFiltro, setPlantaFiltro] = useState('todas');
  const [condicionFiltro, setCondicionFiltro] = useState('todas');
  const [significativoFiltro, setSignificativoFiltro] = useState('todos');
  const [editando, setEditando] = useState<AspectoApi | null>(null);
  const [creando, setCreando] = useState(false);
  const [borrando, setBorrando] = useState<AspectoApi | null>(null);

  const { riesgos, crearAspecto, editarAspecto, borrarAspecto } = useIso();

  const filtered = useMemo(
    () =>
      aspectos.filter((a) => {
        if (plantaFiltro !== 'todas' && a.facilityId !== plantaFiltro) return false;
        if (condicionFiltro !== 'todas' && a.condicionOperacion !== condicionFiltro) return false;
        if (significativoFiltro === 'si' && a.significancia !== 'significant') return false;
        if (significativoFiltro === 'no' && a.significancia === 'significant') return false;
        if (significativoFiltro === 'sin_tratar' && !aspectoSinTratar(a, riesgos)) return false;
        return true;
      }),
    [aspectos, riesgos, plantaFiltro, condicionFiltro, significativoFiltro],
  );

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
              id: 'filtro-condicion',
              label: 'Condición',
              value: condicionFiltro,
              onChange: setCondicionFiltro,
              options: [
                { value: 'todas', label: 'Todas' },
                { value: 'normal', label: 'Normal' },
                { value: 'anormal', label: 'Anormal' },
                { value: 'emergencia', label: 'Emergencia' },
              ],
            },
            {
              id: 'filtro-significativo',
              label: 'Significancia',
              value: significativoFiltro,
              onChange: setSignificativoFiltro,
              options: [
                { value: 'todos', label: 'Todos' },
                { value: 'si', label: 'Significativo' },
                { value: 'no', label: 'No significativo' },
                { value: 'sin_tratar', label: 'Significativo sin tratar' },
              ],
            },
          ]}
        />
        <Button
          onClick={() => setCreando(true)}
          icon={<Plus className="h-4 w-4" aria-hidden />}
        >
          Nuevo aspecto
        </Button>
      </div>

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
                  <td className="px-4 py-3 font-medium text-slate-900">{a.actividad}</td>
                  <td className="px-4 py-3 text-slate-700">{a.aspecto}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {TIPO_LABEL[a.tipoImpacto] ?? a.tipoImpacto}
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
                      {CONDICION_LABEL[a.condicionOperacion] ?? a.condicionOperacion}
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
        campos={campos(plants)}
        onGuardar={crearAspecto}
      />

      <FormularioIso
        open={editando !== null}
        onOpenChange={(v) => !v && setEditando(null)}
        titulo="Editar aspecto ambiental"
        campos={campos(plants)}
        valores={
          editando && {
            facility_id: editando.facilityId,
            activity: editando.actividad,
            aspect: editando.aspecto,
            impact_type: editando.tipoImpacto,
            operating_condition: editando.condicionOperacion,
            severity_score: editando.puntajeSeveridad,
            frequency_score: editando.puntajeFrecuencia,
            legal_score: editando.puntajeLegal,
          }
        }
        onGuardar={(d) => (editando ? editarAspecto(editando.id, d) : Promise.resolve(false))}
      />

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
