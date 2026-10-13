'use client';

import { useEffect, useId, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Button, Input, Textarea } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { mensajeDeError } from '@/lib/api-client';
import { usePersonasAsignables } from '@/lib/crm-etapas-store';
import {
  TIPO_AUDITORIA_LABEL,
  crearAuditoria,
  listarCodigos,
  sugerirCodigo,
  type NuevaAuditoria,
  type TipoAuditoria,
} from '@/lib/ciclo-de-auditoria';

export interface NuevaAuditoriaModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tenantId: string;
  plantas: { id: string; nombre: string }[];
  /** Con la fila que devolvió la API, ya con su id real. */
  onCreada: (raw: Record<string, unknown>) => void;
}

const VACIA: NuevaAuditoria = {
  codigo: '',
  titulo: '',
  tipo: 'internal',
  alcance: '',
  plantaId: null,
  inicio: '',
  fin: '',
  auditorLiderId: null,
};

/**
 * Planificar una auditoría (S-20, RF-92).
 *
 * **Espera a la base.** No agrega una fila optimista: la auditoría recién creada
 * se abre en su ficha, y una ficha con un id que la base no tiene es un 404.
 * El código lo propone la pantalla, pero la unicidad la decide la base
 * (`uq_audits_tenant_code`): si otra persona tomó el mismo, el 409 se muestra
 * tal cual y el formulario queda con lo escrito.
 */
