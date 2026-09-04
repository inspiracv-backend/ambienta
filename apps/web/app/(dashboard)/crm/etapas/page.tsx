'use client';

import { useState } from 'react';
import { AlertTriangle, ArrowDown, ArrowUp, Plus, RefreshCw } from 'lucide-react';
import { Button, Input, Spinner } from '@/components/atoms';
import { Breadcrumbs, FormField, PageHeader } from '@/components/molecules';
import {
  AYUDA_DEL_TIPO,
  TIPO_DE_ETAPA,
  codigoDeEtapa,
  motivoParaNoRetirarEtapa,
  type EtapaCrm,
  type TipoDeEtapa,
} from '@/lib/crm';
import { useEtapasDelPipeline, type DatosDeEtapa } from '@/lib/crm-etapas-store';

/**
 * Configurar las columnas del pipeline (#78).
 *
 * ## Por qué existe
 *
 * Las etapas son configurables por empresa a propósito: una consultora
 * ambiental y un gestor de residuos no venden igual. Pero no había pantalla, así
 * que en la práctica todas tenían el mismo pipeline y la única forma de
 * cambiarlo era por `curl`. Una configuración que no se puede configurar es una
 * decisión de producto que nadie tomó.
 *
 * ## El tipo no es el nombre, y esa es la parte que hay que explicar
 *
 * `kind` dice qué significa la columna **para el sistema**: al llegar a una de
 * ganado el trato se cierra, a una de perdido se exige el motivo. El nombre lo
 * pone la empresa. Por eso el tipo se muestra siempre con su explicación al
 * lado: cambiarlo por error convierte una columna intermedia en un cierre.
 *
 * ## Lo que la pantalla se niega a ofrecer
 *
 * Retirar una etapa con tratos dentro los dejaría fuera del tablero sin
 * borrarlos, y quedarse sin una etapa de un tipo rompe el pipeline. El servidor
 * responde 409 en los dos casos — acá el botón aparece deshabilitado **con el
 * motivo al lado**, porque la pregunta que se hace mirando la lista es «por qué
 * a esta sí y a esta no».
 */

const TIPOS: TipoDeEtapa[] = ['open', 'won', 'lost'];

