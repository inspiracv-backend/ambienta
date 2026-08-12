import { cn } from '@/lib/utils';
import type { AvatarProps } from './Avatar.types';

function getInitials(nombre: string) {
  return nombre
    .split(' ')
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('');
}

export function Avatar({ nombre, avatarUrl, size = 'md' }: AvatarProps) {
  const dimension = size === 'sm' ? 'h-8 w-8 text-xs' : 'h-10 w-10 text-sm';

  if (avatarUrl) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={avatarUrl} alt={nombre} className={cn('rounded-full object-cover', dimension)} />;
  }

  return (
    <div
      className={cn(
        'flex items-center justify-center rounded-full bg-brand-100 font-semibold text-brand-700',
        dimension,
      )}
      role="img"
      aria-label={nombre}
    >
      {getInitials(nombre)}
    </div>
  );
}
