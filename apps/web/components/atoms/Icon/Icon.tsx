import type { IconProps } from './Icon.types';

/** Envuelve lucide-react para forzar accesibilidad: ícono decorativo por defecto, o con label (H10). */
export function Icon({ icon: LucideIconComponent, className, size = 18, label }: IconProps) {
  return (
    <LucideIconComponent
      className={className}
      size={size}
      aria-hidden={label ? undefined : true}
      role={label ? 'img' : undefined}
      aria-label={label}
    />
  );
}
