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

/**
 * El "departamento" de esta pantalla es el **proceso** de la API, no la tabla
 * `departments`.
 *
 * Los nombres divergieron, pero los datos no dejan lugar a dudas: el tipo
 * `Departamento` tiene `tipo`, `entradas`, `salidas` y `responsableId`, y esas
 * cuatro columnas viven en `processes` — `DepartmentRead` solo trae código,
 * nombre y planta. El propio esquema compartido lo dice: "se modela como
 * proceso, y no solo como unidad organizativa, porque es lo que ISO 9001 §4.4
 * pide identificar".
 *
 * `departments` existe igual en la API y sirve para el organigrama; es otra
 * cosa y tiene su propia pantalla pendiente.
 */
const TIPO_POR_PROCESS_TYPE: Record<string, TipoProceso> = {
  strategic: 'estrategico',
  operational: 'operativo',
  support: 'apoyo',
};

function mapApiProceso(raw: Record<string, unknown>): Departamento | null {
  try {
    return {
      id: String(raw.id),
      tenantId: String(raw.tenant_id ?? ''),
      nombre: String(raw.name ?? raw.code ?? ''),
      tipo: TIPO_POR_PROCESS_TYPE[String(raw.process_type ?? '')] ?? 'operativo',
      descripcion: raw.description ? String(raw.description) : undefined,
      responsableId: raw.responsible_user_id ? String(raw.responsible_user_id) : null,
      entradas: Array.isArray(raw.inputs) ? raw.inputs.map(String) : [],
      salidas: Array.isArray(raw.outputs) ? raw.outputs.map(String) : [],
    };
  } catch {
    return null;
  }
}

export function DepartamentosProvider({ children }: { children: ReactNode }) {
  const [departamentos, setDepartamentos] = useState<Departamento[]>(mockDepartamentos);
  const [loading, setLoading] = useState(true);
  const registrar = useRegistrarAuditoria();
  const { user } = useSession();

  useEffect(() => {
    if (!user?.tenantId) {
      setLoading(false);
      return;
    }
    let cancelado = false;
    api
      .get<Record<string, unknown>[]>('/processes/', { tenantId: user.tenantId })
      .then((data) => {
        if (cancelado) return;
        const mapeados = data
          .map(mapApiProceso)
          .filter((d): d is Departamento => d !== null);
        // Solo se reemplaza si la API trajo algo: una empresa sin procesos
        // cargados deja los datos de ejemplo, que es lo que permite trabajar
        // en el frontend sin backend levantado.
        if (mapeados.length > 0) setDepartamentos(mapeados);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelado) setLoading(false);
      });
    return () => {
      cancelado = true;
    };
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
