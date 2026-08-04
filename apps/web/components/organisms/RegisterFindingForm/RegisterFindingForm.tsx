'use client';

import { useId, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import {
  FEATURE_FLAGS,
  ORIGENES_DETECCION,
  TIPOS_REGISTRO_MEJORA,
  type NonConformity,
  type OrigenDeteccion,
  type TipoRegistroMejora,
} from '@ambienta/shared';
import { Button } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useAudits } from '@/lib/audits-store';
import { mockDepartamentos } from '@/mocks/departamentos';
import type { RegisterFindingFormProps } from './RegisterFindingForm.types';

const CRITICIDADES: { value: NonConformity['criticidad']; label: string }[] = [
  { value: 'alta', label: 'Alta' },
  { value: 'media', label: 'Media' },
  { value: 'baja', label: 'Baja' },
];

const SELECT = 'h-11 w-full rounded-lg border border-slate-300 px-3 text-sm';

/**
 * S-24 Registrar Mejora.
 *
 * Con la flag `registroMejora` encendida, el **tipo** es la primera decision
 * del formulario y determina que campos aparecen: no todo lo que se registra es
 * una no conformidad. Son cinco clausulas distintas (ISO 9001 §8.7, §10.2 y
 * §9.1.2, e ISO 14001 §6.1.1), no cinco sabores de lo mismo.
 *
 * Con la flag apagada vuelve al formulario anterior de hallazgo simple.
 */
