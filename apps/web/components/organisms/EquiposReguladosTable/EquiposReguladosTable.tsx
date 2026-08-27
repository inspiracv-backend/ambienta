'use client';

import { useMemo, useState } from 'react';
import { Inbox, Pencil, Plus, Trash2 } from 'lucide-react';
import { FEATURE_FLAGS } from '@ambienta/shared';
import { Button, StatusBadge } from '@/components/atoms';
import { FilterBar } from '@/components/molecules';
import { ConfirmarBorrado, FormularioIso, type CampoIso } from '@/components/organisms/IsoForms';
import { fecha } from '@/lib/fechas';
import { useIso, type EquipoApi, type PlantaApi } from '@/lib/iso-store';
import { AUTORIDAD, ESTADO_EQUIPO, etiqueta, opciones } from '@/lib/iso-vocabulario';

/**
 * El tipo de equipo es **texto libre** en la base (`varchar(80)` sin CHECK).
 *
 * Se ofrece una lista de los habituales y se acepta cualquier otro: acotarlo a
 * un catálogo cerrado dejaría fuera equipos reales el primer día, y este no es
 * un campo del que dependa ninguna regla.
 */
const TIPOS_HABITUALES = [
  'caldera',
  'generador',
  'grupo_electrogeno',
  'estanque',
  'compresor',
  'otro',
];

const TIPO_LABEL: Record<string, string> = {
  caldera: 'Caldera',
  generador: 'Generador',
  grupo_electrogeno: 'Grupo electrógeno',
  estanque: 'Estanque',
  compresor: 'Compresor',
  otro: 'Otro',
};

function campos(plants: PlantaApi[]): CampoIso[] {
  return [
    {
      nombre: 'facility_id',
      etiqueta: 'Planta',
      tipo: 'select',
      requerido: true,
      opciones: plants.map((p) => ({ value: p.id, label: p.nombre })),
    },
    { nombre: 'name', etiqueta: 'Nombre', tipo: 'texto', requerido: true },
    {
      nombre: 'equipment_type',
      etiqueta: 'Tipo',
      // Texto y no desplegable, por lo mismo que arriba: la columna es
      // `varchar(80)` sin CHECK. Un desplegable cerrado prometeria una lista
      // que la base no tiene, y le cambiaria el valor a las filas existentes.
      tipo: 'texto',
      requerido: true,
      ayuda: `Habituales: ${TIPOS_HABITUALES.map((t) => TIPO_LABEL[t] ?? t).join(', ')}. Se acepta cualquier otro.`,
    },
    { nombre: 'brand', etiqueta: 'Marca', tipo: 'texto' },
    { nombre: 'model', etiqueta: 'Modelo', tipo: 'texto' },
    {
      nombre: 'registration_authority',
      etiqueta: 'Organismo',
      tipo: 'select',
      opciones: opciones(AUTORIDAD),
      ayuda: 'Ante quién está inscrito el equipo.',
    },
    { nombre: 'registration_number', etiqueta: 'N.º de inscripción', tipo: 'texto' },
    {
      nombre: 'registration_expires_at',
      etiqueta: 'Vence el',
      tipo: 'fecha',
      ayuda: 'Una inscripción vencida se marca en rojo en la tabla.',
    },
    {
      nombre: 'status',
      etiqueta: 'Estado',
      tipo: 'select',
      requerido: true,
      opciones: opciones(ESTADO_EQUIPO),
    },
  ];
}

interface Props {
  equipos: EquipoApi[];
  /** Las plantas **de la API**, con su id real. Ver `plantas` en `iso-store`. */
  plants: PlantaApi[];
}

/**
 * Equipos regulados y su inscripción ante el organismo que corresponda.
 *
 * Leía `mocks/` **directamente**, sin una sola llamada a la API, y no había
 * forma de crear, editar ni borrar nada.
 *
 * ## Lo que la tabla tiene que gritar
 *
 * **Una inscripción vencida.** Operar una caldera con la inscripción vencida es
 * una infracción por sí sola, independiente de lo que emita. Por eso va en rojo
 * y tiene su propio filtro, en vez de ser una fecha más en una celda.
 *
 * ## Lo que ya no muestra
 *
 * La columna "Operadores" salía de los datos de ejemplo:
 * `regulated_equipment` **no tiene** operadores habilitados, ni tabla que los
 * relacione. Se quitó en vez de dejarla vacía o inventarla — una columna que
 * siempre dice "—" enseña a ignorarla.
 */
