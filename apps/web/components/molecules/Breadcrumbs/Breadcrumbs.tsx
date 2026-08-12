import Link from 'next/link';
import { ChevronRight } from 'lucide-react';
import type { BreadcrumbsProps } from './Breadcrumbs.types';

/** Migas de pan en pantallas anidadas (H6) — ej. Matriz Legal > Detalle de norma. */
export function Breadcrumbs({ items }: BreadcrumbsProps) {
  return (
    <nav aria-label="Miga de pan" className="flex items-center gap-1.5 text-sm text-slate-500">
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <span key={item.label} className="flex items-center gap-1.5">
            {i > 0 && <ChevronRight className="h-3.5 w-3.5" aria-hidden />}
            {item.href && !isLast ? (
              <Link href={item.href} className="hover:text-brand-600 hover:underline">
                {item.label}
              </Link>
            ) : (
              <span aria-current={isLast ? 'page' : undefined} className={isLast ? 'font-medium text-slate-700' : undefined}>
                {item.label}
              </span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
