'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Articulo, LegalNorm, TipoDocumento } from '@ambienta/shared';
import { mockLegalNorms } from '@/mocks/catalog';

interface LegalMatrixContextValue {
  norms: LegalNorm[];
  updateArticulo: (normId: string, articuloId: string, updates: Partial<Articulo>) => void;
  setIncluidoEnCalculo: (normId: string, articuloId: string, incluido: boolean) => void;
  addNorm: (input: { nombre: string; tipoDocumento: TipoDocumento; fuente: 'RCA' | 'ISO'; tenantId: string; plantIds: string[] }) => void;
}

const LegalMatrixContext = createContext<LegalMatrixContextValue | null>(null);

/**
 * Estado en memoria para esta iteración (equivalente al `useState` de
 * SessionProvider) — simula persistencia de las evaluaciones de artículo
 * dentro de la sesión del navegador. Integración real: mutations vía
 * apps/api cuando exista spec aprobada para Matriz Legal (RF-08 a RF-13).
 */
export function LegalMatrixProvider({ children }: { children: ReactNode }) {
  const [norms, setNorms] = useState<LegalNorm[]>(mockLegalNorms);

  function updateArticulo(normId: string, articuloId: string, updates: Partial<Articulo>) {
    setNorms((prev) =>
      prev.map((norm) =>
        norm.id !== normId
          ? norm
          : { ...norm, articulos: norm.articulos.map((a) => (a.id === articuloId ? { ...a, ...updates } : a)) },
      ),
    );
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
  }

  return (
    <LegalMatrixContext.Provider value={{ norms, updateArticulo, setIncluidoEnCalculo, addNorm }}>
      {children}
    </LegalMatrixContext.Provider>
  );
}

export function useLegalMatrix() {
  const ctx = useContext(LegalMatrixContext);
  if (!ctx) throw new Error('useLegalMatrix debe usarse dentro de <LegalMatrixProvider>');
  return ctx;
}