export function RegisterFindingForm({
  tenantId,
  plants,
  responsableOptions,
  defaultPlantId,
  defaultAuditId,
}: RegisterFindingFormProps) {
  const router = useRouter();
  const { addNonConformity } = useAudits();
  const formId = useId();
  const conMejora = FEATURE_FLAGS.registroMejora;

  const [plantId, setPlantId] = useState(defaultPlantId ?? plants[0]?.id ?? '');
  const [hallazgo, setHallazgo] = useState('');
  const [criticidad, setCriticidad] = useState<NonConformity['criticidad']>('media');
  const [responsableId, setResponsableId] = useState('');
  const [error, setError] = useState<string | null>(null);

  const [tipo, setTipo] = useState<TipoRegistroMejora | ''>('');
  const [origen, setOrigen] = useState<OrigenDeteccion | ''>(
    defaultAuditId ? 'auditoria_interna' : '',
  );
  const [procesoId, setProcesoId] = useState('');
  const [sku, setSku] = useState('');
  const [lote, setLote] = useState('');
  const [producto, setProducto] = useState('');
  const [cantidad, setCantidad] = useState('');
  const [unidad, setUnidad] = useState('unidades');
  const [cliente, setCliente] = useState('');
  const [canal, setCanal] = useState('');

  const procesos = mockDepartamentos.filter((d) => d.tenantId === tenantId);
  const esSalidaNoConforme = tipo === 'salida_no_conforme';
  const esReclamo = tipo === 'reclamo';
  const clausula = TIPOS_REGISTRO_MEJORA.find((t) => t.value === tipo)?.clausula;

  function validar(): string | null {
    if (!plantId || !hallazgo.trim() || !responsableId) {
      return 'Completa la planta, la descripción y el responsable.';
    }
    if (!conMejora) return null;
    if (!tipo) return 'Selecciona el tipo de registro: define qué cláusula aplica.';
    if (!origen) return 'Selecciona cómo se detectó.';
    if (esSalidaNoConforme && (!sku.trim() || !lote.trim() || !producto.trim() || !cantidad.trim())) {
      return 'Una salida no conforme exige identificar SKU, lote, producto y cantidad (§8.7).';
    }
    if (esReclamo && (!cliente.trim() || !canal.trim())) {
      return 'Un reclamo exige identificar al cliente y el canal (§9.1.2).';
    }
    return null;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const problema = validar();
    if (problema) {
      setError(problema);
      return;
    }
    setError(null);
    const nc = addNonConformity({
      tenantId,
      plantId,
      auditId: defaultAuditId,
      hallazgo: hallazgo.trim(),
      criticidad,
      responsableId,
      ...(conMejora && tipo ? { tipoRegistro: tipo } : {}),
    });
    router.push(`/no-conformidades/${nc.id}`);
  }

  return (
    <div className="w-full max-w-2xl rounded-card border border-slate-200 bg-white p-6">
      <h1 className="text-xl font-semibold text-slate-900">
        {conMejora ? 'Registrar mejora' : 'Registrar hallazgo'}
      </h1>
      <p className="mt-1 text-sm text-slate-500">
        {conMejora
          ? 'El tipo define qué cláusula aplica y qué datos se piden.'
          : 'Formulario rápido, pensado también para uso en terreno.'}
      </p>

      <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-4" noValidate>
        {conMejora && (
          <>
            <FormField label="Tipo de registro" htmlFor={`${formId}-tipo`} required>
              <select
                id={`${formId}-tipo`}
                className={SELECT}
                value={tipo}
                onChange={(e) => setTipo(e.target.value as TipoRegistroMejora)}
              >
                <option value="">Seleccione…</option>
                {TIPOS_REGISTRO_MEJORA.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </FormField>
            {clausula && (
              <p className="-mt-2 text-xs text-slate-500">
                Se tratará según <span className="font-medium text-slate-700">{clausula}</span>.
              </p>
            )}

            <FormField label="Tipo de detección" htmlFor={`${formId}-origen`} required>
              <select
                id={`${formId}-origen`}
                className={SELECT}
                value={origen}
                onChange={(e) => setOrigen(e.target.value as OrigenDeteccion)}
              >
                <option value="">Seleccione…</option>
                {ORIGENES_DETECCION.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </FormField>
          </>
        )}

        <FormField label="Planta" htmlFor={`${formId}-planta`} required>
          <select
            id={`${formId}-planta`}
            className={SELECT}
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

        {conMejora && (
          <FormField label="Proceso involucrado" htmlFor={`${formId}-proceso`}>
            <select
              id={`${formId}-proceso`}
              className={SELECT}
              value={procesoId}
              onChange={(e) => setProcesoId(e.target.value)}
            >
              <option value="">Seleccione…</option>
              {procesos.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </select>
          </FormField>
        )}

        {conMejora && esSalidaNoConforme && (
          <fieldset className="rounded-lg border border-slate-200 p-4">
            <legend className="px-1 text-sm font-medium text-slate-700">
              Producto afectado (§8.7)
            </legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="SKU" htmlFor={`${formId}-sku`} required>
                <input id={`${formId}-sku`} className={SELECT} value={sku} onChange={(e) => setSku(e.target.value)} />
              </FormField>
              <FormField label="Lote" htmlFor={`${formId}-lote`} required>
                <input id={`${formId}-lote`} className={SELECT} value={lote} onChange={(e) => setLote(e.target.value)} />
              </FormField>
              <FormField label="Nombre del producto" htmlFor={`${formId}-producto`} required>
                <input
                  id={`${formId}-producto`}
                  className={SELECT}
                  value={producto}
                  onChange={(e) => setProducto(e.target.value)}
                />
              </FormField>
              <FormField label="Cantidad" htmlFor={`${formId}-cantidad`} required>
                <div className="flex gap-2">
                  <input
                    id={`${formId}-cantidad`}
                    type="number"
                    min="0"
                    className={SELECT}
                    value={cantidad}
                    onChange={(e) => setCantidad(e.target.value)}
                  />
                  <select
                    aria-label="Unidad"
                    className={`${SELECT} w-32`}
                    value={unidad}
                    onChange={(e) => setUnidad(e.target.value)}
                  >
                    <option value="unidades">unidades</option>
                    <option value="kg">kg</option>
                    <option value="L">L</option>
                  </select>
                </div>
              </FormField>
            </div>
          </fieldset>
        )}

        {conMejora && esReclamo && (
          <fieldset className="rounded-lg border border-slate-200 p-4">
            <legend className="px-1 text-sm font-medium text-slate-700">Reclamo (§9.1.2)</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Cliente" htmlFor={`${formId}-cliente`} required>
                <input
                  id={`${formId}-cliente`}
                  className={SELECT}
                  value={cliente}
                  onChange={(e) => setCliente(e.target.value)}
                />
              </FormField>
              <FormField label="Canal" htmlFor={`${formId}-canal`} required>
                <input
                  id={`${formId}-canal`}
                  className={SELECT}
                  value={canal}
                  onChange={(e) => setCanal(e.target.value)}
                  placeholder="Correo, teléfono, visita…"
                />
              </FormField>
            </div>
          </fieldset>
        )}

        <FormField
          label={conMejora ? 'Descripción (hallazgo)' : 'Hallazgo'}
          htmlFor={`${formId}-hallazgo`}
          required
          error={error ?? undefined}
        >
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
            className={SELECT}
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
          {conMejora ? 'Registrar mejora' : 'Registrar hallazgo'}
        </Button>
      </form>
    </div>
  );
}
