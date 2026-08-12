'use client';

import { AlertCircle, CheckCircle2, Info, Undo2, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useToast, type ToastTipo } from '@/lib/toast-store';

const ESTILO: Record<ToastTipo, { icono: typeof CheckCircle2; clase: string; iconoClase: string }> = {
  exito: { icono: CheckCircle2, clase: 'border-semaforo-cumple/30 bg-semaforo-cumple-bg', iconoClase: 'text-semaforo-cumple' },
  error: { icono: AlertCircle, clase: 'border-semaforo-no-cumple/30 bg-semaforo-no-cumple-bg', iconoClase: 'text-semaforo-no-cumple' },
  info: { icono: Info, clase: 'border-slate-200 bg-white', iconoClase: 'text-brand-600' },
};

/**
 * Zona donde aparecen los avisos de acción. Vive una sola vez, en el layout
 * raíz.
 *
 * Accesibilidad: la región es `aria-live="polite"` para que un lector de
 * pantalla anuncie el resultado de la acción sin interrumpir lo que el
 * usuario esté haciendo. Los errores usan `role="alert"`, que sí interrumpe,
 * porque implican que algo no ocurrió.
 */
export function ToastViewport() {
  const { toasts, cerrarToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      aria-label="Notificaciones de acciones"
      className="pointer-events-none fixed inset-x-4 bottom-4 z-[60] flex flex-col items-center gap-2 sm:inset-x-auto sm:right-6 sm:items-end"
    >
      {toasts.map((toast) => {
        const { icono: Icono, clase, iconoClase } = ESTILO[toast.tipo];
        return (
          <div
            key={toast.id}
            role={toast.tipo === 'error' ? 'alert' : 'status'}
            className={cn(
              'pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-card border p-3 shadow-lg',
              clase,
            )}
          >
            <Icono className={cn('mt-0.5 h-5 w-5 shrink-0', iconoClase)} aria-hidden />

            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-900">{toast.mensaje}</p>
              {toast.descripcion && <p className="mt-0.5 text-xs text-slate-600">{toast.descripcion}</p>}

              {toast.onUndo && (
                <button
                  type="button"
                  onClick={() => {
                    toast.onUndo?.();
                    cerrarToast(toast.id);
                  }}
                  className="mt-2 inline-flex items-center gap-1.5 rounded-md text-xs font-semibold text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                >
                  <Undo2 className="h-3.5 w-3.5" aria-hidden />
                  Deshacer
                </button>
              )}
            </div>

            <button
              type="button"
              onClick={() => cerrarToast(toast.id)}
              aria-label="Cerrar aviso"
              className="shrink-0 rounded text-slate-400 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
        );
      })}
    </div>
  );
}
