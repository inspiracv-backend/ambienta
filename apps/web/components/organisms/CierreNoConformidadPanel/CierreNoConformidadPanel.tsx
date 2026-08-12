'use client';

import { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { FEATURE_FLAGS, type NonConformity } from '@ambienta/shared';
import { Button } from '@/components/atoms';
import { useAudits } from '@/lib/audits-store';
import { getUserName } from '@/lib/get-user-name';

function formatFecha(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

interface Props {
  nonConformity: NonConformity;
  responsableOptions: { id: string; nombre: string }[];
  /**
   * Resultado de la Etapa de Seguimiento (§10.2.1 d).
   * `null` = sin responder, que no habilita: solo `true` lo hace.
   */
  eficaciaVerificada?: boolean | null;
}

/**
 * Cierre con firma de una no conformidad (RF-49).
 *
 * Vive en su propio componente y no dentro del detalle **por orden de lectura**:
 * el cierre es el ultimo acto del tratamiento, asi que tiene que renderizarse
 * despues de las etapas. Cuando estaba embebido en el detalle, la pantalla
 * pedia firmar antes de mostrar el trabajo que se estaba cerrando.
 *
 * Es el unico punto de cierre del sistema: es el que registra en el audit log,
 * y tener un segundo boton en otra parte dejaria uno de los dos salteando la
 * verificacion de eficacia.
 */
export function CierreNoConformidadPanel({
  nonConformity: nc,
  responsableOptions,
  eficaciaVerificada,
}: Props) {
  const { closeNonConformity } = useAudits();
  const [cierreResponsableId, setCierreResponsableId] = useState(nc.responsableId);
  const [firmada, setFirmada] = useState(false);

  const exigeEficacia = FEATURE_FLAGS.registroMejora;
  const eficaciaOk = !exigeEficacia || eficaciaVerificada === true;
  const puedeCerrar = nc.estado !== 'cerrada' && eficaciaOk;

  function handleCerrar() {
    if (!firmada || !puedeCerrar) return;
    closeNonConformity(nc.id, cierreResponsableId);
  }

  return (
    <div className="rounded-card border border-slate-200 bg-white p-6">
      <h2 className="mb-3 text-sm font-semibold text-slate-700">Cierre</h2>
      {nc.cierre ? (
        <div className="flex items-center gap-2 text-sm text-semaforo-cumple">
          <CheckCircle2 className="h-4 w-4" aria-hidden />
          Cerrada el {formatFecha(nc.cierre.fecha)} por {getUserName(nc.cierre.responsableId)}{' '}
          (firmada)
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-600">Responsable del cierre</span>
            <select
              className="h-11 w-full max-w-xs rounded-lg border border-slate-300 px-3 text-sm"
              value={cierreResponsableId}
              onChange={(e) => setCierreResponsableId(e.target.value)}
            >
              {responsableOptions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.nombre}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={firmada} onChange={(e) => setFirmada(e.target.checked)} />
            Firmo y confirmo el cierre de esta no conformidad (RF-49)
          </label>
          <Button onClick={handleCerrar} disabled={!firmada || !puedeCerrar} className="w-fit">
            Cerrar No Conformidad
          </Button>
          {exigeEficacia && !eficaciaOk && (
            <p className="text-sm text-slate-500">
              El cierre se habilita cuando la Etapa de Seguimiento verifica la eficacia como SI
              (§10.2.1 d).
            </p>
          )}
        </div>
      )}
    </div>
  );
}
