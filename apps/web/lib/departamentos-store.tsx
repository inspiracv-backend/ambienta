'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Departamento, TipoProceso } from '@ambienta/shared';
import { nombreTipoProceso } from '@ambienta/shared';
import { mockDepartamentos } from '@/mocks/departamentos';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { useToast } from '@/lib/toast-store';
import { api, mensajeDeError } from '@/lib/api-client';

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

const PROCESS_TYPE_POR_TIPO: Record<TipoProceso, string> = {
  estrategico: 'strategic',
  operativo: 'operational',
  apoyo: 'support',
};

/**
 * `processes.code` es obligatorio y la pantalla no lo pide.
 *
 * Se deriva del nombre siguiendo la forma del catálogo existente
 * (`PROC-CHANC` para "Chancado y Molienda"). No se le agrega nada aleatorio a
 * propósito: es un identificador que la gente lee y escribe, y un sufijo de
 * timestamp lo volvería ilegible. Si dos procesos derivan el mismo código, la
 * base rechaza el segundo con 409 y eso se muestra en pantalla — que es más
 * honesto que inventar `PROC-CHANC-1731...` a espaldas de quien lo creó.
 */
function codigoDesdeNombre(nombre: string): string {
  const limpio = nombre
    .normalize('NFD')
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '');
  return `PROC-${limpio.slice(0, 10) || 'NUEVO'}`;
}

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
  const { mostrarToast } = useToast();

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
    // Id provisional: la fila aparece de inmediato y se reemplaza por la que
    // devuelve la API. Sin ese reemplazo la fila queda con un id inventado y
    // **cualquier edición posterior sobre ella apunta a algo que no existe**.
    const idProvisional = `depto-${Date.now()}`;

    setDepartamentos((prev) => [
      ...prev,
      {
        id: idProvisional,
        tenantId: input.tenantId,
        nombre: input.nombre,
        tipo: input.tipo,
        descripcion: input.descripcion,
        responsableId: input.responsableId ?? null,
        entradas: [],
        salidas: [],
      },
    ]);

    function registrarAlta(id: string) {
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

    // Sin empresa en la sesión no hay a dónde escribir: es el modo sin backend,
    // donde la pantalla trabaja sobre los datos de ejemplo.
    if (!user?.tenantId) {
      registrarAlta(idProvisional);
      return;
    }

    api
      .post<Record<string, unknown>>(
        '/processes/',
        {
          code: codigoDesdeNombre(input.nombre),
          name: input.nombre,
          process_type: PROCESS_TYPE_POR_TIPO[input.tipo],
          description: input.descripcion ?? null,
          responsible_user_id: input.responsableId ?? null,
        },
        { tenantId: user.tenantId },
      )
      .then((creado) => {
        const persistido = mapApiProceso(creado);
        setDepartamentos((prev) =>
          prev.map((d) => (d.id === idProvisional ? (persistido ?? { ...d, id: String(creado.id) }) : d)),
        );
        registrarAlta(persistido?.id ?? String(creado.id));
      })
      .catch((error) => {
        // Se retira la fila. Dejarla puesta es peor que no haberla mostrado:
        // la pantalla afirmaría que el proceso existe y desaparecería al
        // recargar, sin que nadie sepa por qué.
        setDepartamentos((prev) => prev.filter((d) => d.id !== idProvisional));
        mostrarToast({
          tipo: 'error',
          mensaje: 'No se pudo crear el proceso',
          descripcion: mensajeDeError(error),
        });
      });
  }

  /**
   * **Esto no llega a la base, y no es un olvido.**
   *
   * `ProcessUpdate` no expone `process_type` (`apps/api/app/schemas/organization.py`),
   * así que la API no acepta reclasificar un proceso — justo la operación que
   * hace esta pantalla. La columna existe y es `NOT NULL` sin marca de
   * inmutabilidad, así que parece un descuido del esquema, no una decisión.
   *
   * Reclasificar sigue funcionando en pantalla y se pierde al recargar. Se deja
   * así en vez de mandar un `PATCH` que la API ignoraría en silencio: un 200
   * que no guarda nada es peor que no llamar.
   */
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