export function NuevaAuditoriaModal({ open, onOpenChange, tenantId, plantas, onCreada }: NuevaAuditoriaModalProps) {
  const formId = useId();
  const { personas } = usePersonasAsignables();
  const [datos, setDatos] = useState<NuevaAuditoria>(VACIA);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);
  const [listaCortada, setListaCortada] = useState(false);

  useEffect(() => {
    if (!open) return;
    let vigente = true;
    listarCodigos(tenantId)
      .then(({ codigos, cortada }) => {
        // Con la lista cortada la sugerencia podría chocar con un código que no
        // se alcanzó a mirar: se deja el campo vacío y se dice por qué.
        if (!vigente || cortada) {
          if (vigente) setListaCortada(true);
          return;
        }
        setDatos((d) => (d.codigo ? d : { ...d, codigo: sugerirCodigo(codigos, new Date().getFullYear()) }));
      })
      // Sin la lista no hay sugerencia: el campo queda vacío y se escribe a mano.
      .catch(() => {});
    return () => {
      vigente = false;
    };
  }, [open, tenantId]);

  function cambiar<K extends keyof NuevaAuditoria>(campo: K, valor: NuevaAuditoria[K]) {
    setDatos((d) => ({ ...d, [campo]: valor }));
  }

  function cerrar(abierto: boolean) {
    onOpenChange(abierto);
    if (!abierto) {
      setDatos(VACIA);
      setErrores({});
    }
  }

  async function enviar(e: FormEvent) {
    e.preventDefault();
    const siguientes: Record<string, string> = {};
    if (!datos.codigo.trim()) siguientes.codigo = 'Ingresa un código.';
    if (!datos.titulo.trim()) siguientes.titulo = 'Ingresa un título.';
    if (!datos.alcance.trim()) siguientes.alcance = 'Describe qué se va a auditar.';
    if (datos.inicio && datos.fin && datos.fin < datos.inicio) {
      siguientes.fin = 'El término no puede ser anterior al inicio.';
    }
    setErrores(siguientes);
    if (Object.keys(siguientes).length > 0) return;

    setEnviando(true);
    try {
      const creada = await crearAuditoria(tenantId, datos);
      onCreada(creada);
      cerrar(false);
    } catch (err) {
      setErrores({ envio: `No se creó la auditoría: ${mensajeDeError(err)}` });
    } finally {
      setEnviando(false);
    }
  }

  const select = 'h-11 w-full rounded-lg border border-slate-300 px-3 text-sm';

  return (
    <Dialog.Root open={open} onOpenChange={cerrar}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-card bg-white p-6 shadow-lg">
          <div className="flex items-start justify-between">
            <Dialog.Title className="text-lg font-semibold text-slate-900">Nueva auditoría</Dialog.Title>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>
          <Dialog.Description className="mt-1 text-xs text-slate-500">
            Queda planificada. El checklist se carga desde su ficha.
          </Dialog.Description>

          <form onSubmit={enviar} className="mt-4 flex flex-col gap-4" noValidate>
            <div className="grid gap-4 sm:grid-cols-[10rem_1fr]">
              <FormField
                label="Código"
                htmlFor={`${formId}-codigo`}
                required
                error={errores.codigo}
                hint={listaCortada ? 'Hay más auditorías de las que se pudieron revisar: escribe el código.' : undefined}
              >
                <Input
                  id={`${formId}-codigo`}
                  value={datos.codigo}
                  invalid={!!errores.codigo}
                  onChange={(e) => cambiar('codigo', e.target.value)}
                />
              </FormField>
              <FormField label="Título" htmlFor={`${formId}-titulo`} required error={errores.titulo}>
                <Input
                  id={`${formId}-titulo`}
                  value={datos.titulo}
                  invalid={!!errores.titulo}
                  onChange={(e) => cambiar('titulo', e.target.value)}
                />
              </FormField>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Tipo" htmlFor={`${formId}-tipo`}>
                <select
                  id={`${formId}-tipo`}
                  className={select}
                  value={datos.tipo}
                  onChange={(e) => cambiar('tipo', e.target.value as TipoAuditoria)}
                >
                  {(Object.keys(TIPO_AUDITORIA_LABEL) as TipoAuditoria[]).map((t) => (
                    <option key={t} value={t}>
                      {TIPO_AUDITORIA_LABEL[t]}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField label="Planta" htmlFor={`${formId}-planta`} hint="Vacío: toda la empresa">
                <select
                  id={`${formId}-planta`}
                  className={select}
                  value={datos.plantaId ?? ''}
                  onChange={(e) => cambiar('plantaId', e.target.value || null)}
                >
                  <option value="">Toda la empresa</option>
                  {plantas.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nombre}
                    </option>
                  ))}
                </select>
              </FormField>
            </div>

            <FormField label="Alcance" htmlFor={`${formId}-alcance`} required error={errores.alcance}>
              <Textarea
                id={`${formId}-alcance`}
                rows={2}
                value={datos.alcance}
                onChange={(e) => cambiar('alcance', e.target.value)}
              />
            </FormField>

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Inicio planificado" htmlFor={`${formId}-inicio`}>
                <Input
                  id={`${formId}-inicio`}
                  type="date"
                  value={datos.inicio}
                  onChange={(e) => cambiar('inicio', e.target.value)}
                />
              </FormField>
              <FormField label="Término planificado" htmlFor={`${formId}-fin`} error={errores.fin}>
                <Input
                  id={`${formId}-fin`}
                  type="date"
                  value={datos.fin}
                  invalid={!!errores.fin}
                  onChange={(e) => cambiar('fin', e.target.value)}
                />
              </FormField>
            </div>

            <FormField label="Auditor líder" htmlFor={`${formId}-lider`}>
              <select
                id={`${formId}-lider`}
                className={select}
                value={datos.auditorLiderId ?? ''}
                onChange={(e) => cambiar('auditorLiderId', e.target.value || null)}
              >
                <option value="">Sin asignar</option>
                {personas.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre}
                  </option>
                ))}
              </select>
            </FormField>

            {errores.envio && (
              <p role="alert" className="text-sm text-semaforo-no-cumple">
                {errores.envio}
              </p>
            )}

            <div className="flex justify-end gap-2">
              <Dialog.Close asChild>
                <Button type="button" variant="secondary">
                  Cancelar
                </Button>
              </Dialog.Close>
              <Button type="submit" disabled={enviando}>
                {enviando ? 'Creando…' : 'Crear auditoría'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
