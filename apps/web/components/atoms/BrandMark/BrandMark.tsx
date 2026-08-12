import { cn } from '@/lib/utils';

interface BrandMarkProps {
  className?: string;
  /** Cuando el nombre "Ambienta" ya aparece como texto al lado, el logo es decorativo. */
  decorativo?: boolean;
}

/**
 * Isotipo de Ambienta: una hoja inscrita en un escudo.
 *
 * Los dos elementos son el producto: la hoja es lo ambiental, el escudo es el
 * cumplimiento (protección frente a multas de la SMA). Va en SVG inline y no
 * como archivo porque hereda `currentColor` y escala sin pedir un asset
 * distinto por tamaño ni una petición extra.
 */
export function BrandMark({ className, decorativo = true }: BrandMarkProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      className={cn('h-8 w-8', className)}
      role={decorativo ? 'presentation' : 'img'}
      aria-hidden={decorativo || undefined}
      aria-label={decorativo ? undefined : 'Ambienta'}
    >
      <path
        d="M16 2.5 4.5 6.8v9.4c0 6.6 4.7 12.1 11.5 13.8 6.8-1.7 11.5-7.2 11.5-13.8V6.8L16 2.5Z"
        className="fill-brand-600"
      />
      <path
        d="M16 22.5c-.5 0-.8-.4-.8-.8v-4.4c-2.9-.3-5.1-2.7-5.1-5.6 0-.4.3-.8.8-.8 3.1 0 5.6 2.4 5.9 5.4.3-3 2.8-5.4 5.9-5.4.4 0 .8.3.8.8 0 2.9-2.2 5.3-5.1 5.6v4.4c0 .5-.4.8-.8.8h-1.6Z"
        className="fill-brand-100"
      />
    </svg>
  );
}
