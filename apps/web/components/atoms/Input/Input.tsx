import { forwardRef } from 'react';
import { cn } from '@/lib/utils';
import type { InputProps } from './Input.types';

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid, ...props }, ref) => (
    <input
      ref={ref}
      aria-invalid={invalid}
      className={cn(
        'h-11 w-full rounded-lg border px-3 text-sm text-slate-900 placeholder:text-slate-400',
        // Anillo de foco explícito: el borde de color solo no da contraste
        // suficiente para navegación por teclado (WCAG 2.4.7).
        'border-slate-300 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20',
        'disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500',
        invalid && 'border-red-500 focus:border-red-500 focus:ring-red-500/20',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';
