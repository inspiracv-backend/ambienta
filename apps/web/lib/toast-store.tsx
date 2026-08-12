'use client';

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';

/**
 * Feedback de acciones (H1: visibilidad del estado del sistema).
 *
 * Hasta ahora las acciones ocurrían en silencio: al invitar un usuario,
 * cerrar una no conformidad o suspender un tenant, la lista cambiaba sin
 * confirmar que la acción fue exitosa. En pantallas largas el cambio ocurre
 * fuera del viewport y el usuario no tiene forma de saber si funcionó.
 *
 * Las acciones destructivas o difíciles de rehacer pueden pasar `onUndo`
 * (H3: control y libertad del usuario).
 */

export type ToastTipo = 'exito' | 'error' | 'info';

export interface Toast {
  id: string;
  tipo: ToastTipo;
  mensaje: string;
  descripcion?: string;
  onUndo?: () => void;
}

interface ToastContextValue {
  toasts: Toast[];
  mostrarToast: (toast: Omit<Toast, 'id'>) => string;
  cerrarToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

/** Los errores se quedan más tiempo: suelen traer información que hay que leer. */
const DURACION_MS: Record<ToastTipo, number> = {
  exito: 4000,
  info: 5000,
  error: 8000,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const temporizadores = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const cerrarToast = useCallback((id: string) => {
    const t = temporizadores.current.get(id);
    if (t) {
      clearTimeout(t);
      temporizadores.current.delete(id);
    }
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const mostrarToast = useCallback(
    (toast: Omit<Toast, 'id'>) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) => {
        // Tope de 4: más que eso tapa la pantalla y deja de ser útil.
        const siguiente = [...prev, { ...toast, id }];
        return siguiente.slice(-4);
      });

      const timeout = setTimeout(() => cerrarToast(id), DURACION_MS[toast.tipo]);
      temporizadores.current.set(id, timeout);
      return id;
    },
    [cerrarToast],
  );

  const value = useMemo(() => ({ toasts, mostrarToast, cerrarToast }), [toasts, mostrarToast, cerrarToast]);

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast debe usarse dentro de <ToastProvider>');
  return ctx;
}
