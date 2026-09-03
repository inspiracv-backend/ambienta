'use client';

import { useCallback, useEffect, useId, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Button, Spinner } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { api, mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';
import {
  contratosCompatibles,
  mapContratoParaPromover,
  type ContratoParaPromover,
  type EmpresaCrm,
  type TratoCrm,
} from '@/lib/crm';
import type { Resultado } from '@/lib/crm-empresas-store';

/**
 * Promover un trato ganado al contrato que lo materializó (RF-66, #82).
 *
 * ## No crea el contrato: lo enlaza
 *
 * Crear un contrato exige que el cliente ya exista como tenant de la
 * plataforma, que es un alta con su propio flujo. Hacerlo acá de paso
 * produciría empresas a medias creadas por cerrar una venta. Por eso el
 * formulario **elige** entre los contratos que ya hay, y dice qué hacer cuando
 * no hay ninguno.
 *
 * ## Los contratos se piden al abrir, no con la ficha
 *
 * La ficha de una empresa se abre muchas veces y se promueve una. Traer la
 * lista de contratos en cada carga sería una petición de más en el caso normal.
 *
 * ## Y se filtran los que el servidor va a rechazar
 *
 * Si la ficha ya nombra a un cliente de la plataforma, un contrato de otro
 * cliente responde **409**. Ofrecerlo en el selector sería ofrecer una opción
 * que falla; la barrera sigue siendo el servidor.
 */
export function PromoverTratoModal({
  open,
  onOpenChange,
  empresa,
  trato,
  onPromover,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  empresa: EmpresaCrm;
  trato: TratoCrm | null;
  onPromover: (tratoId: string, contratoId: string) => Promise<Resultado>;
}) {
  const formId = useId();
  const { user } = useSession();
  const [contratos, setContratos] = useState<ContratoParaPromover[]>([]);
  const [cargando, setCargando] = useState(false);
  const [errorDeCarga, setErrorDeCarga] = useState<string | null>(null);
  const [contratoId, setContratoId] = useState('');
  const [promoviendo, setPromoviendo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!user?.tenantId) return;
    setCargando(true);
    try {
      const raw = await api.get<Record<string, unknown>[]>('/contracts/?limit=500', {
        tenantId: user.tenantId,
      });
      const compatibles = contratosCompatibles(
        empresa,
        raw.map(mapContratoParaPromover),
      );
      setContratos(compatibles);
      setContratoId(compatibles[0]?.id ?? '');
      setErrorDeCarga(null);
    } catch (e) {
      // Lista vacía **y** el motivo. Sin el mensaje, "no hay contratos" y "no
      // se pudo preguntar" se ven exactamente igual, y el primero llevaría a
      // crear un contrato que quizá ya existe.
      setContratos([]);
      setErrorDeCarga(mensajeDeError(e));
    } finally {
      setCargando(false);
    }
  }, [user?.tenantId, empresa]);

  useEffect(() => {
    if (!open) return;
    setError(null);
    void cargar();
  }, [open, cargar]);

  const puedePromover = contratoId !== '' && trato !== null && !promoviendo;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!puedePromover || !trato) return;
    setPromoviendo(true);
    setError(null);

    const r = await onPromover(trato.id, contratoId);

    setPromoviendo(false);
    if (r.ok) {
      onOpenChange(false);
      return;
    }
    setError(r.error ?? 'No se pudo promover el trato.');
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-full max-w-md -translate-x-1/2 -translate-y-1/2 flex-col rounded-card bg-white shadow-lg">
          <div className="flex items-start justify-between border-b border-slate-200 p-6">
            <div>
              <Dialog.Title className="text-lg font-semibold text-slate-900">
                Promover a contrato
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-slate-500">
                {trato ? trato.titulo : ''}
              </Dialog.Description>
            </div>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <form onSubmit={enviar} className="flex min-h-0 flex-1 flex-col">
            <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
              {cargando && (
                <p className="flex items-center gap-2 text-sm text-slate-500">
                  <Spinner className="h-4 w-4" />
                  Buscando contratos…
                </p>
              )}

              {errorDeCarga && !cargando && (
                <p
                  role="alert"
                  className="rounded-lg border border-semaforo-incumple/30 bg-semaforo-incumple-bg px-3 py-2 text-sm text-semaforo-incumple"
                >
                  No se pudo traer la lista de contratos: {errorDeCarga}
                </p>
              )}

              {!cargando && !errorDeCarga && contratos.length === 0 && (
                <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                  No hay contratos a los que enlazar este trato
                  {empresa.clienteTenantId
                    ? ' para el cliente que nombra esta ficha'
                    : ''}
                  . El contrato se crea en Contratos, con el cliente ya dado de alta
                  en la plataforma; después se vuelve acá.
                </p>
              )}

              {!cargando && contratos.length > 0 && (
                <FormField
                  label="Contrato"
                  htmlFor={`${formId}-contrato`}
                  hint="El trato queda enlazado a este contrato y la ficha pasa a cliente."
                >
                  <select
                    id={`${formId}-contrato`}
                    value={contratoId}
                    onChange={(e) => setContratoId(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                  >
                    {contratos.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.numero} · {c.titulo}
                      </option>
                    ))}
                  </select>
                </FormField>
              )}

              {error && (
                <p
                  role="alert"
                  className="rounded-lg border border-semaforo-incumple/30 bg-semaforo-incumple-bg px-3 py-2 text-sm text-semaforo-incumple"
                >
                  {error}
                </p>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-200 p-4">
              <Dialog.Close asChild>
                <Button type="button" variant="secondary">
                  Cancelar
                </Button>
              </Dialog.Close>
              <Button type="submit" disabled={!puedePromover}>
                {promoviendo ? 'Promoviendo…' : 'Promover'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
