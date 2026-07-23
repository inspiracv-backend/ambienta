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
        'border-slate-300 focus:border-brand-500',
        invalid && 'border-red-500 focus:border-red-500',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';
