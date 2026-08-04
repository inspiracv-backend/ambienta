'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Articulo, LegalNorm, TipoDocumento } from '@ambienta/shared';
import { mockLegalNorms } from '@/mocks/catalog';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { useSession } from '@/lib/session';
import { api } from '@/lib/api-client';

interface LegalMatrixContextValue {
  norms: LegalNorm[];
  loading: boolean;
  updateArticulo: (normId: string, articuloId: string, updates: Partial<Articulo>) => void;
  setIncluidoEnCalculo: (normId: string, articuloId: string, incluido: boolean) => void;
  addNorm: (input: { nombre: string; tipoDocumento: TipoDocumento; fuente: 'RCA' | 'ISO'; tenantId: string; plantIds: string[] }) => void;
  setNormPlants: (normId: string, plantIds: string[]) => void;
}

const LegalMatrixContext = createContext<LegalMatrixContextValue | null>(null);

const RESPUESTA_LABEL: Record<NonNullable<Articulo['respuesta']>, string> = {
  SI: 'Cumple',
  NO: 'No cumple',
  NA: 'No aplica',
  N_E: 'Sin evaluar',
};

export function LegalMatrixProvider({ children }: { children: ReactNode }) {
  const [norms, setNorms] = useState<LegalNorm[]>(mockLegalNorms);
  const [loading, setLoading] = useState(true);
  const registrar = useRegistrarAuditoria();
  const { user } = useSession();

  useEffect(() => {
    if (!user?.tenantId) { setLoading(false); return; }
    let cancelled = false;
    api
      .get<Record<string, unknown>[]>('/catalog/norms')
      .then((data) => {
        if (cancelled) return;
        const mapped: LegalNorm[] = data.map((raw) => ({
          id: String(raw.id),
          tenantId: user.tenantId!,
          plantIds: [],
          tipoDocumento: 'ley' as TipoDocumento,
          nombre: String(raw.title ?? raw.norm_number ?? ''),
          fuente: 'RCA' as const,
          articulos: [],
        }));
        if (mapped.length > 0) setNorms(mapped);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [user?.tenantId]);

  function updateArticulo(normId: string, articuloId: string, updates: Partial<Articulo>) {
    const norm = norms.find((n) => n.id === normId);
    const anterior = norm?.articulos.find((a) => a.id === articuloId);

    setNorms((prev) =>
      prev.map((n) =>
        n.id !== normId
          ? n
          : { ...n, articulos: n.articulos.map((a) => (a.id === articuloId ? { ...a, ...updates } : a)) },
      ),
    );

    if (!norm || !anterior) return;

    const cambios = [];
    if (updates.respuesta !== undefined && updates.respuesta !== anterior.respuesta) {
      cambios.push({
        campo: 'Evaluación',
        antes: RESPUESTA_LABEL[anterior.respuesta],
        despues: RESPUESTA_LABEL[updates.respuesta],
      });
    }
    if (updates.formaCumplimiento !== undefined && updates.formaCumplimiento !== anterior.formaCumplimiento) {
      cambios.push({
        campo: 'Forma de cumplimiento',
        antes: anterior.formaCumplimiento || null,
        despues: updates.formaCumplimiento || null,
      });
    }
    if (updates.responsableId !== undefined && updates.responsableId !== anterior.responsableId) {
      cambios.push({ campo: 'Responsable', antes: anterior.responsableId ?? null, despues: updates.responsableId ?? null });
    }
    if (updates.evidenciaUrl !== undefined && updates.evidenciaUrl !== anterior.evidenciaUrl) {
      cambios.push({ campo: 'Evidencia', antes: anterior.evidenciaUrl ?? null, despues: updates.evidenciaUrl ?? null });
    }
    if (updates.incluidoEnCalculo !== undefined && updates.incluidoEnCalculo !== anterior.incluidoEnCalculo) {
      cambios.push({
        campo: 'Entra en el % de cumplimiento',
        antes: anterior.incluidoEnCalculo ? 'Sí' : 'No',
        despues: updates.incluidoEnCalculo ? 'Sí' : 'No',
      });
    }

    if (cambios.length === 0) return;

    const evaluado = updates.respuesta !== undefined && updates.respuesta !== anterior.respuesta;

    registrar({
      entidadTipo: 'articulo',
      entidadId: articuloId,
      entidadLabel: `${anterior.numero} — ${norm.nombre}`,
      tenantId: norm.tenantId,
      accion: evaluado ? 'evaluado' : 'actualizado',
      resumen: evaluado
        ? `Evaluó el artículo como ${RESPUESTA_LABEL[updates.respuesta!].toLowerCase()}`
        : 'Actualizó la evaluación del artículo',
      cambios,
      ...(updates.formaCumplimiento ? { motivo: updates.formaCumplimiento } : {}),
    });
  }

  function setIncluidoEnCalculo(normId: string, articuloId: string, incluido: boolean) {
    updateArticulo(normId, articuloId, { incluidoEnCalculo: incluido });
  }

  function addNorm(input: { nombre: string; tipoDocumento: TipoDocumento; fuente: 'RCA' | 'ISO'; tenantId: string; plantIds: string[] }) {
    const newNorm: LegalNorm = {
      id: `norm-${Date.now()}`,
      tenantId: input.tenantId,
      plantIds: input.plantIds,
      tipoDocumento: input.tipoDocumento,
      nombre: input.nombre,
      fuente: input.fuente,
      articulos: [],
    };
    setNorms((prev) => [...prev, newNorm]);

    registrar({
      entidadTipo: 'norma',
      entidadId: newNorm.id,
      entidadLabel: newNorm.nombre,
      tenantId: input.tenantId,
      accion: 'creado',
      resumen: `Agregó la norma al catálogo (${input.fuente})`,
      cambios: [
        { campo: 'Fuente', antes: null, despues: input.fuente },
        { campo: 'Plantas asignadas', antes: null, despues: String(input.plantIds.length) },
      ],
    });
  }

  function setNormPlants(normId: string, plantIds: string[]) {
    const anterior = norms.find((n) => n.id === normId);
    if (!anterior || JSON.stringify(anterior.plantIds) === JSON.stringify(plantIds)) return;

    setNorms((prev) => prev.map((n) => (n.id === normId ? { ...n, plantIds } : n)));

    registrar({
      entidadTipo: 'norma',
      entidadId: normId,
      entidadLabel: anterior.nombre,
      tenantId: anterior.tenantId,
      accion: 'asignado',
      resumen: 'Cambió las plantas donde aplica la norma',
      cambios: [
        {
          campo: 'Plantas asignadas',
          antes: String(anterior.plantIds.length),
          despues: String(plantIds.length),
        },
      ],
    });
  }

  return (
    <LegalMatrixContext.Provider value={{ norms, loading, updateArticulo, setIncluidoEnCalculo, addNorm, setNormPlants }}>
      {children}
    </LegalMatrixContext.Provider>
  );
}

export function useLegalMatrix() {
  const ctx = useContext(LegalMatrixContext);
  if (!ctx) throw new Error('useLegalMatrix debe usarse dentro de <LegalMatrixProvider>');
  return ctx;
}
