import { forwardRef, type TextareaHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

/**
 * Mismo tratamiento visual y de estados que `Input`. Existe como átomo propio
 * porque los campos largos del sistema (forma de cumplimiento RF-29, hallazgo
 * de una no conformidad RF-46, los 5 ¿Por qué? RF-47) se venían escribiendo
 * con `<textarea>` sueltos y estilos copiados en cada organismo.
 */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, invalid, rows = 3, ...props }, ref) => (
    <textarea
      ref={ref}
      rows={rows}
      aria-invalid={invalid}
      className={cn(
        'w-full resize-y rounded-lg border px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400',
        'border-slate-300 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20',
        invalid && 'border-red-500 focus:border-red-500 focus:ring-red-500/20',
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = 'Textarea';
