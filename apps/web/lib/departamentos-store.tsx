'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Departamento, TipoProceso } from '@ambienta/shared';
import { nombreTipoProceso } from '@ambienta/shared';
import { mockDepartamentos } from '@/mocks/departamentos';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { api } from '@/lib/api-client';

interface DepartamentosContextValue {
  departamentos: Departamento[];
  loading: boolean;
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

export function DepartamentosProvider({ children }: { children: ReactNode }) {
  const [departamentos, setDepartamentos] = useState<Departamento[]>(mockDepartamentos);
  const [loading, setLoading] = useState(true);
  const registrar = useRegistrarAuditoria();
  const { user } = useSession();

  useEffect(() => {
    // Departments don't have a direct endpoint yet — keep mocks as fallback
    setLoading(false);
  }, [user?.tenantId]);

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
      resumen: 'Reclasificó el proceso en el mapa',
      cambios: [
        { campo: 'Tipo de proceso', antes: nombreTipoProceso(anterior.tipo), despues: nombreTipoProceso(tipo) },
      ],
    });
  }

  return (
    <DepartamentosContext.Provider value={{ departamentos, loading, addDepartamento, updateTipo }}>
      {children}
    </DepartamentosContext.Provider>
  );
}

export function useDepartamentos() {
  const ctx = useContext(DepartamentosContext);
  if (!ctx) throw new Error('useDepartamentos debe usarse dentro de <DepartamentosProvider>');
  return ctx;
}
