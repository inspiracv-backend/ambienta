'use client';

import { useMemo, useState } from 'react';
import { Inbox, Pencil, Plus, Trash2 } from 'lucide-react';
import { FEATURE_FLAGS } from '@ambienta/shared';
import { Button, StatusBadge } from '@/components/atoms';
import { FilterBar } from '@/components/molecules';
import { ConfirmarBorrado, FormularioIso, type CampoIso } from '@/components/organisms/IsoForms';
import { getUserName } from '@/lib/get-user-name';
import { useIso, type RiesgoApi, type PlantaApi } from '@/lib/iso-store';
import {
  ESTADO_REGISTRO,
  NIVEL_RIESGO,
  ORIGEN_REGISTRO,
  TIPO_REGISTRO,
  TRATAMIENTO,
  etiqueta,
  opciones,
} from '@/lib/iso-vocabulario';

function nivelSemaforo(nivel: string): 'cumple' | 'parcial' | 'no_cumple' {
  if (nivel === 'critical' || nivel === 'high') return 'no_cumple';
  if (nivel === 'medium') return 'parcial';
  return 'cumple';
}

function campos(plants: PlantaApi[], aspectos: { id: string; actividad: string }[]): CampoIso[] {
  return [
    {
      nombre: 'code',
      etiqueta: 'Código',
      tipo: 'texto',
      requerido: true,
      ayuda: 'Único dentro de la empresa. Lo pone la empresa, no el sistema.',
    },
    {
      nombre: 'entry_type',
      etiqueta: 'Tipo',
      tipo: 'select',
      requerido: true,
      opciones: opciones(TIPO_REGISTRO),
    },
    { nombre: 'description', etiqueta: 'Descripción', tipo: 'textarea', requerido: true },
    {
      nombre: 'origin',
      etiqueta: 'Origen',
      tipo: 'select',
      requerido: true,
      opciones: opciones(ORIGEN_REGISTRO),
      // La base lo exige: `ck_risks_origen_aspecto`. Decirlo acá evita que la
      // persona descubra la regla con un 422 después de escribir todo.
      ayuda: 'Si eliges "Aspecto ambiental", tienes que indicar cuál más abajo.',
    },
    {
      nombre: 'environmental_aspect_id',
      etiqueta: 'Aspecto de origen',
      tipo: 'select',
      opciones: aspectos.map((a) => ({ value: a.id, label: a.actividad })),
    },
    {
      nombre: 'risk_level',
      etiqueta: 'Nivel',
      tipo: 'select',
      requerido: true,
      opciones: opciones(NIVEL_RIESGO),
    },
    { nombre: 'treatment', etiqueta: 'Tratamiento', tipo: 'select', opciones: opciones(TRATAMIENTO) },
    {
      nombre: 'status',
      etiqueta: 'Estado',
      tipo: 'select',
      requerido: true,
      opciones: opciones(ESTADO_REGISTRO),
    },
    {
      nombre: 'facility_id',
      etiqueta: 'Planta',
      tipo: 'select',
      opciones: plants.map((p) => ({ value: p.id, label: p.nombre })),
      ayuda: 'Vacío = afecta a toda la empresa.',
    },
    { nombre: 'review_date', etiqueta: 'Próxima revisión', tipo: 'fecha' },
  ];
}

interface Props {
  riesgos: RiesgoApi[];
  /** Las plantas **de la API**, con su id real. Ver `plantas` en `iso-store`. */
  plants: PlantaApi[];
}

/**
 * Riesgos y oportunidades (ISO 14001 §6.1.1).
 *
 * Leía `mocks/` **directamente**, sin una sola llamada a la API, y no había
 * forma de crear, editar ni borrar nada — mientras la API tenía CRUD completo.
 *
 * El vocabulario es el de la base (`risk`, `in_treatment`, `climate_change`), y
 * no el del paquete compartido, que lo define en español. Esa divergencia era
 * real y estas pantallas leían el lado equivocado.
 */
