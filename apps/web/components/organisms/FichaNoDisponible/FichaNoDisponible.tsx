'use client';

import Link from 'next/link';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';

export interface FichaNoDisponibleProps {
  /** Si el store que trae la entidad todavia esta cargando. */
  cargando: boolean;
  /** Lo que se buscaba, con su articulo: "esta auditoría". */
  que: string;
  volverA?: string;
  volverEtiqueta?: string;
}

/**
 * Lo que muestra una ficha cuando todavia no tiene su entidad.
 *
 * **Reemplaza a `notFound()`, que dejaba toda ficha inalcanzable por enlace.**
 * Los stores arrancan vacios y, sin sesion, bajan `loading` de inmediato: la
 * ficha decidia "no existe" antes de preguntar, y `notFound()` desmonta la
 * pagina, asi que cuando los datos llegaban ya no habia nada que mostrarlos.
 * Recargar la ficha de una auditoria, una no conformidad o una obligacion daba
 * 404; solo se llegaba navegando desde la lista. Aca no se lanza nada: si la
 * entidad aparece despues, la ficha se dibuja sola.
 */
export function FichaNoDisponible({ cargando, que, volverA, volverEtiqueta }: FichaNoDisponibleProps) {
  const { cargando: cargandoSesion, user } = useSession();

  if (cargando || cargandoSesion || !user) {
    return (
      <div className="flex h-full items-center justify-center py-16">
        <Spinner label={`Cargando ${que}`} />
      </div>
    );
  }

  return (
    <div role="status" className="mx-auto mt-16 max-w-md rounded-card border border-slate-200 bg-white p-6 text-center">
      <p className="text-base font-semibold text-slate-800">No encontramos {que}</p>
      <p className="mt-1 text-sm text-slate-500">Puede que se haya eliminado o que no sea de tu empresa.</p>
      {volverA && (
        <Link href={volverA} className="mt-4 inline-block text-sm text-brand-600 hover:underline">
          {volverEtiqueta ?? 'Volver'}
        </Link>
      )}
    </div>
  );
}
