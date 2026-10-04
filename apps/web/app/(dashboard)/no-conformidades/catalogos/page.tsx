'use client';

import { useState } from 'react';
import type { FormaMetodologia } from '@ambienta/shared';
import { Button, Input, Spinner } from '@/components/atoms';
import { Breadcrumbs, FormField, PageHeader } from '@/components/molecules';
import {
  plazoDesdeCampo,
  useCatalogosDeMejora,
  type MetodologiaDeCausa,
  type NivelDeSeveridad,
} from '@/lib/catalogos-mejora';

const FORMAS: { value: FormaMetodologia; label: string }[] = [
  { value: 'cinco_porques', label: '5 por qué (cinco escalones)' },
  { value: 'espina_pescado', label: 'Espina de pescado (lista de causas)' },
  { value: 'texto_libre', label: 'Texto libre' },
];

/**
 * Catálogos del registro de mejora (RF-100, #41).
 *
 * ## Por qué importa el plazo
 *
 * `días para cerrar` es lo que le da **fecha límite** a las etapas de un
 * hallazgo, y con ella los avisos al responsable (RF-99). Vacío no es cero: es
 * «la empresa no declaró plazo», y entonces el sistema no inventa uno. Hasta el
 * 13-sep no había dónde declararlo.
 *
 * ## Lo que la pantalla no ofrece
 *
 * - **Agregar un nivel de severidad.** El código de cada nivel es lo que se
 *   guarda en el hallazgo, y la base solo admite los tres que ya existen.
 * - **Borrar.** Un hallazgo antiguo nombra el nivel o la metodología con que se
 *   registró. Se desactiva, y se puede volver a activar.
 */
export default function CatalogosDeMejoraPage() {
  const cat = useCatalogosDeMejora();

  return (
    <div className="flex flex-col gap-6">
      <Breadcrumbs items={[{ label: 'No Conformidades', href: '/no-conformidades' }, { label: 'Catálogos' }]} />
      <PageHeader
        titulo="Catálogos del registro de mejora"
        descripcion="La escala de severidad con sus plazos, y las metodologías de análisis de causa de tu empresa."
      />

      {cat.cargando ? (
        <Spinner label="Cargando catálogos" />
      ) : cat.errorDeCarga ? (
        <p role="alert" className="rounded-card border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          No se pudieron cargar los catálogos: {cat.errorDeCarga}
        </p>
      ) : (
        <>
          <section className="rounded-card border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-semibold text-slate-900">Escala de severidad</h2>
            <p className="mt-1 max-w-prose text-sm text-slate-500">
              Los días para cerrar dan la fecha límite de cada etapa y activan los avisos al responsable. Vacío significa que
              la empresa no declaró plazo: el sistema no inventa uno. El plazo se aplica a los hallazgos que se registren desde
              ahora; los existentes conservan su fecha.
            </p>
            <ul className="mt-4 flex flex-col gap-3">
              {cat.niveles.map((n) => (
                <FilaNivel key={n.id} nivel={n} onGuardar={cat.editarNivel} />
              ))}
            </ul>
          </section>

          <section className="rounded-card border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-semibold text-slate-900">Metodologías de análisis de causa</h2>
            <p className="mt-1 max-w-prose text-sm text-slate-500">
              El nombre lo pones tú; la forma decide qué pide el formulario del análisis.
            </p>
            <ul className="mt-4 flex flex-col gap-3">
              {cat.metodologias.map((m) => (
                <FilaMetodologia key={m.id} metodologia={m} onGuardar={cat.editarMetodologia} />
              ))}
            </ul>
            <NuevaMetodologia onCrear={cat.crearMetodologia} codigos={cat.metodologias.map((m) => m.code)} />
          </section>
        </>
      )}
    </div>
  );
}

type Guardar<T> = (id: string, cambios: T) => Promise<{ ok: true } | { ok: false; error: string }>;

function FilaNivel({
  nivel,
  onGuardar,
}: {
  nivel: NivelDeSeveridad;
  onGuardar: Guardar<{ label?: string; daysToClose?: number | null; active?: boolean }>;
}) {
  const [label, setLabel] = useState(nivel.label);
  const [dias, setDias] = useState(nivel.daysToClose === null ? '' : String(nivel.daysToClose));
  const [estado, setEstado] = useState<{ ok: boolean; texto: string } | null>(null);
  const [guardando, setGuardando] = useState(false);

  const plazo = plazoDesdeCampo(dias);
  const cambio = label.trim() !== nivel.label || plazo !== nivel.daysToClose;

  async function guardar(cambios: { label?: string; daysToClose?: number | null; active?: boolean }) {
    setGuardando(true);
    const r = await onGuardar(nivel.id, cambios);
    setGuardando(false);
    setEstado(r.ok ? { ok: true, texto: 'Guardado.' } : { ok: false, texto: `No se guardó: ${r.error}` });
  }

  return (
    <li className={`rounded-lg border p-4 ${nivel.active ? 'border-slate-200' : 'border-dashed border-slate-300 bg-slate-50'}`}>
      <div className="grid gap-3 sm:grid-cols-[1fr_10rem_auto] sm:items-end">
        <FormField label={`Etiqueta (código ${nivel.code})`} htmlFor={`nivel-${nivel.id}`}>
          <Input id={`nivel-${nivel.id}`} value={label} onChange={(e) => setLabel(e.target.value)} />
        </FormField>
        <FormField
          label="Días para cerrar"
          htmlFor={`dias-${nivel.id}`}
          error={plazo === undefined ? 'Un número entero mayor que cero, o vacío.' : undefined}
        >
          <Input
            id={`dias-${nivel.id}`}
            inputMode="numeric"
            placeholder="Sin plazo"
            value={dias}
            invalid={plazo === undefined}
            onChange={(e) => setDias(e.target.value)}
          />
        </FormField>
        <div className="flex gap-2">
          <Button
            type="button"
            disabled={!cambio || plazo === undefined || !label.trim() || guardando}
            onClick={() => guardar({ label: label.trim(), daysToClose: plazo as number | null })}
          >
            Guardar
          </Button>
          <Button type="button" variant="secondary" disabled={guardando} onClick={() => guardar({ active: !nivel.active })}>
            {nivel.active ? 'Desactivar' : 'Activar'}
          </Button>
        </div>
      </div>
      {!nivel.active && <p className="mt-2 text-xs text-slate-500">Desactivado: no se ofrece al registrar hallazgos nuevos.</p>}
      {estado && (
        <p role="status" className={`mt-2 text-sm ${estado.ok ? 'text-green-700' : 'text-semaforo-no-cumple'}`}>
          {estado.texto}
        </p>
      )}
    </li>
  );
}

