'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Departamento, TipoProceso } from '@ambienta/shared';
import { nombreTipoProceso } from '@ambienta/shared';
import { mockDepartamentos } from '@/mocks/departamentos';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';

interface DepartamentosContextValue {
  departamentos: Departamento[];
  addDepartamento: (input: {
    tenantId: string;
    nombre: string;
    tipo: TipoProceso;
    descripcion?: string;
    responsableId?: string | null;
  }) => void;
  updateTipo: (departamentoId: string, tipo: TipoProceso) => void;
}

const DepartamentosContext = createContext<DepartamentosContextValue | null>(null);

/**
 * Departamentos/procesos del Perfil Empresa (RF-11, RF-12) — estado en
 * memoria, mismo patrón que los demás stores.
 *
 * Se pide el **tipo de proceso** al crear y no después: clasificarlo es lo que
 * convierte una lista de áreas en un mapa de procesos (ISO 9001 §4.4), y
 * dejarlo opcional garantiza que nadie lo complete y el mapa quede inservible.
 */
export function DepartamentosProvider({ children }: { children: ReactNode }) {
  const [departamentos, setDepartamentos] = useState<Departamento[]>(mockDepartamentos);
  const registrar = useRegistrarAuditoria();

  function addDepartamento(input: {
    tenantId: string;
    nombre: string;
    tipo: TipoProceso;
    descripcion?: string;
    responsableId?: string | null;
  }) {
    const id = `depto-${Date.now()}`;
    setDepartamentos((prev) => [
      ...prev,
      {
        id,
        tenantId: input.tenantId,
        nombre: input.nombre,
        tipo: input.tipo,
        descripcion: input.descripcion,
        responsableId: input.responsableId ?? null,
        entradas: [],
        salidas: [],
      },
    ]);

    registrar({
      entidadTipo: 'departamento',
      entidadId: id,
      entidadLabel: input.nombre,
      tenantId: input.tenantId,
      accion: 'creado',
      resumen: `Creó el proceso ${input.nombre}`,
      cambios: [{ campo: 'Tipo de proceso', antes: null, despues: nombreTipoProceso(input.tipo) }],
    });
  }

  function updateTipo(departamentoId: string, tipo: TipoProceso) {
    const anterior = departamentos.find((d) => d.id === departamentoId);
    if (!anterior || anterior.tipo === tipo) return;

    setDepartamentos((prev) => prev.map((d) => (d.id === departamentoId ? { ...d, tipo } : d)));

    registrar({
      entidadTipo: 'departamento',
      entidadId: departamentoId,
      entidadLabel: anterior.nombre,
      tenantId: anterior.tenantId,
      accion: 'actualizado',
      // Reclasificar un proceso cambia el mapa que se presenta en auditoría,
      // así que no es un ajuste cosmético.
      resumen: 'Reclasificó el proceso en el mapa',
      cambios: [
        { campo: 'Tipo de proceso', antes: nombreTipoProceso(anterior.tipo), despues: nombreTipoProceso(tipo) },
      ],
    });
  }

  return (
    <DepartamentosContext.Provider value={{ departamentos, addDepartamento, updateTipo }}>
      {children}
    </DepartamentosContext.Provider>
  );
}

export function useDepartamentos() {
  const ctx = useContext(DepartamentosContext);
  if (!ctx) throw new Error('useDepartamentos debe usarse dentro de <DepartamentosProvider>');
  return ctx;
}
