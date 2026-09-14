'use client';

import { useCallback } from 'react';
import { useUsersOpcional } from '@/lib/users-store';

/**
 * El nombre de una persona para mostrar, a partir de su id.
 *
 * ## Qué estaba mal hasta el 14-sep
 *
 * Buscaba **solo en `mockUsers`**. Con datos de la API los ids son UUID que no
 * están ahí, así que **todo responsable real se mostraba «Sin asignar»** — en
 * obligaciones, matriz legal, no conformidades, riesgos, aspectos, kanban y
 * Gantt. Doce pantallas afirmando que nadie estaba a cargo de algo que sí tenía
 * dueño, que en cumplimiento es exactamente la señal equivocada.
 *
 * ## Dos textos distintos, a propósito
 *
 * - Sin id → **«Sin asignar»**: es verdad, no hay responsable.
 * - Con un id que no está entre las personas cargadas → **«Responsable no
 *   identificado»**: hay alguien asignado y no se sabe quién (todavía cargando,
 *   o una persona que ya no está). Decir «Sin asignar» ahí es falso.
 */
export function nombreDeUsuario(personas: readonly { id: string; nombre: string }[], userId?: string | null): string {
  if (!userId) return 'Sin asignar';
  return personas.find((p) => p.id === userId)?.nombre ?? 'Responsable no identificado';
}

/**
 * Hook: devuelve la función que resuelve nombres con las personas del
 * `UsersProvider`, así la pantalla se vuelve a pintar cuando llegan.
 *
 * Fuera del provider no revienta —hay pruebas de componentes que no lo montan—:
 * resuelve contra una lista vacía.
 */
export function useNombreDeUsuario(): (userId?: string | null) => string {
  const ctx = useUsersOpcional();
  const personas = ctx?.users ?? SIN_PERSONAS;
  return useCallback((userId?: string | null) => nombreDeUsuario(personas, userId), [personas]);
}

const SIN_PERSONAS: { id: string; nombre: string }[] = [];
