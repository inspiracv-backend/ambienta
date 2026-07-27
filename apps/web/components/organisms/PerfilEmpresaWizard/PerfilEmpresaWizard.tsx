'use client';

import { useId, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { Check, Building2, MapPin, Users2, ClipboardCheck } from 'lucide-react';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { cn } from '@/lib/utils';
import { ROLE_LABEL } from '@/lib/roles';
import type { PerfilEmpresaWizardProps } from './PerfilEmpresaWizard.types';

const PASOS = [
  { label: 'Empresa', icon: Building2 },
  { label: 'Plantas', icon: MapPin },
  { label: 'Departamentos', icon: Users2 },
  { label: 'Trabajadores', icon: Users2 },
  { label: 'Confirmación', icon: ClipboardCheck },
] as const;

/**
 * Flujo obligatorio de Perfil Empresa (RF-10 a RF-12, v1.7) — sin prompt de
 * diseño propio (gap documentado en seccion-perfil-empresa.md), adaptado del
 * patrón de wizard de S-04 (barra de progreso + pasos + Atrás/Continuar).
 * Trabajadores y permisos se muestran de solo lectura: la edición vive en
 * Usuarios y Roles (Sección N, RF-06 a RF-58, aún no construida).
 */
export function PerfilEmpresaWizard({
  tenant,
  departamentos,
  usuarios,
  onUpdateDatosBasicos,
  onAddPlant,
  onAddDepartamento,
  onCompletar,
}: PerfilEmpresaWizardProps) {
  const formId = useId();
  const [paso, setPaso] = useState(0);
  const [maxPasoAlcanzado, setMaxPasoAlcanzado] = useState(0);

  const [giro, setGiro] = useState(tenant.giro ?? '');
  const [direccion, setDireccion] = useState(tenant.direccion ?? '');

  const [nombrePlanta, setNombrePlanta] = useState('');
  const [comunaPlanta, setComunaPlanta] = useState('');
  const [regionPlanta, setRegionPlanta] = useState('');

  const [nombreDepto, setNombreDepto] = useState('');

  const tenantDepartamentos = departamentos.filter((d) => d.tenantId === tenant.id);

  function irAPaso(next: number) {
    setPaso(next);
    setMaxPasoAlcanzado((prev) => Math.max(prev, next));
  }

  function handleAgregarPlanta(e: FormEvent) {
    e.preventDefault();
    if (!nombrePlanta.trim() || !comunaPlanta.trim() || !regionPlanta.trim()) return;
    onAddPlant({ nombre: nombrePlanta.trim(), comuna: comunaPlanta.trim(), region: regionPlanta.trim() });
    setNombrePlanta('');
    setComunaPlanta('');
    setRegionPlanta('');
  }

  function handleAgregarDepto(e: FormEvent) {
    e.preventDefault();
    if (!nombreDepto.trim()) return;
    onAddDepartamento(nombreDepto.trim());
    setNombreDepto('');
  }

  const puedeContinuarPaso0 = giro.trim().length > 0 && direccion.trim().length > 0;
  const puedeContinuarPaso1 = tenant.plants.length > 0;
  const puedeContinuarPaso2 = tenantDepartamentos.length > 0;

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Perfil Empresa</h1>
        <p className="text-sm text-slate-500">
          Antes de usar Matriz Legal u Obligaciones, completa la estructura de {tenant.nombre}.
        </p>
      </div>

      <ol className="flex items-center gap-2" aria-label="Pasos del Perfil Empresa">
        {PASOS.map((p, i) => {
          const StepIcon = p.icon;
          const activo = i === paso;
          const completado = i < maxPasoAlcanzado || (i === maxPasoAlcanzado && i < paso);
          const alcanzable = i <= maxPasoAlcanzado;
          return (
            <li key={p.label} className="flex flex-1 items-center gap-2">
              <button
                type="button"
                disabled={!alcanzable}
                onClick={() => alcanzable && irAPaso(i)}
                aria-current={activo ? 'step' : undefined}
                className={cn(
                  'flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-sm font-medium',
                  activo && 'border-brand-600 bg-brand-600 text-white',
                  !activo && completado && 'border-brand-300 bg-brand-50 text-brand-700',
                  !activo && !completado && 'border-slate-300 text-slate-400',
                  !alcanzable && 'cursor-not-allowed',
                )}
              >
                {completado && !activo ? <Check className="h-4 w-4" aria-hidden /> : <StepIcon className="h-4 w-4" aria-hidden />}
              </button>
              <span className={cn('hidden text-xs font-medium sm:block', activo ? 'text-slate-900' : 'text-slate-500')}>
                {p.label}
              </span>
              {i < PASOS.length - 1 && <span className="h-px flex-1 bg-slate-200" aria-hidden />}
            </li>
          );
        })}
      </ol>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        {paso === 0 && (
          <div className="flex flex-col gap-4">
            <h2 className="text-base font-semibold text-slate-900">Datos de la empresa</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <FormField label="Razón social" htmlFor={`${formId}-nombre`}>
                <Input id={`${formId}-nombre`} value={tenant.nombre} disabled className="bg-slate-50 text-slate-500" />
              </FormField>
              <FormField label="RUT" htmlFor={`${formId}-rut`}>
                <Input id={`${formId}-rut`} value={tenant.rut} disabled className="bg-slate-50 text-slate-500" />
              </FormField>
            </div>
            <FormField label="Giro" htmlFor={`${formId}-giro`} required hint="Actividad económica principal de la empresa.">
              <Input id={`${formId}-giro`} value={giro} onChange={(e) => setGiro(e.target.value)} />
            </FormField>
            <FormField label="Dirección" htmlFor={`${formId}-direccion`} required>
              <Input id={`${formId}-direccion`} value={direccion} onChange={(e) => setDireccion(e.target.value)} />
            </FormField>
          </div>
        )}

        {paso === 1 && (
          <div className="flex flex-col gap-4">
            <h2 className="text-base font-semibold text-slate-900">Plantas / Instalaciones</h2>
            <ul className="flex flex-col gap-2">
              {tenant.plants.map((plant) => (
                <li key={plant.id} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
                  <span className="font-medium text-slate-800">{plant.nombre}</span>{' '}
                  <span className="text-slate-500">— {plant.comuna}, {plant.region}</span>
                </li>
              ))}
              {tenant.plants.length === 0 && <p className="text-sm text-slate-500">Aún no hay plantas registradas.</p>}
            </ul>

            <form onSubmit={handleAgregarPlanta} className="grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-3">
              <FormField label="Nombre" htmlFor={`${formId}-planta-nombre`}>
                <Input id={`${formId}-planta-nombre`} value={nombrePlanta} onChange={(e) => setNombrePlanta(e.target.value)} />
              </FormField>
              <FormField label="Comuna" htmlFor={`${formId}-planta-comuna`}>
                <Input id={`${formId}-planta-comuna`} value={comunaPlanta} onChange={(e) => setComunaPlanta(e.target.value)} />
              </FormField>
              <FormField label="Región" htmlFor={`${formId}-planta-region`}>
                <Input id={`${formId}-planta-region`} value={regionPlanta} onChange={(e) => setRegionPlanta(e.target.value)} />
              </FormField>
              <Button type="submit" variant="secondary" className="sm:col-span-3 sm:w-fit">
                Agregar planta
              </Button>
            </form>
          </div>
        )}

        {paso === 2 && (
          <div className="flex flex-col gap-4">
            <h2 className="text-base font-semibold text-slate-900">Departamentos / Procesos</h2>
            <p className="text-sm text-slate-500">Todo Usuario Interno debe pertenecer a un departamento.</p>
            <ul className="flex flex-wrap gap-2">
              {tenantDepartamentos.map((d) => (
                <li key={d.id} className="rounded-full bg-brand-50 px-3 py-1 text-sm font-medium text-brand-700">
                  {d.nombre}
                </li>
              ))}
              {tenantDepartamentos.length === 0 && <p className="text-sm text-slate-500">Aún no hay departamentos.</p>}
            </ul>

            <form onSubmit={handleAgregarDepto} className="flex items-end gap-3 border-t border-slate-100 pt-4">
              <FormField label="Nuevo departamento" htmlFor={`${formId}-depto`}>
                <Input id={`${formId}-depto`} value={nombreDepto} onChange={(e) => setNombreDepto(e.target.value)} />
              </FormField>
              <Button type="submit" variant="secondary">
                Agregar
              </Button>
            </form>
          </div>
        )}

        {paso === 3 && (
          <div className="flex flex-col gap-4">
            <h2 className="text-base font-semibold text-slate-900">Trabajadores y permisos</h2>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full min-w-[480px] text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                    <th scope="col" className="px-3 py-2">Nombre</th>
                    <th scope="col" className="px-3 py-2">Rol</th>
                    <th scope="col" className="px-3 py-2">Departamento</th>
                  </tr>
                </thead>
                <tbody>
                  {usuarios.map((u) => (
                    <tr key={u.id} className="border-b border-slate-100 last:border-0">
                      <td className="px-3 py-2 text-slate-800">{u.nombre}</td>
                      <td className="px-3 py-2">
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                          {ROLE_LABEL[u.role]}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-slate-500">
                        {departamentos.find((d) => d.id === u.departamentoId)?.nombre ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-400">
              Asignar/reasignar departamento e invitar nuevos trabajadores se gestiona desde{' '}
              <Link href="/usuarios" className="font-medium text-brand-600 hover:underline">
                Usuarios y Roles
              </Link>
              .
            </p>
          </div>
        )}

        {paso === 4 && (
          <div className="flex flex-col gap-4">
            <h2 className="text-base font-semibold text-slate-900">Confirmación</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <dt className="text-slate-500">Giro</dt>
              <dd className="text-slate-800">{giro}</dd>
              <dt className="text-slate-500">Dirección</dt>
              <dd className="text-slate-800">{direccion}</dd>
              <dt className="text-slate-500">Plantas</dt>
              <dd className="text-slate-800">{tenant.plants.length}</dd>
              <dt className="text-slate-500">Departamentos</dt>
              <dd className="text-slate-800">{tenantDepartamentos.length}</dd>
              <dt className="text-slate-500">Trabajadores</dt>
              <dd className="text-slate-800">{usuarios.length}</dd>
            </dl>
            <p className="text-sm text-slate-500">
              Al finalizar, podrás usar Matriz Legal, Obligaciones y el resto de la plataforma.
            </p>
          </div>
        )}
      </div>

      <div className="flex justify-between">
        <Button variant="secondary" disabled={paso === 0} onClick={() => setPaso((p) => Math.max(0, p - 1))}>
          Atrás
        </Button>
        {paso < PASOS.length - 1 ? (
          <Button
            disabled={(paso === 0 && !puedeContinuarPaso0) || (paso === 1 && !puedeContinuarPaso1) || (paso === 2 && !puedeContinuarPaso2)}
            onClick={() => {
              if (paso === 0) onUpdateDatosBasicos({ giro: giro.trim(), direccion: direccion.trim() });
              irAPaso(paso + 1);
            }}
          >
            Continuar
          </Button>
        ) : (
          <Button onClick={onCompletar}>Finalizar</Button>
        )}
      </div>
    </div>
  );
}