export function RiesgosOportunidadesTable({ riesgos, plants }: Props) {
  const [plantaFiltro, setPlantaFiltro] = useState('todas');
  const [tipoFiltro, setTipoFiltro] = useState('todos');
  const [estadoFiltro, setEstadoFiltro] = useState('todos');
  const [creando, setCreando] = useState(false);
  const [editando, setEditando] = useState<RiesgoApi | null>(null);
  const [borrando, setBorrando] = useState<RiesgoApi | null>(null);

  const { aspectos, crearRiesgo, editarRiesgo, borrarRiesgo } = useIso();

  const filtered = useMemo(
    () =>
      riesgos.filter((r) => {
        if (plantaFiltro !== 'todas' && r.facilityId !== plantaFiltro) return false;
        if (tipoFiltro !== 'todos' && r.tipo !== tipoFiltro) return false;
        if (estadoFiltro !== 'todos' && r.estado !== estadoFiltro) return false;
        return true;
      }),
    [riesgos, plantaFiltro, tipoFiltro, estadoFiltro],
  );

  const opcionesAspecto = useMemo(
    () => aspectos.map((a) => ({ id: a.id, actividad: `${a.actividad} — ${a.aspecto}` })),
    [aspectos],
  );

  if (!FEATURE_FLAGS.matricesIso) return null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <FilterBar
          filters={[
            {
              id: 'filtro-planta-ro',
              label: 'Planta',
              value: plantaFiltro,
              onChange: setPlantaFiltro,
              options: [
                { value: 'todas', label: 'Todas las plantas' },
                ...plants.map((p) => ({ value: p.id, label: p.nombre })),
              ],
            },
            {
              id: 'filtro-tipo-ro',
              label: 'Tipo',
              value: tipoFiltro,
              onChange: setTipoFiltro,
              options: [{ value: 'todos', label: 'Todos' }, ...opciones(TIPO_REGISTRO)],
            },
            {
              id: 'filtro-estado-ro',
              label: 'Estado',
              value: estadoFiltro,
              onChange: setEstadoFiltro,
              options: [{ value: 'todos', label: 'Todos' }, ...opciones(ESTADO_REGISTRO)],
            },
          ]}
        />
        <Button onClick={() => setCreando(true)} icon={<Plus className="h-4 w-4" aria-hidden />}>
          Nuevo registro
        </Button>
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 py-12 text-center text-slate-500">
          <Inbox className="h-8 w-8 text-slate-400" aria-hidden />
          {riesgos.length === 0 ? (
            <>
              <p className="text-sm font-medium text-slate-700">
                Todavía no hay riesgos ni oportunidades
              </p>
              <p className="text-sm">
                Nada de lo que veas acá es de ejemplo: si está en la tabla, está en la
                empresa.
              </p>
            </>
          ) : (
            <p className="text-sm">No hay registros que coincidan con los filtros.</p>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-200">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Riesgos y oportunidades</caption>
            <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Código</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Descripción</th>
                <th className="px-4 py-3">Origen</th>
                <th className="px-4 py-3">Nivel</th>
                <th className="px-4 py-3">Tratamiento</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Responsable</th>
                <th className="px-4 py-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs font-medium text-slate-900">
                    {r.codigo}
                  </td>
                  <td className="px-4 py-3">
                    <span className={r.tipo === 'risk' ? 'text-red-700' : 'text-green-700'}>
                      {etiqueta(TIPO_REGISTRO, r.tipo)}
                    </span>
                  </td>
                  <td className="max-w-xs px-4 py-3 text-slate-700">{r.descripcion}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {etiqueta(ORIGEN_REGISTRO, r.origen)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge
                      status={nivelSemaforo(r.nivel)}
                      label={etiqueta(NIVEL_RIESGO, r.nivel)}
                    />
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {etiqueta(TRATAMIENTO, r.tratamiento)}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {etiqueta(ESTADO_REGISTRO, r.estado)}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {r.responsableId ? getUserName(r.responsableId) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`Editar ${r.codigo}`}
                        onClick={() => setEditando(r)}
                        icon={<Pencil className="h-4 w-4" aria-hidden />}
                      >
                        Editar
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`Eliminar ${r.codigo}`}
                        onClick={() => setBorrando(r)}
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
        titulo="Nuevo riesgo u oportunidad"
        campos={campos(plants, opcionesAspecto)}
        onGuardar={crearRiesgo}
      />

      <FormularioIso
        open={editando !== null}
        onOpenChange={(v) => !v && setEditando(null)}
        titulo={`Editar ${editando?.codigo ?? ''}`}
        campos={campos(plants, opcionesAspecto)}
        valores={
          editando && {
            code: editando.codigo,
            entry_type: editando.tipo,
            description: editando.descripcion,
            origin: editando.origen,
            environmental_aspect_id: editando.aspectoAmbientalId,
            risk_level: editando.nivel,
            treatment: editando.tratamiento,
            status: editando.estado,
            facility_id: editando.facilityId,
            review_date: editando.fechaRevision,
          }
        }
        onGuardar={(d) => (editando ? editarRiesgo(editando.id, d) : Promise.resolve(false))}
      />

      <ConfirmarBorrado
        open={borrando !== null}
        onOpenChange={(v) => !v && setBorrando(null)}
        queSeBorra={borrando ? `${borrando.codigo} — ${borrando.descripcion}` : ''}
        onConfirmar={() => (borrando ? borrarRiesgo(borrando.id) : Promise.resolve(false))}
      />
    </div>
  );
}
