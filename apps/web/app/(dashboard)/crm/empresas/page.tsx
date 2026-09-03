'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, Building2, Plus, RefreshCw, Search } from 'lucide-react';
import { Button, Input, Spinner, StatusBadge } from '@/components/atoms';
import type { SemaforoStatus } from '@/components/atoms/StatusBadge/StatusBadge.types';
import { EmptyState, PageHeader } from '@/components/molecules';
import { EmpresaCrmModal } from '@/components/organisms';
import { ESTADO_DE_EMPRESA, type EmpresaCrm, type EstadoDeEmpresa } from '@/lib/crm';
import { useCrmEmpresas, type DatosDeEmpresa } from '@/lib/crm-empresas-store';

/**
 * La cartera comercial: prospectos y clientes (épica #32).
 *
 * ## Por qué existe esta pantalla
 *
 * La API del CRM tiene 28 operaciones y la interfaz llamaba a **dos**
 * —`/crm/pipeline` y mover de etapa—, desde una sola pantalla: el kanban.
 * Se podía mirar el tablero y arrastrar un trato, pero no dar de alta una
 * empresa — así que las oportunidades del kanban solo podían existir si alguien
 * las creaba por fuera del sistema. El módulo estaba completo por API e
 * inutilizable como producto.
 *
 * ## Prospecto y cliente no son lo mismo, y se distinguen a la vista
 *
 * Una empresa pasa a cliente cuando **existe en la plataforma** como tenant, y
 * eso es lo que habilita promover un trato ganado a contrato. Mostrar el estado
 * en la lista evita la pregunta de por qué el botón de promover no aparece en
 * unas y sí en otras.
 */

// Cliente es el estado 'bueno' del embudo, prospecto el intermedio, e inactiva
// el que pide atencion. Se reusa el semaforo de la plataforma en vez de
// inventar colores propios: es el mismo atomo de todas las pantallas.
const COLOR_DEL_ESTADO: Record<EstadoDeEmpresa, SemaforoStatus> = {
  client: 'cumple',
  prospect: 'pendiente',
  inactive: 'na',
};

export default function EmpresasCrmPage() {
  const { empresas, hayMas, cargando, errorDeCarga, crear, editar, recargar } = useCrmEmpresas();
  const [busqueda, setBusqueda] = useState('');
  const [enEdicion, setEnEdicion] = useState<EmpresaCrm | null>(null);
  const [modalAbierto, setModalAbierto] = useState(false);

  const filtradas = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return empresas;
    return empresas.filter(
      (e) =>
        e.nombre.toLowerCase().includes(q) ||
        (e.rut ?? '').toLowerCase().includes(q) ||
        (e.rubro ?? '').toLowerCase().includes(q),
    );
  }, [empresas, busqueda]);

  function abrirAlta() {
    setEnEdicion(null);
    setModalAbierto(true);
  }

  function abrirEdicion(empresa: EmpresaCrm) {
    setEnEdicion(empresa);
    setModalAbierto(true);
  }

  async function guardar(datos: DatosDeEmpresa) {
    return enEdicion ? editar(enEdicion.id, datos) : crear(datos);
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo="Empresas"
        descripcion="Prospectos y clientes de la cartera comercial. Desde acá se dan de alta las oportunidades del pipeline."
        acciones={
          <div className="flex gap-2">
            <Button
              variant="secondary"
              icon={<RefreshCw className="h-4 w-4" aria-hidden />}
              onClick={() => void recargar()}
            >
              Actualizar
            </Button>
            <Button icon={<Plus className="h-4 w-4" aria-hidden />} onClick={abrirAlta}>
              Nueva empresa
            </Button>
          </div>
        }
      />

      {cargando && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="h-4 w-4" />
          Cargando la cartera…
        </div>
      )}

      {errorDeCarga && !cargando && (
        <div className="rounded-card border border-semaforo-incumple/30 bg-semaforo-incumple-bg p-4">
          <p className="flex items-center gap-2 text-sm font-medium text-semaforo-incumple">
            <AlertTriangle className="h-4 w-4" aria-hidden />
            No se pudo cargar la cartera.
          </p>
          {/* Se dice qué NO se sabe. Una lista vacía acá afirmaría que la
              empresa no tiene ni un prospecto. */}
          <p className="mt-1 text-xs text-slate-600">
            No se muestra ninguna empresa porque no sabemos cuáles hay, no porque no haya.
          </p>
          <button
            type="button"
            onClick={() => void recargar()}
            className="mt-2 text-xs font-semibold text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            Reintentar
          </button>
        </div>
      )}

      {!cargando && !errorDeCarga && empresas.length === 0 && (
        <EmptyState
          icono={Building2}
          titulo="Todavía no hay empresas"
          descripcion="Da de alta el primer prospecto para poder registrarle oportunidades y actividades."
          accion={<Button onClick={abrirAlta}>Nueva empresa</Button>}
        />
      )}

      {!cargando && !errorDeCarga && empresas.length > 0 && (
        <>
          <div className="max-w-sm">
            <label className="sr-only" htmlFor="buscar-empresa">
              Buscar empresa
            </label>
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                aria-hidden
              />
              <Input
                id="buscar-empresa"
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                placeholder="Nombre, RUT o rubro"
                className="pl-9"
              />
            </div>
          </div>

          <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
            <table className="w-full min-w-[44rem] text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th scope="col" className="px-4 py-3">Empresa</th>
                  <th scope="col" className="px-4 py-3">RUT</th>
                  <th scope="col" className="px-4 py-3">Rubro</th>
                  <th scope="col" className="px-4 py-3">Estado</th>
                  <th scope="col" className="px-4 py-3">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filtradas.map((empresa) => (
                  <tr key={empresa.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link
                        href={`/crm/empresas/${empresa.id}`}
                        className="font-medium text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                      >
                        {empresa.nombre}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{empresa.rut ?? '—'}</td>
                    <td className="px-4 py-3 text-slate-500">{empresa.rubro ?? '—'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={COLOR_DEL_ESTADO[empresa.estado]} className="mr-1" />
                      <span className="text-slate-600">{ESTADO_DE_EMPRESA[empresa.estado]}</span>
                    </td>
                    <td className="px-4 py-3">
                      <Button variant="secondary" size="sm" onClick={() => abrirEdicion(empresa)}>
                        Editar
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* El corte se dice, no se esconde. Una cartera de 500 de 640 se ve
              perfectamente normal, y ese es justo el defecto que #167 llama
              «mas enganoso que no paginar». */}
          {hayMas && (
            <p className="rounded-card border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              La API cortó la lista en su tope: hay más empresas de las que se
              muestran acá. El buscador filtra solo lo que se alcanzó a traer, así
              que una empresa que no aparezca puede existir igual.
            </p>
          )}

          {filtradas.length === 0 && (
            <p className="text-sm text-slate-500">
              Ninguna empresa coincide con «{busqueda}».
            </p>
          )}
        </>
      )}

      <EmpresaCrmModal
        open={modalAbierto}
        onOpenChange={setModalAbierto}
        empresa={enEdicion}
        onGuardar={guardar}
      />
    </div>
  );
}
