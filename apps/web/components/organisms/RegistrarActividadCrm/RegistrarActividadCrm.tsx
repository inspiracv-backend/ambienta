'use client';

import { useId, useState, type FormEvent } from 'react';
import { Button, Input, Textarea } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { TIPO_DE_ACTIVIDAD, type TipoDeActividad } from '@/lib/crm';
import type { DatosDeActividad, Resultado } from '@/lib/crm-empresas-store';

/**
 * Anotar una llamada, un correo, una reunión o una nota en la ficha.
 *
 * ## Va en la página y no en un modal
 *
 * Es la acción más frecuente del CRM y la que más se abandona si cuesta: quien
 * corta el teléfono anota en dos líneas o no anota. Un modal agrega un clic
 * para abrirlo y tapa la línea de tiempo que se está mirando.
 *
 * ## El formulario se limpia solo si se guardó
 *
 * Si la API rechaza, lo escrito se queda donde está. Volver a tipear el resumen
 * de una llamada es exactamente el momento en que se deja de usar el CRM.
 */
export function RegistrarActividadCrm({
  onRegistrar,
}: {
  onRegistrar: (datos: DatosDeActividad) => Promise<Resultado>;
}) {
  const formId = useId();
  const [tipo, setTipo] = useState<TipoDeActividad>('call');
  const [asunto, setAsunto] = useState('');
  const [detalle, setDetalle] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const puedeGuardar = asunto.trim().length > 0 && !guardando;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!puedeGuardar) return;
    setGuardando(true);
    setError(null);

    const r = await onRegistrar({ tipo, asunto, detalle });

    setGuardando(false);
    if (!r.ok) {
      setError(r.error ?? 'No se pudo registrar la actividad.');
      return;
    }
    setAsunto('');
    setDetalle('');
  }

  return (
    <form
      onSubmit={enviar}
      aria-label="Registrar actividad"
      className="flex flex-col gap-3 rounded-card border border-slate-200 bg-white p-4"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[10rem_1fr]">
        <FormField label="Tipo" htmlFor={`${formId}-tipo`}>
          <select
            id={`${formId}-tipo`}
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoDeActividad)}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            {(Object.keys(TIPO_DE_ACTIVIDAD) as TipoDeActividad[]).map((t) => (
              <option key={t} value={t}>
                {TIPO_DE_ACTIVIDAD[t]}
              </option>
            ))}
          </select>
        </FormField>

        <FormField label="Asunto" htmlFor={`${formId}-asunto`}>
          <Input
            id={`${formId}-asunto`}
            value={asunto}
            onChange={(e) => setAsunto(e.target.value)}
            placeholder="Ej: Llamada de seguimiento a la propuesta"
            required
          />
        </FormField>
      </div>

      <FormField label="Detalle" htmlFor={`${formId}-detalle`} hint="Opcional.">
        <Textarea
          id={`${formId}-detalle`}
          rows={2}
          value={detalle}
          onChange={(e) => setDetalle(e.target.value)}
          placeholder="Qué se habló, qué quedó pendiente…"
        />
      </FormField>

      {error && (
        <p
          role="alert"
          className="rounded-lg border border-semaforo-incumple/30 bg-semaforo-incumple-bg px-3 py-2 text-sm text-semaforo-incumple"
        >
          {error}
        </p>
      )}

      <div className="flex justify-end">
        <Button type="submit" disabled={!puedeGuardar}>
          {guardando ? 'Anotando…' : 'Anotar'}
        </Button>
      </div>
    </form>
  );
}
