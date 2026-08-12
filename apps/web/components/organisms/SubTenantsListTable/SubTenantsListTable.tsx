import Link from 'next/link';
import { Inbox } from 'lucide-react';
import { StatusBadge } from '@/components/atoms';
import type { SubTenantsListTableProps } from './SubTenantsListTable.types';

/** S-27 Listado de Clientes (Sub-tenants) de un tenant Gestor. */
export function SubTenantsListTable({ subTenants }: SubTenantsListTableProps) {
  if (subTenants.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
        <Inbox className="h-6 w-6 text-slate-400" aria-hidden />
        Aún no tienes clientes registrados.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
      <table className="w-full min-w-[640px] text-sm">
        <caption className="sr-only">Clientes del gestor</caption>
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
            <th scope="col" className="px-4 py-3">Cliente</th>
            <th scope="col" className="px-4 py-3">RUT</th>
            <th scope="col" className="px-4 py-3">Contactos</th>
            <th scope="col" className="px-4 py-3">Estado</th>
          </tr>
        </thead>
        <tbody>
          {subTenants.map((s) => (
            <tr key={s.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
              <td className="px-4 py-3 font-medium text-slate-800">
                <Link href={`/gestores/${s.id}`} className="hover:underline">
                  {s.nombre}
                </Link>
              </td>
              <td className="px-4 py-3 text-slate-500">{s.rut}</td>
              <td className="px-4 py-3 text-slate-500">{s.contactos.length}</td>
              <td className="px-4 py-3">
                <StatusBadge status={s.estado === 'activo' ? 'cumple' : 'no_cumple'} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