function FilaMetodologia({
  metodologia,
  onGuardar,
}: {
  metodologia: MetodologiaDeCausa;
  onGuardar: Guardar<{ name?: string; shape?: FormaMetodologia; active?: boolean }>;
}) {
  const [name, setName] = useState(metodologia.name);
  const [shape, setShape] = useState<FormaMetodologia>(metodologia.shape);
  const [estado, setEstado] = useState<{ ok: boolean; texto: string } | null>(null);
  const [guardando, setGuardando] = useState(false);
  const cambio = name.trim() !== metodologia.name || shape !== metodologia.shape;

  async function guardar(cambios: { name?: string; shape?: FormaMetodologia; active?: boolean }) {
    setGuardando(true);
    const r = await onGuardar(metodologia.id, cambios);
    setGuardando(false);
    setEstado(r.ok ? { ok: true, texto: 'Guardado.' } : { ok: false, texto: `No se guardó: ${r.error}` });
  }

  return (
    <li className={`rounded-lg border p-4 ${metodologia.active ? 'border-slate-200' : 'border-dashed border-slate-300 bg-slate-50'}`}>
      <div className="grid gap-3 sm:grid-cols-[1fr_16rem_auto] sm:items-end">
        <FormField label="Nombre" htmlFor={`met-${metodologia.id}`}>
          <Input id={`met-${metodologia.id}`} value={name} onChange={(e) => setName(e.target.value)} />
        </FormField>
        <FormField label="Forma" htmlFor={`forma-${metodologia.id}`}>
          <select
            id={`forma-${metodologia.id}`}
            className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
            value={shape}
            onChange={(e) => setShape(e.target.value as FormaMetodologia)}
          >
            {FORMAS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
        </FormField>
        <div className="flex gap-2">
          <Button type="button" disabled={!cambio || !name.trim() || guardando} onClick={() => guardar({ name: name.trim(), shape })}>
            Guardar
          </Button>
          <Button type="button" variant="secondary" disabled={guardando} onClick={() => guardar({ active: !metodologia.active })}>
            {metodologia.active ? 'Desactivar' : 'Activar'}
          </Button>
        </div>
      </div>
      {estado && (
        <p role="status" className={`mt-2 text-sm ${estado.ok ? 'text-green-700' : 'text-semaforo-no-cumple'}`}>
          {estado.texto}
        </p>
      )}
    </li>
  );
}

function NuevaMetodologia({
  onCrear,
  codigos,
}: {
  onCrear: (d: { code: string; name: string; shape: FormaMetodologia }) => Promise<{ ok: true } | { ok: false; error: string }>;
  codigos: string[];
}) {
  const [name, setName] = useState('');
  const [shape, setShape] = useState<FormaMetodologia>('texto_libre');
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  // El código se deriva del nombre: es un identificador interno, y pedirlo
  // haría escribir dos veces lo mismo.
  const code = name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
    .slice(0, 40);
  const repetido = code !== '' && codigos.includes(code);

  async function crear() {
    setGuardando(true);
    const r = await onCrear({ code, name: name.trim(), shape });
    setGuardando(false);
    if (r.ok) {
      setName('');
      setError(null);
    } else {
      setError(`No se creó: ${r.error}`);
    }
  }

  return (
    <div className="mt-5 border-t border-slate-100 pt-4">
      <h3 className="text-sm font-semibold text-slate-700">Agregar metodología</h3>
      <div className="mt-2 grid gap-3 sm:grid-cols-[1fr_16rem_auto] sm:items-end">
        <FormField label="Nombre" htmlFor="met-nueva" error={repetido ? 'Ya hay una con ese nombre.' : undefined}>
          <Input id="met-nueva" value={name} invalid={repetido} onChange={(e) => setName(e.target.value)} placeholder="Ej: Árbol de fallos" />
        </FormField>
        <FormField label="Forma" htmlFor="forma-nueva">
          <select
            id="forma-nueva"
            className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
            value={shape}
            onChange={(e) => setShape(e.target.value as FormaMetodologia)}
          >
            {FORMAS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
        </FormField>
        <Button type="button" disabled={!code || repetido || guardando} onClick={crear}>
          Agregar
        </Button>
      </div>
      {error && <p className="mt-2 text-sm text-semaforo-no-cumple">{error}</p>}
    </div>
  );
}
