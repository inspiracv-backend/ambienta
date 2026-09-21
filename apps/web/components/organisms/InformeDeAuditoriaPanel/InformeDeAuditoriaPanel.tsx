'use client';

import { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Button } from '@/components/atoms';
import { mensajeDeError } from '@/lib/api-client';
import type { Tenant } from '@ambienta/shared';
import { useSession } from '@/lib/session';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { InformeDeAuditoriaPdf } from '@/components/organisms/InformeDeAuditoriaPdf';
import {
  CLASIFICACION_LABEL,
  cargarInforme,
  guardarVeredicto,
  porcentaje,
  type Clasificacion,
  type FilaDeLaMatriz,
  type InformeDeAuditoria,
} from '@/lib/informe-auditoria';

/** La marca que, al imprimir, deja en la hoja solo el documento (`globals.css`). */
export const CLASE_IMPRIMIENDO_INFORME = 'imprimiendo-informe';

const ESTILO: Record<Clasificacion, string> = {
  conforme: 'bg-semaforo-cumple-bg text-semaforo-cumple',
  conforme_con_observaciones: 'bg-semaforo-parcial-bg text-semaforo-parcial',
  no_conforme: 'bg-semaforo-no-cumple-bg text-semaforo-no-cumple',
  // "No auditado" no es un semáforo: no dice nada bueno ni malo del proceso.
  no_auditado: 'bg-slate-100 text-slate-600',
};

/**
 * El informe de la auditoría (RF-101): resumen, matriz por proceso y tasa de
 * cierre del ciclo anterior. El auditor escribe acá el veredicto de cada
 * proceso; los conteos los calcula el servidor al pedirlo.
 */