export default function EtapasDelPipelinePage() {
  const {
    etapas,
    tratosPorEtapa,
    cargando,
    errorDeCarga,
    crear,
    editar,
    retirar,
    recargar,
  } = useEtapasDelPipeline();

  const [nueva, setNueva] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function conAviso(accion: () => Promise<{ ok: boolean; error?: string }>) {
    const r = await accion();
    setError(r.ok ? null : (r.error ?? 'No se pudo guardar.'));
    return r;
  }

  /** Intercambia la posición con la vecina, que es lo que hace «subir». */
  async function mover(etapa: EtapaCrm, direccion: -1 | 1) {
    const orden = [...etapas].sort((a, b) => a.posicion - b.posicion);
    const i = orden.findIndex((e) => e.id === etapa.id);
    const vecina = orden[i + direccion];
    if (!vecina) return;
    // Se mandan las dos: intercambiar posiciones es una operación sobre el par,
    // y mover solo una dejaría dos columnas con el mismo número — donde el
    // desempate lo decide el nombre, que es alfabético y no significa nada.
    const r = await conAviso(() => editar(etapa.id, { posicion: vecina.posicion }));
    if (r.ok) await conAviso(() => editar(vecina.id, { posicion: etapa.posicion }));
  }

  const ordenadas = [...etapas].sort((a, b) => a.posicion - b.posicion);

  return (
    <div className="flex flex-col gap-6">
      <Breadcrumbs items={[{ label: 'CRM', href: '/crm' }, { label: 'Etapas' }]} />

      <PageHeader
        titulo="Etapas del pipeline"
        descripcion="Las columnas del tablero, en su orden. Cada empresa arma el suyo: lo que no cambia es que el sistema necesita al menos una de cada tipo."
        acciones={
          <div className="flex gap-2">
            <Button
              variant="secondary"
              icon={<RefreshCw className="h-4 w-4" aria-hidden />}
              onClick={() => void recargar()}
            >
              Actualizar
            </Button>
            <Button
              icon={<Plus className="h-4 w-4" aria-hidden />}
              onClick={() => setNueva(true)}
            >
              Nueva etapa
            </Button>
          </div>
        }
      />

      {cargando && (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="h-4 w-4" />
          Cargando las etapas…
        </p>
      )}

      {errorDeCarga && !cargando && (
        <div className="rounded-card border border-semaforo-incumple/30 bg-semaforo-incumple-bg p-4">
          <p className="flex items-center gap-2 text-sm font-medium text-semaforo-incumple">
            <AlertTriangle className="h-4 w-4" aria-hidden />
            No se pudieron cargar las etapas.
          </p>
          <p className="mt-1 text-xs text-slate-600">{errorDeCarga}</p>
          <Button variant="secondary" size="sm" className="mt-3" onClick={() => void recargar()}>
            Reintentar
          </Button>
        </div>
      )}

      {error && (
        <p
          role="alert"
          className="rounded-card border border-semaforo-incumple/30 bg-semaforo-incumple-bg px-3 py-2 text-sm text-semaforo-incumple"
        >
          {error}
        </p>
      )}

      {nueva && (
        <FormularioDeEtapa
          siguientePosicion={Math.max(0, ...etapas.map((e) => e.posicion)) + 1}
          codigosEnUso={etapas.map((e) => e.codigo)}
          onCancelar={() => setNueva(false)}
          onGuardar={async (datos) => {
            const r = await conAviso(() => crear(datos));
            if (r.ok) setNueva(false);
            return r;
          }}
        />
      )}

      {!cargando && !errorDeCarga && (
        <ul className="flex flex-col gap-3">
          {ordenadas.map((etapa, i) => {
            const dentro = tratosPorEtapa[etapa.id] ?? 0;
            const bloqueo = motivoParaNoRetirarEtapa(etapa, etapas, dentro);
            return (
              <li
                key={etapa.id}
                className="flex flex-col gap-3 rounded-card border border-slate-200 bg-white p-4 sm:flex-row sm:items-start sm:justify-between"
              >
                <div className="flex min-w-0 flex-1 flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-medium tabular-nums text-slate-400">
                      {i + 1}
                    </span>
                    <label className="sr-only" htmlFor={`nombre-${etapa.id}`}>
                      Nombre de la etapa
                    </label>
                    <Input
                      id={`nombre-${etapa.id}`}
                      defaultValue={etapa.nombre}
                      className="max-w-xs"
                      onBlur={(e) => {
                        const nombre = e.target.value.trim();
                        if (nombre && nombre !== etapa.nombre) {
                          void conAviso(() => editar(etapa.id, { nombre }));
                        }
                      }}
                    />
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                      {dentro} {dentro === 1 ? 'oportunidad' : 'oportunidades'}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <label className="text-xs text-slate-500" htmlFor={`tipo-${etapa.id}`}>
                      Tipo
                    </label>
                    <select
                      id={`tipo-${etapa.id}`}
                      value={etapa.tipo}
                      onChange={(e) =>
                        void conAviso(() =>
                          editar(etapa.id, { tipo: e.target.value as TipoDeEtapa }),
                        )
                      }
                      className="rounded-lg border border-slate-200 px-2 py-1 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                    >
                      {TIPOS.map((t) => (
                        <option key={t} value={t}>
                          {TIPO_DE_ETAPA[t]}
                        </option>
                      ))}
                    </select>
                    <span className="text-xs text-slate-500">{AYUDA_DEL_TIPO[etapa.tipo]}</span>
                  </div>

                  {bloqueo && <p className="text-xs text-slate-500">{bloqueo}</p>}
                </div>

                <div className="flex shrink-0 gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Subir ${etapa.nombre}`}
                    disabled={i === 0}
                    onClick={() => void mover(etapa, -1)}
                  >
                    <ArrowUp className="h-4 w-4" aria-hidden />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Bajar ${etapa.nombre}`}
                    disabled={i === ordenadas.length - 1}
                    onClick={() => void mover(etapa, 1)}
                  >
                    <ArrowDown className="h-4 w-4" aria-hidden />
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={bloqueo !== null}
                    onClick={() => void conAviso(() => retirar(etapa.id))}
                  >
                    Retirar
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** El alta. Va en la página y no en un modal: es una fila más de la lista. */
function FormularioDeEtapa({
  siguientePosicion,
  codigosEnUso,
  onCancelar,
  onGuardar,
}: {
  siguientePosicion: number;
  /** Para no proponer un `code` que la base ya tiene: el índice es único. */
  codigosEnUso: string[];
  onCancelar: () => void;
  onGuardar: (datos: DatosDeEtapa) => Promise<{ ok: boolean; error?: string }>;
}) {
  const [nombre, setNombre] = useState('');
  const [tipo, setTipo] = useState<TipoDeEtapa>('open');
  const [guardando, setGuardando] = useState(false);

  // `codigoDeEtapa` vive en `lib/crm.ts` y tiene sus propias pruebas: los
  // acentos, el nombre que no deja nada utilizable y el choque con una etapa
  // que ya existe son casos con respuesta, no detalles de esta pantalla.
  const codigo = codigoDeEtapa(nombre, codigosEnUso);

  return (
    <form
      aria-label="Nueva etapa"
      className="flex flex-col gap-4 rounded-card border border-brand-200 bg-brand-50/40 p-4"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!codigo || guardando) return;
        setGuardando(true);
        await onGuardar({ codigo, nombre: nombre.trim(), posicion: siguientePosicion, tipo });
        setGuardando(false);
      }}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormField label="Nombre" htmlFor="etapa-nueva-nombre">
          <Input
            id="etapa-nueva-nombre"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Ej: Visita técnica"
            required
          />
        </FormField>
        <FormField label="Tipo" htmlFor="etapa-nueva-tipo" hint={AYUDA_DEL_TIPO[tipo]}>
          <select
            id="etapa-nueva-tipo"
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoDeEtapa)}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            {TIPOS.map((t) => (
              <option key={t} value={t}>
                {TIPO_DE_ETAPA[t]}
              </option>
            ))}
          </select>
        </FormField>
      </div>

      <div className="flex items-center justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onCancelar}>
          Cancelar
        </Button>
        <Button type="submit" disabled={!codigo || guardando}>
          {guardando ? 'Creando…' : 'Crear etapa'}
        </Button>
      </div>
    </form>
  );
}
