'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { FlaskConical, X } from 'lucide-react';
import type { User } from '@ambienta/shared';
import { useSession } from '@/lib/session';
import { useUsers } from '@/lib/users-store';
import { ROLE_LABEL } from '@/lib/roles';
import { rutaInicialParaRol } from '@/lib/navigation';
import { CLERK_HABILITADO } from '@/lib/clerk-config';

/**
 * HERRAMIENTA DE DESARROLLO — NO ES PARTE DEL PRODUCTO.
 *
 * Cambia de rol **sin cerrar sesión**. `DevRoleSwitcher` ya permitía entrar
 * como cualquier usuario, pero vive en la pantalla de ingreso: para probar una
 * función con otro rol había que salir y volver a entrar, y eso convierte
 * "revisar cómo se ve esto para un Encargado" en cuatro pasos.
 *
 * ## Por qué no se muestra con Clerk configurado
 *
 * No es prudencia de más: **con Clerk activo esto no funcionaría**. La API
 * valida la firma del JWT, así que una sesión fabricada en el navegador entra a
 * la interfaz y después cobra 401 en cada llamada. La pantalla se vería bien y
 * no habría datos, que es la peor combinación para depurar.
 *
 * El acceso rápido y el modo sin proveedor son la misma cosa: el frontend
 * simula la sesión y la API acepta el header `X-Tenant-Id`. Uno sin el otro no
 * sirve.
 *
 * ## Por qué no puede filtrarse a producción
 *
 * `process.env.NODE_ENV` lo reemplaza Next.js en tiempo de build por un
 * literal, así que en un build de producción la condición es constante y el
 * componente entero queda como código muerto que el minificador descarta. **No
 * es una comprobación en runtime que alguien pueda saltarse**: el código
 * directamente no existe en el bundle.
 */
export function DevCambioDeRol() {
  if (process.env.NODE_ENV === 'production' || CLERK_HABILITADO) return null;
  return <Panel />;
}

function Panel() {
  const router = useRouter();
  const { user, login } = useSession();
  const { users } = useUsers();
  const [abierto, setAbierto] = useState(false);

  if (!user) return null;

  function cambiarA(destino: User) {
    login(destino.id);
    setAbierto(false);
    // Cada rol aterriza donde le corresponde: un Cliente Invitado en sus
    // tickets, no en un tablero de empresa que para él saldría vacío.
    router.push(rutaInicialParaRol(destino.role));
  }

  return (
    <div className="fixed bottom-4 left-4 z-50 print:hidden">
      {abierto ? (
        <div className="w-64 rounded-card border border-dashed border-amber-400 bg-amber-50 p-3 shadow-lg">
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-amber-900">
              <FlaskConical className="h-3.5 w-3.5" aria-hidden />
              Cambiar de rol
            </span>
            <button
              type="button"
              onClick={() => setAbierto(false)}
              aria-label="Cerrar el selector de rol"
              className="rounded p-0.5 text-amber-800 hover:bg-amber-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>

          <ul className="mt-2 flex flex-col gap-1">
            {users.map((u) => {
              const esActual = u.id === user!.id;
              return (
                <li key={u.id}>
                  <button
                    type="button"
                    onClick={() => cambiarA(u)}
                    disabled={esActual}
                    aria-current={esActual ? 'true' : undefined}
                    className="flex w-full items-center justify-between gap-2 rounded-lg border border-amber-200 bg-white px-2 py-1.5 text-left text-xs transition hover:border-amber-400 hover:bg-amber-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 disabled:cursor-default disabled:opacity-60"
                  >
                    <span className="min-w-0 truncate font-medium text-slate-900">{u.nombre}</span>
                    <span className="shrink-0 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                      {ROLE_LABEL[u.role]}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setAbierto(true)}
          className="flex items-center gap-1.5 rounded-full border border-dashed border-amber-400 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-900 shadow-md transition hover:bg-amber-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
        >
          <FlaskConical className="h-3.5 w-3.5" aria-hidden />
          {ROLE_LABEL[user.role]}
        </button>
      )}
    </div>
  );
}