export function InformeDeAuditoriaPanel({
  auditId,
  tenant,
}: {
  auditId: string;
  /** La empresa que emite el documento. Sin ella no se ofrece el PDF: un
      informe sin quien lo emite no sirve para entregar. */
  tenant?: Tenant;
}) {
  const { user } = useSession();
  const registrar = useRegistrarAuditoria();
  const tenantId = user?.tenantId ?? null;
  const [informe, setInforme] = useState<InformeDeAuditoria | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!tenantId) return;
    try {
      setInforme(await cargarInforme(auditId, tenantId));
      setError(null);
    } catch (e) {
      setError(mensajeDeError(e));
    }
  }, [auditId, tenantId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  // El documento se monta directo en <body> (ver abajo), y eso solo se puede
  // hacer en el navegador.
  const [montado, setMontado] = useState(false);
  useEffect(() => setMontado(true), []);

  const puedeEmitir = Boolean(tenant && user && informe);
  const emisor = tenant?.id;
  const codigo = informe?.codigo;
  const titulo = informe?.titulo;

  useEffect(() => {
    if (!puedeEmitir || !emisor) return;
    // **Imprimir en esta ficha es imprimir el informe**, venga del boton o de
    // Ctrl+P. Por eso se engancha en `beforeprint` y no en el clic: con el
    // clic, Ctrl+P sacaba la pantalla entera con el informe pegado al final, y
    // no quedaba anotado.
    function antes() {
      document.body.classList.add(CLASE_IMPRIMIENDO_INFORME);
      // Se anota que **se abrio la impresion**, no que se emitio: el navegador
      // no avisa si la persona cancela el dialogo.
      //
      // Y es el historial **de esta sesion**, no el registro del servidor:
      // `useRegistrarAuditoria` no llega a la API (lo dice `audit-log-store`),
      // y el `audit_log` solo anota lo que cambia por la ORM. Que la emision
      // quede guardada necesita un endpoint propio, que no existe.
      registrar({
        entidadTipo: 'auditoria',
        entidadId: auditId,
        entidadLabel: codigo ?? auditId,
        tenantId: emisor,
        accion: 'exportado',
        resumen: `Abrió la impresión del informe de "${titulo ?? auditId}" (imprimir o guardar PDF)`,
        cambios: [],
      });
    }
    function despues() {
      document.body.classList.remove(CLASE_IMPRIMIENDO_INFORME);
    }
    window.addEventListener('beforeprint', antes);
    window.addEventListener('afterprint', despues);
    return () => {
      window.removeEventListener('beforeprint', antes);
      window.removeEventListener('afterprint', despues);
      despues();
    };
  }, [puedeEmitir, emisor, registrar, auditId, codigo, titulo]);

  if (error) {
    return (
      <section className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-slate-900">Informe de auditoría</h2>
        <p className="mt-2 text-sm text-semaforo-no-cumple">No se pudo cargar el informe: {error}</p>
      </section>
    );
  }
  if (!informe) {
    return (
      <section className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-slate-900">Informe de auditoría</h2>
        <p className="mt-2 text-sm text-slate-500">Cargando informe…</p>
      </section>
    );
  }

  const r = informe.resumen;
  const cifras: { label: string; valor: string }[] = [
    { label: 'Conformidad', valor: porcentaje(r.conformidad) },
    { label: 'Procesos auditados', valor: String(r.procesos_auditados) },
    { label: 'No conformidades', valor: String(r.no_conformidades) },
    { label: 'Observaciones', valor: String(r.observaciones) },
    { label: 'Oportunidades de mejora', valor: String(r.oportunidades_de_mejora) },
  ];

  function imprimir() {
    // Lo demas —ocultar la pantalla y anotarlo— pasa en `beforeprint`, para
    // que Ctrl+P haga exactamente lo mismo.
    window.print();
  }

  return (
    <>
    <section className="rounded-card border border-slate-200 bg-white p-6 print:hidden">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Informe de auditoría</h2>
          <p className="mt-1 text-sm text-slate-500">
            {informe.codigo} · {informe.titulo}
          </p>
        </div>
        {tenant && user ? (
          <Button variant="secondary" size="sm" onClick={imprimir}>
            Imprimir / Guardar PDF
          </Button>
        ) : (
          // **Se dice por que no se puede, en vez de esconder el boton.** El
          // documento lleva quien lo emite —razon social, RUT, logo— y sin la
          // empresa cargada seria un informe sin emisor. Un boton que
          // desaparece se lee como que la funcion no existe.
          <p className="max-w-xs text-xs text-slate-500">
            Para emitir el PDF falta cargar la empresa que lo emite. Recarga la
            pagina; si sigue igual, es que no se pudo leer su ficha.
          </p>
        )}
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {cifras.map((c) => (
          <div key={c.label} className="rounded-lg border border-slate-100 p-3">
            <dt className="text-xs text-slate-500">{c.label}</dt>
            <dd className="mt-1 text-lg font-semibold tabular-nums text-slate-900">{c.valor}</dd>
          </div>
        ))}
      </dl>
      {r.items_sin_proceso > 0 && (
        <p className="mt-2 text-xs text-slate-500">
          {r.items_sin_proceso} pregunta(s) son requisitos generales del sistema de gestión y no cuentan en ningún proceso.
        </p>
      )}

      <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
        <span className="font-medium">Tasa de cierre del ciclo anterior: </span>
        {informe.tasa_de_cierre_del_ciclo_anterior !== null
          ? porcentaje(informe.tasa_de_cierre_del_ciclo_anterior)
          : `No aplica — ${informe.motivo_sin_tasa ?? 'sin ciclo anterior comparable'}`}
      </div>

      <h3 className="mt-6 text-sm font-semibold text-slate-700">Matriz por proceso</h3>
      {informe.matriz.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">
          Ninguna pregunta de esta auditoría está asociada a un proceso, así que no hay filas que mostrar.
        </p>
      ) : (
        <ul className="mt-2 flex flex-col gap-3">
          {informe.matriz.map((fila) => (
            <FilaProceso
              key={fila.proceso_id}
              fila={fila}
              auditId={auditId}
              tenantId={tenantId}
              onGuardado={cargar}
              // Cerrada o cancelada, la API responde 409: ofrecer el editor seria
              // un boton que falla siempre.
              editable={informe.estado !== 'closed' && informe.estado !== 'cancelled'}
            />
          ))}
        </ul>
      )}
    </section>

    {/* El documento entregable, con el mismo informe que muestra el panel.
        **Se monta directo en <body>** y no aca adentro: asi, al imprimir, la
        hoja puede ocultar a todos los demas hijos de <body> —la ficha entera—
        sin tener que marcar uno por uno lo que no es el informe. */}
    {montado &&
      tenant &&
      user &&
      createPortal(
        <div className="solo-impresion">
          <InformeDeAuditoriaPdf tenant={tenant} informe={informe} emitidoPor={user.nombre} />
        </div>,
        document.body,
      )}
    </>
  );
}

