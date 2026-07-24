'use client';

import { useId, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import type { NonConformity } from '@ambienta/shared';
import { Button } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useAudits } from '@/lib/audits-store';
import type { RegisterFindingFormProps } from './RegisterFindingForm.types';

const CRITICIDADES: { value: NonConformity['criticidad']; label: string }[] = [
  { value: 'alta', label: 'Alta' },
  { value: 'media', label: 'Media' },
  { value: 'baja', label: 'Baja' },
];

/**
 * S-24 Crear/Registrar Hallazgo. Formulario simple y rapido, pensado para
 * uso en terreno (mobile-first) — RF-34.
 */
export function RegisterFindingForm({ tenantId, plants, responsableOptions, defaultPlantId, defaultAuditId }: RegisterFindingFormProps) {
  const router = useRouter();
  const { addNonConformity } = useAudits();
  const formId = useId();

  const [plantId, setPlantId] = useState(defaultPlantId ?? plants[0]?.id ?? '');
  const [hallazgo, setHallazgo] = useState('');
  const [criticidad, setCriticidad] = useState<NonConformity['criticidad']>('media');
  const [responsableId, setResponsableId] = useState('');
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!hallazgo.trim() || !plantId || !responsableId) {
      setError('Completa la planta, el hallazgo y el responsable.');
      return;
    }
    const nc = addNonConformity({
      tenantId,
      plantId,
      auditId: defaultAuditId,
      hallazgo: hallazgo.trim(),
      criticidad,
      responsableId,
    });
    router.push(`/no-conformidades/${nc.id}`);
  }

  return (
    <div className="w-full max-w-lg rounded-card border border-slate-200 bg-white p-6">
      <h1 className="text-xl font-semibold text-slate-900">Registrar hallazgo</h1>
      <p className="mt-1 text-sm text-slate-500">Formulario rápido, pensado también para uso en terreno.</p>

      <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-4" noValidate>
        <FormField label="Planta" htmlFor={`${formId}-planta`} required>
          <select
            id={`${formId}-planta`}
            className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
            value={plantId}
            onChange={(e) => setPlantId(e.target.value)}
          >
            {plants.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre}
              </option>
            ))}
          </select>
        </FormField>

        <FormField label="Hallazgo" htmlFor={`${formId}-hallazgo`} required error={error ?? undefined}>
          <textarea
            id={`${formId}-hallazgo`}
            rows={4}
            className="w-full rounded-lg border border-slate-300 p-3 text-sm"
            value={hallazgo}
            onChange={(e) => setHallazgo(e.target.value)}
          />
        </FormField>

        <FormField label="Criticidad" htmlFor={`${formId}-criticidad`}>
          <div className="flex gap-2">
            {CRITICIDADES.map((c) => (
              <button
                key={c.value}
                type="button"
                onClick={() => setCriticidad(c.value)}
                aria-pressed={criticidad === c.value}
                className={
                  criticidad === c.value
                    ? 'flex-1 rounded-lg border-2 border-brand-600 bg-brand-50 px-3 py-2 text-sm font-medium text-brand-700'
                    : 'flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600'
                }
              >
                {c.label}
              </button>
            ))}
          </div>
        </FormField>

        <FormField label="Responsable" htmlFor={`${formId}-responsable`} required>
          <select
            id={`${formId}-responsable`}
            className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
            value={responsableId}
            onChange={(e) => setResponsableId(e.target.value)}
          >
            <option value="">Selecciona un responsable</option>
            {responsableOptions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.nombre}
              </option>
            ))}
          </select>
        </FormField>

        <Button type="submit" className="mt-2 w-full">
          Registrar hallazgo
        </Button>
      </form>
    </div>
  );
}
