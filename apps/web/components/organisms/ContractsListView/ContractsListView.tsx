'use client';

import { useId, useState, type FormEvent } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useGestores } from '@/lib/gestores-store';
import type { ContractsListViewProps } from './ContractsListView.types';

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

/**
 * S-29 Contratos del Cliente, con campos dinámicos/customizables (RF-58b).
 * La extracción asistida por IA desde PDF (RF-58c) queda fuera de alcance
 * (depende de apps/ai-service) — el alta es manual.
 */
export function ContractsListView({ subTenantId, subTenantNombre }: ContractsListViewProps) {
  const { contratos, addContrato, errorAlGuardar } = useGestores();
  const formId = useId();
  const subContratos = contratos.filter((c) => c.subTenantId === subTenantId);

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [numero, setNumero] = useState('');
  const [nombre, setNombre] = useState('');
  const [fechaInicio, setFechaInicio] = useState('');
  const [fechaTermino, setFechaTermino] = useState('');
  const [campos, setCampos] = useState<{ clave: string; valor: string }[]>([{ clave: '', valor: '' }]);
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  function updateCampo(index: number, field: 'clave' | 'valor', value: string) {
    setCampos((prev) => prev.map((c, i) => (i === index ? { ...c, [field]: value } : c)));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!numero.trim() || !nombre.trim() || !fechaInicio || !fechaTermino) {
      setError('Completa número, nombre, fecha de inicio y fecha de término.');
      return;
    }
    const clavesValidas = campos.filter((c) => c.clave.trim());
    const claves = clavesValidas.map((c) => c.clave.trim().toLowerCase());
    if (new Set(claves).size !== claves.length) {
      setError('Hay campos personalizados con la misma clave repetida.');
      return;
    }
    const camposCustom = Object.fromEntries(clavesValidas.map((c) => [c.clave.trim(), c.valor.trim()]));
    setGuardando(true);
    const ok = await addContrato({
      subTenantId,
      numero: numero.trim(),
      nombre: nombre.trim(),
      // **Se manda la fecha de calendario tal cual, sin pasar por `Date`.**
      // `new Date('2026-08-27').toISOString()` es medianoche UTC, y en Chile
      // —UTC−4— eso es el 26: la vigencia de un contrato empezaria un dia
      // antes. Es el defecto que ya aparecio en la pantalla de documentos.
      fechaInicio,
      fechaTermino,
      camposCustom,
    });
    setGuardando(false);
    // Solo se limpia si se guardo: el numero duplicado es un rechazo esperable
    // y perder lo escrito obligaria a tipear el contrato entero de nuevo.
    if (!ok) return;
    setNumero('');
    setNombre('');
    setFechaInicio('');
    setFechaTermino('');
    setCampos([{ clave: '', valor: '' }]);
    setError(null);
    setIsFormOpen(false);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">Contratos de {subTenantNombre}</h2>
        <Button size="md" icon={<Plus className="h-4 w-4" aria-hidden />} onClick={() => setIsFormOpen((v) => !v)}>
          Subir contrato
        </Button>
      </div>

      {isFormOpen && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-card border border-slate-200 bg-white p-4" noValidate>
          <FormField
            label="Número de contrato"
            htmlFor={`${formId}-numero`}
            required
            hint="El que figura en el documento firmado. No se genera solo: un número inventado no coincidiría con el del papel."
          >
            <Input id={`${formId}-numero`} value={numero} onChange={(e) => setNumero(e.target.value)} />
          </FormField>
          <FormField label="Nombre del contrato" htmlFor={`${formId}-nombre`} required error={error ?? undefined}>
            <Input id={`${formId}-nombre`} value={nombre} invalid={!!error} onChange={(e) => setNombre(e.target.value)} />
          </FormField>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Fecha de inicio" htmlFor={`${formId}-inicio`} required>
              <Input id={`${formId}-inicio`} type="date" value={fechaInicio} onChange={(e) => setFechaInicio(e.target.value)} />
            </FormField>
            <FormField label="Fecha de término" htmlFor={`${formId}-termino`} required>
              <Input id={`${formId}-termino`} type="date" value={fechaTermino} onChange={(e) => setFechaTermino(e.target.value)} />
            </FormField>
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">Campos personalizados (opcional)</p>
            <div className="flex flex-col gap-2">
              {campos.map((c, i) => (
                <div key={i} className="flex items-center gap-2">
                  <Input placeholder="Nombre del campo" value={c.clave} onChange={(e) => updateCampo(i, 'clave', e.target.value)} />
                  <Input placeholder="Valor" value={c.valor} onChange={(e) => updateCampo(i, 'valor', e.target.value)} />
                  <button
                    type="button"
                    aria-label="Quitar campo"
                    onClick={() => setCampos((prev) => prev.filter((_, idx) => idx !== i))}
                    className="shrink-0 text-slate-400 hover:text-red-600"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden />
                  </button>
                </div>
              ))}
            </div>
            <Button
              type="button"
              variant="ghost"
              size="md"
              className="mt-2"
              onClick={() => setCampos((prev) => [...prev, { clave: '', valor: '' }])}
            >
              + Agregar campo
            </Button>
          </div>

          <FormField label="Documento (PDF)" htmlFor={`${formId}-pdf`} hint="La extracción automática de campos estará disponible próximamente; por ahora se completan manualmente.">
            <input id={`${formId}-pdf`} type="file" accept="application/pdf" className="text-sm" />
          </FormField>

          {errorAlGuardar && (
            <p role="alert" className="text-sm text-semaforo-no-cumple">
              No se pudo guardar el contrato: {errorAlGuardar}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setIsFormOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={guardando}>
              {guardando ? 'Guardando…' : 'Guardar contrato'}
            </Button>
          </div>
        </form>
      )}

      {subContratos.length === 0 ? (
        <p className="rounded-card border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
          Aún no hay contratos registrados para este cliente.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {subContratos.map((c) => (
            <li key={c.id} className="rounded-lg border border-slate-100 bg-white p-4">
              <p className="font-medium text-slate-800">{c.nombre}</p>
              <p className="text-xs text-slate-500">
                {formatFecha(c.fechaInicio)} — {formatFecha(c.fechaTermino)}
              </p>
              {Object.keys(c.camposCustom).length > 0 && (
                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-600">
                  {Object.entries(c.camposCustom).map(([clave, valor]) => (
                    <div key={clave} className="contents">
                      <dt className="font-medium text-slate-500">{clave}</dt>
                      <dd>{valor}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