function FilaProceso({
  fila,
  auditId,
  tenantId,
  onGuardado,
  editable,
}: {
  editable: boolean;
  fila: FilaDeLaMatriz;
  auditId: string;
  tenantId: string | null;
  onGuardado: () => Promise<void>;
}) {
  const [editando, setEditando] = useState(false);
  const [clasificacion, setClasificacion] = useState<Clasificacion>(fila.clasificacion);
  const [conclusion, setConclusion] = useState(fila.conclusion ?? '');
  const [evidencia, setEvidencia] = useState(fila.evidencia_revisada ?? '');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function guardar() {
    if (!tenantId) return;
    setGuardando(true);
    try {
      await guardarVeredicto(
        auditId,
        fila.proceso_id,
        { classification: clasificacion, conclusion: conclusion.trim() || null, evidence_reviewed: evidencia.trim() || null },
        tenantId,
      );
      setError(null);
      setEditando(false);
      await onGuardado();
    } catch (e) {
      setError(`No se guardó el veredicto: ${mensajeDeError(e)}`);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <li className="rounded-lg border border-slate-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium text-slate-800">{fila.proceso_nombre}</p>
          <p className="text-xs text-slate-500">
            {fila.items} pregunta(s) · {fila.items_conformes} conformes · {fila.items_no_conformes} no conformes
            {fila.clausulas_auditadas.length > 0 ? ` · cláusulas ${fila.clausulas_auditadas.join(', ')}` : ''}
          </p>
          {fila.hallazgos.length > 0 && <p className="text-xs text-slate-500">Hallazgos: {fila.hallazgos.join(', ')}</p>}
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${ESTILO[fila.clasificacion]}`}>
          {CLASIFICACION_LABEL[fila.clasificacion]}
        </span>
      </div>
      {!editando && fila.conclusion && <p className="mt-2 text-sm text-slate-700">{fila.conclusion}</p>}

      {editando ? (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-600">Veredicto</span>
            <select
              className="h-11 rounded-lg border border-slate-300 px-3 text-sm"
              value={clasificacion}
              onChange={(e) => setClasificacion(e.target.value as Clasificacion)}
            >
              {(Object.keys(CLASIFICACION_LABEL) as Clasificacion[]).map((c) => (
                <option key={c} value={c}>{CLASIFICACION_LABEL[c]}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm sm:col-span-2">
            <span className="font-medium text-slate-600">Conclusión</span>
            <textarea rows={2} className="rounded-lg border border-slate-300 p-3 text-sm" value={conclusion} onChange={(e) => setConclusion(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-sm sm:col-span-2">
            <span className="font-medium text-slate-600">Evidencia revisada</span>
            <textarea rows={2} className="rounded-lg border border-slate-300 p-3 text-sm" value={evidencia} onChange={(e) => setEvidencia(e.target.value)} />
          </label>
          <div className="flex gap-2 sm:col-span-2">
            <Button type="button" onClick={guardar} disabled={guardando}>
              {guardando ? 'Guardando…' : 'Guardar veredicto'}
            </Button>
            <Button type="button" variant="secondary" onClick={() => setEditando(false)} disabled={guardando}>
              Cancelar
            </Button>
          </div>
        </div>
      ) : editable ? (
        <Button type="button" variant="secondary" className="mt-3" onClick={() => setEditando(true)}>
          {fila.clasificacion === 'no_auditado' && !fila.conclusion ? 'Dejar veredicto' : 'Editar veredicto'}
        </Button>
      ) : null}
      {error && <p className="mt-2 text-sm text-semaforo-no-cumple">{error}</p>}
    </li>
  );
}
