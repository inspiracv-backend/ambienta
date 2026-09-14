'use client';

import { useEffect, useId, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import {
  FEATURE_FLAGS,
  ORIGENES_DETECCION,
  TIPOS_REGISTRO_MEJORA,
  type OrigenDeteccion,
  type TipoRegistroMejora,
} from '@ambienta/shared';
import { Button } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useAudits } from '@/lib/audits-store';
import { api, mensajeDeError } from '@/lib/api-client';
import { cargarCatalogos, type Severidad } from '@/lib/etapas-mejora';
import type { RegisterFindingFormProps } from './RegisterFindingForm.types';

/** Los origenes que exigen decir de que pregunta de la auditoria salio. */
const ORIGENES_DE_AUDITORIA: OrigenDeteccion[] = ['auditoria_interna', 'auditoria_externa'];

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
  // La escala sale del catalogo de la empresa, no de "Alta/Media/Baja" escrito
  // aca: esas etiquetas no eran las de nadie.
  const [severidades, setSeveridades] = useState<Severidad[] | null>(null);
  const [severidad, setSeveridad] = useState('');
  const [preguntas, setPreguntas] = useState<{ id: string; texto: string }[]>([]);
  const [auditItemId, setAuditItemId] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [responsableId, setResponsableId] = useState('');
  const [error, setError] = useState<string | null>(null);

  const [tipo, setTipo] = useState<TipoRegistroMejora | ''>('');
  const [origen, setOrigen] = useState<OrigenDeteccion | ''>(
    defaultAuditId ? 'auditoria_interna' : '',
  );
  const [sku, setSku] = useState('');
  const [lote, setLote] = useState('');
  const [producto, setProducto] = useState('');
  const [cantidad, setCantidad] = useState('');
  const [unidad, setUnidad] = useState('unidades');
  const [cliente, setCliente] = useState('');
  const [canal, setCanal] = useState('');

  useEffect(() => {
    if (!tenantId) return;
    cargarCatalogos(tenantId)
      .then((c) => {
        setSeveridades(c.severidades);
        const porDefecto = c.severidades.find((x) => x.code === 'major') ?? c.severidades[0];
        setSeveridad((actual) => actual || porDefecto?.code || '');
      })
      .catch((e) => setError(`No se pudo cargar la escala de severidad: ${mensajeDeError(e)}`));
  }, [tenantId]);

  useEffect(() => {
    if (!tenantId || !defaultAuditId) return;
    api
      .get<Record<string, unknown>[]>(`/audits/${defaultAuditId}/items`, { tenantId })
      .then((items) => setPreguntas(items.map((i) => ({ id: String(i.id), texto: `${i.sequence}. ${i.question}` }))))
      .catch(() => setPreguntas([]));
  }, [tenantId, defaultAuditId]);

  const esDeAuditoria = !!origen && ORIGENES_DE_AUDITORIA.includes(origen as OrigenDeteccion);
  // Sin auditoria de origen no hay pregunta que elegir, y la API exige una para
  // esos origenes: ofrecerlos seria un formulario que siempre falla.
  const origenes = defaultAuditId
    ? ORIGENES_DETECCION
    : ORIGENES_DETECCION.filter((o) => !ORIGENES_DE_AUDITORIA.includes(o.value));
  const esSalidaNoConforme = tipo === 'salida_no_conforme';
  const esReclamo = tipo === 'reclamo';
  const clausula = TIPOS_REGISTRO_MEJORA.find((t) => t.value === tipo)?.clausula;

  function validar(): string | null {
    if (!plantId || !hallazgo.trim() || !responsableId) {
      return 'Completa la planta, la descripción y el responsable.';
    }
    if (!severidad) return 'Selecciona la severidad.';
    if (!conMejora) return null;
    if (!tipo) return 'Selecciona el tipo de registro: define qué cláusula aplica.';
    if (!origen) return 'Selecciona cómo se detectó.';
    if (esDeAuditoria && !auditItemId) return 'Indica de qué pregunta de la auditoría salió el hallazgo.';
    if (esSalidaNoConforme && (!sku.trim() || !lote.trim() || !producto.trim() || !cantidad.trim())) {
      return 'Una salida no conforme exige identificar SKU, lote, producto y cantidad (§8.7).';
    }
    if (esReclamo && (!cliente.trim() || !canal.trim())) {
      return 'Un reclamo exige identificar al cliente y el canal (§9.1.2).';
    }
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const problema = validar();
    if (problema) {
      setError(problema);
      return;
    }
    setError(null);
    setGuardando(true);
    try {
      const nc = await addNonConformity({
        tenantId,
        plantId,
        hallazgo: hallazgo.trim(),
        severidad,
        responsableId,
        ...(conMejora && tipo ? { tipoRegistro: tipo } : {}),
        ...(conMejora && origen ? { origen } : {}),
        ...(conMejora && esDeAuditoria ? { auditItemId } : {}),
        // Las claves son las que exige la base (`db/24`), no las del formulario.
        ...(conMejora && esSalidaNoConforme
          ? { productData: { sku: sku.trim(), lote: lote.trim(), nombre: producto.trim(), cantidad: cantidad.trim(), unidad } }
          : {}),
        ...(conMejora && esReclamo ? { complaintData: { cliente_nombre: cliente.trim(), canal: canal.trim() } } : {}),
      });
      // El id es el de la base: antes se navegaba a `nc-<timestamp>`, que no existia.
      router.push(`/no-conformidades/${nc.id}`);
    } catch (err) {
      setError(`No se registró: ${mensajeDeError(err)}`);
      setGuardando(false);
    }
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
                {origenes.map((o) => (
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

        {/* "Proceso involucrado" se quito el 13-sep: salia de departamentos de
            ejemplo y no se mandaba, porque el registro no tiene ese campo. */}
        {conMejora && esDeAuditoria && (
          <FormField label="Pregunta de la auditoría" htmlFor={`${formId}-pregunta`} required>
            <select
              id={`${formId}-pregunta`}
              className={SELECT}
              value={auditItemId}
              onChange={(e) => setAuditItemId(e.target.value)}
            >
              <option value="">Seleccione…</option>
              {preguntas.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.texto}
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

        <FormField label="Severidad" htmlFor={`${formId}-severidad`} required>
          {severidades === null ? (
            <p className="text-sm text-slate-500">Cargando la escala…</p>
          ) : (
            <div id={`${formId}-severidad`} className="flex gap-2">
              {severidades.map((c) => (
                <button
                  key={c.code}
                  type="button"
                  onClick={() => setSeveridad(c.code)}
                  aria-pressed={severidad === c.code}
                  className={
                    severidad === c.code
                      ? 'flex-1 rounded-lg border-2 border-brand-600 bg-brand-50 px-3 py-2 text-sm font-medium text-brand-700'
                      : 'flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600'
                  }
                >
                  {c.label}
                </button>
              ))}
            </div>
          )}
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

        <Button type="submit" className="mt-2 w-full" disabled={guardando}>
          {guardando ? 'Registrando…' : conMejora ? 'Registrar mejora' : 'Registrar hallazgo'}
        </Button>
      </form>
    </div>
  );
}