export function EquiposReguladosTable({ equipos, plants }: Props) {
  const [plantaFiltro, setPlantaFiltro] = useState('todas');
  const [estadoFiltro, setEstadoFiltro] = useState('todos');
  const [vencimientoFiltro, setVencimientoFiltro] = useState('todos');
  const [creando, setCreando] = useState(false);
  const [editando, setEditando] = useState<EquipoApi | null>(null);
  const [borrando, setBorrando] = useState<EquipoApi | null>(null);

  const { crearEquipo, editarEquipo, borrarEquipo } = useIso();

  const hoy = new Date().toISOString().slice(0, 10);

  const filtered = useMemo(
    () =>
      equipos.filter((e) => {
        if (plantaFiltro !== 'todas' && e.facilityId !== plantaFiltro) return false;
        if (estadoFiltro !== 'todos' && e.estado !== estadoFiltro) return false;
        if (
          vencimientoFiltro === 'vencida' &&
          !(e.inscripcionVence && e.inscripcionVence < hoy)
        ) {
          return false;
        }
        if (vencimientoFiltro === 'sin_inscripcion' && e.numeroInscripcion) return false;
        return true;
      }),
    [equipos, plantaFiltro, estadoFiltro, vencimientoFiltro, hoy],
  );

  if (!FEATURE_FLAGS.matricesIso) return null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <FilterBar
          filters={[
            {
              id: 'filtro-planta-eq',
              label: 'Planta',
              value: plantaFiltro,
              onChange: setPlantaFiltro,
              options: [
                { value: 'todas', label: 'Todas las plantas' },
                ...plants.map((p) => ({ value: p.id, label: p.nombre })),
              ],
            },
            {
              id: 'filtro-estado-eq',
              label: 'Estado',
              value: estadoFiltro,
              onChange: setEstadoFiltro,
              options: [{ value: 'todos', label: 'Todos' }, ...opciones(ESTADO_EQUIPO)],
            },
            {
              id: 'filtro-inscripcion-eq',
              label: 'Inscripción',
              value: vencimientoFiltro,
              onChange: setVencimientoFiltro,
              options: [
                { value: 'todos', label: 'Todas' },
                { value: 'vencida', label: 'Vencida' },
                { value: 'sin_inscripcion', label: 'Sin inscribir' },
              ],
            },
          ]}
        />
        <Button onClick={() => setCreando(true)} icon={<Plus className="h-4 w-4" aria-hidden />}>
          Nuevo equipo
        </Button>
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 py-12 text-center text-slate-500">
          <Inbox className="h-8 w-8 text-slate-400" aria-hidden />
          {equipos.length === 0 ? (
            <>
              <p className="text-sm font-medium text-slate-700">Todavía no hay equipos</p>
              <p className="text-sm">
                Nada de lo que veas acá es de ejemplo: si está en la tabla, está en la
                empresa.
              </p>
            </>
          ) : (
            <p className="text-sm">No hay equipos que coincidan con los filtros.</p>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Equipos regulados</caption>
            <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Nombre</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Marca / Modelo</th>
                <th className="px-4 py-3">Inscripción</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((e) => {
                const vencida = !!e.inscripcionVence && e.inscripcionVence < hoy;
                return (
                  <tr key={e.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-slate-900">{e.nombre}</td>
                    <td className="px-4 py-3 text-slate-600">
                      {TIPO_LABEL[e.tipo] ?? e.tipo}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {[e.marca, e.modelo].filter(Boolean).join(' ') || '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {e.numeroInscripcion ? (
                        <span>
                          {etiqueta(AUTORIDAD, e.autoridad)} — {e.numeroInscripcion}
                          {e.inscripcionVence && (
                            <span className={vencida ? 'font-medium text-red-600' : ''}>
                              {' '}
                              ({vencida ? 'venció' : 'vence'} {fecha(e.inscripcionVence)})
                            </span>
                          )}
                        </span>
                      ) : (
                        // Operar sin inscripción es una infracción por sí sola.
                        // Se dice, en vez de dejar la celda vacía como si
                        // faltara el dato.
                        <span className="font-medium text-semaforo-parcial">Sin inscribir</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge
                        status={
                          e.estado === 'operational'
                            ? vencida
                              ? 'no_cumple'
                              : 'cumple'
                            : 'na'
                        }
                        label={etiqueta(ESTADO_EQUIPO, e.estado)}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Editar ${e.nombre}`}
                          onClick={() => setEditando(e)}
                          icon={<Pencil className="h-4 w-4" aria-hidden />}
                        >
                          Editar
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Eliminar ${e.nombre}`}
                          onClick={() => setBorrando(e)}
                          icon={<Trash2 className="h-4 w-4" aria-hidden />}
                        >
                          Eliminar
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <FormularioIso
        open={creando}
        onOpenChange={setCreando}
        titulo="Nuevo equipo regulado"
        campos={campos(plants)}
        onGuardar={crearEquipo}
      />

      <FormularioIso
        open={editando !== null}
        onOpenChange={(v) => !v && setEditando(null)}
        titulo={`Editar ${editando?.nombre ?? ''}`}
        campos={campos(plants)}
        valores={
          editando && {
            facility_id: editando.facilityId,
            name: editando.nombre,
            equipment_type: editando.tipo,
            brand: editando.marca,
            model: editando.modelo,
            registration_authority: editando.autoridad,
            registration_number: editando.numeroInscripcion,
            registration_expires_at: editando.inscripcionVence,
            status: editando.estado,
          }
        }
        onGuardar={(d) => (editando ? editarEquipo(editando.id, d) : Promise.resolve(false))}
      />

      <ConfirmarBorrado
        open={borrando !== null}
        onOpenChange={(v) => !v && setBorrando(null)}
        queSeBorra={borrando?.nombre ?? ''}
        onConfirmar={() => (borrando ? borrarEquipo(borrando.id) : Promise.resolve(false))}
      />
    </div>
  );
}
