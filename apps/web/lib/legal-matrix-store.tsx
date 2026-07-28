'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Articulo, LegalNorm, TipoDocumento } from '@ambienta/shared';
import { mockLegalNorms } from '@/mocks/catalog';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';

interface LegalMatrixContextValue {
  norms: LegalNorm[];
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

/**
 * Estado en memoria para esta iteración (equivalente al `useState` de
 * SessionProvider) — simula persistencia de las evaluaciones de artículo
 * dentro de la sesión del navegador. Integración real: mutations vía
 * apps/api cuando exista spec aprobada para Matriz Legal (RF-19 a RF-24).
 *
 * La evaluación de artículos es **el flujo más sensible del sistema para el
 * audit log**: RF-32 y RNF-08 nacen justamente de aquí. Declarar que un
 * artículo "cumple" es una afirmación con consecuencias legales, y ante una
 * fiscalización hay que poder demostrar quién lo declaró, cuándo y con qué
 * fundamento. Por eso cada cambio de respuesta se registra con su forma de
 * cumplimiento como motivo.
 */
export function LegalMatrixProvider({ children }: { children: ReactNode }) {
  const [norms, setNorms] = useState<LegalNorm[]>(mockLegalNorms);
  const registrar = useRegistrarAuditoria();

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
      // Se guarda norma + artículo porque un "Art. 10" suelto no identifica nada.
      entidadLabel: `${anterior.numero} — ${norm.nombre}`,
      tenantId: norm.tenantId,
      accion: evaluado ? 'evaluado' : 'actualizado',
      resumen: evaluado
        ? `Evaluó el artículo como ${RESPUESTA_LABEL[updates.respuesta!].toLowerCase()}`
        : 'Actualizó la evaluación del artículo',
      cambios,
      // RF-29: la forma de cumplimiento es el fundamento de la declaración.
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
    <LegalMatrixContext.Provider value={{ norms, updateArticulo, setIncluidoEnCalculo, addNorm, setNormPlants }}>
      {children}
    </LegalMatrixContext.Provider>
  );
}

export function useLegalMatrix() {
  const ctx = useContext(LegalMatrixContext);
  if (!ctx) throw new Error('useLegalMatrix debe usarse dentro de <LegalMatrixProvider>');
  return ctx;
}
