'use client';

import { useId, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { FileText, Plus } from 'lucide-react';
import type { TipoDocumento } from '@ambienta/shared';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useLegalMatrix } from '@/lib/legal-matrix-store';
import type { TenantNormsManagerProps } from './TenantNormsManager.types';

const FUENTE_OPTIONS = [
  { value: 'RCA', label: 'RCA' },
  { value: 'ISO', label: 'ISO' },
] as const;

/**
 * S-12 Gestión de RCAs e ISO del Tenant. La extracción asistida por IA
 * (RF-11) queda fuera de esta iteración (gap documentado en
 * openspec/analisis/seccion-d-matriz-legal.md) — el alta solo registra
 * metadata; los artículos se agregan luego manualmente en el detalle.
 */
export function TenantNormsManager({ tenantId, plantIds }: TenantNormsManagerProps) {
  const { norms, addNorm } = useLegalMatrix();
  const formId = useId();
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [nombre, setNombre] = useState('');
  const [fuente, setFuente] = useState<'RCA' | 'ISO'>('RCA');
  const [error, setError] = useState<string | null>(null);

  const tenantNorms = norms.filter((n) => n.tenantId === tenantId && n.fuente !== 'BCN');

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!nombre.trim()) {
      setError('Ingresa un nombre para identificar el documento.');
      return;
    }
    const tipoDocumento: TipoDocumento = fuente === 'RCA' ? 'Resolucion' : 'NCh';
    addNorm({ nombre: nombre.trim(), tipoDocumento, fuente, tenantId, plantIds });
    setNombre('');
    setError(null);
    setIsFormOpen(false);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">RCAs e ISO del tenant</h2>
        <Button size="md" icon={<Plus className="h-4 w-4" aria-hidden />} onClick={() => setIsFormOpen((v) => !v)}>
          Subir RCA / ISO
        </Button>
      </div>

      {isFormOpen && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-card border border-slate-200 bg-white p-4" noValidate>
          <FormField label="Nombre del documento" htmlFor={`${formId}-nombre`} required error={error ?? undefined}>
            <Input id={`${formId}-nombre`} value={nombre} invalid={!!error} onChange={(e) => setNombre(e.target.value)} />
          </FormField>
          <FormField label="Tipo" htmlFor={`${formId}-fuente`}>
            <select
              id={`${formId}-fuente`}
              className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
              value={fuente}
              onChange={(e) => setFuente(e.target.value as 'RCA' | 'ISO')}
            >
              {FUENTE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Documento (PDF)" htmlFor={`${formId}-pdf`} hint="La extracción automática de artículos estará disponible próximamente; por ahora se agregan manualmente en el detalle.">
            <input id={`${formId}-pdf`} type="file" accept="application/pdf" className="text-sm" />
          </FormField>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setIsFormOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit">Guardar</Button>
          </div>
        </form>
      )}

      {tenantNorms.length === 0 ? (
        <p className="rounded-card border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
          Aún no has cargado RCAs ni normas ISO propias.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {tenantNorms.map((norm) => (
            <li key={norm.id} className="flex items-center justify-between rounded-lg border border-slate-100 bg-white p-3">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-brand-600" aria-hidden />
                <div>
                  <Link href={`/matriz-legal/${norm.id}`} className="font-medium text-slate-800 hover:underline">
                    {norm.nombre}
                  </Link>
                  <p className="text-xs text-slate-500">
                    {norm.fuente === 'RCA' ? 'RCA' : 'ISO'} · {norm.articulos.length} artículo(s)
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
