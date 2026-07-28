'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Building2, FlaskConical, Globe } from 'lucide-react';
import { Avatar, Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import { useUsers } from '@/lib/users-store';
import { ROLE_LABEL } from '@/lib/roles';
import { mockTenants } from '@/mocks/tenants';

/**
 * HERRAMIENTA DE DESARROLLO — NO ES PARTE DEL PRODUCTO.
 *
 * Permite entrar como cualquiera de los usuarios mock para revisar las vistas
 * de cada rol. Existe porque `LoginCard` (S-01) siempre inicia sesión como
 * Admin Empresa y `GuestAccessCard` (S-02) siempre como Cliente Invitado, así
 * que sin esto los otros 4 usuarios solo eran alcanzables escribiendo en
 * `localStorage` a mano desde la consola del navegador.
 *
 * Se elimina del bundle de producción: `process.env.NODE_ENV` lo reemplaza
 * Next.js en tiempo de build por un literal, así que en un build de producción
 * la condición es constante y todo el componente queda como código muerto que
 * el minificador descarta. No es una comprobación en runtime que alguien pueda
 * saltarse: el código directamente no existe en el bundle.
 *
 * Cuando exista auth real (JWT + OAuth vía apps/api), este archivo se borra
 * junto con su uso en `app/(auth)/login/page.tsx`.
 */
export function DevRoleSwitcher() {
  if (process.env.NODE_ENV === 'production') return null;
  return <DevRoleSwitcherPanel />;
}

function DevRoleSwitcherPanel() {
  const router = useRouter();
  const { login } = useSession();
  const { users } = useUsers();
  const [entrandoComo, setEntrandoComo] = useState<string | null>(null);

  function handleEntrar(userId: string, esClienteInvitado: boolean) {
    setEntrandoComo(userId);
    login(userId);
    // El Cliente Invitado no puede ver contenido de negocio (RF-05): mandarlo
    // al dashboard solo provocaría que `ClienteInvitadoGate` lo rebote.
    // El resto va al dashboard y los gates deciden si corresponde redirigir.
    router.push(esClienteInvitado ? '/crear-ticket' : '/dashboard');
  }

  return (
    <section
      aria-labelledby="dev-switcher-titulo"
      className="mt-6 w-full max-w-sm rounded-card border border-dashed border-amber-400 bg-amber-50 p-5"
    >
      <div className="flex items-start gap-2">
        <FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" aria-hidden />
        <div>
          <h2 id="dev-switcher-titulo" className="text-sm font-semibold text-amber-900">
            Acceso rápido de desarrollo
          </h2>
          <p className="mt-0.5 text-xs text-amber-800">
            Solo visible en desarrollo. Entra como cualquier usuario para revisar su vista.
          </p>
        </div>
      </div>

      <ul className="mt-4 flex flex-col gap-1.5">
        {users.map((u) => {
          // Se lee el mock estático en vez de `useTenants`: TenantsProvider vive
          // en el layout de (dashboard) y esta pantalla está en (auth), fuera de
          // su alcance. Mover el provider al layout raíz por una herramienta de
          // desarrollo sería peor que leer el dato de solo lectura que necesita.
          const tenant = mockTenants.find((t) => t.id === u.tenantId);
          const esClienteInvitado = u.role === 'cliente_invitado';
          const estaEntrando = entrandoComo === u.id;

          return (
            <li key={u.id}>
              <button
                type="button"
                onClick={() => handleEntrar(u.id, esClienteInvitado)}
                disabled={entrandoComo !== null}
                className="flex w-full items-center gap-3 rounded-lg border border-amber-200 bg-white px-3 py-2 text-left transition hover:border-amber-400 hover:bg-amber-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 disabled:opacity-50"
              >
                <Avatar nombre={u.nombre} size="sm" />

                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-slate-900">{u.nombre}</span>
                  <span className="mt-0.5 flex items-center gap-1 text-xs text-slate-500">
                    {u.tenantId ? (
                      <Building2 className="h-3 w-3 shrink-0" aria-hidden />
                    ) : (
                      <Globe className="h-3 w-3 shrink-0" aria-hidden />
                    )}
                    <span className="truncate">{tenant?.nombre ?? 'Plataforma completa'}</span>
                  </span>
                </span>

                <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                  {ROLE_LABEL[u.role]}
                </span>

                {estaEntrando && <Spinner label={`Entrando como ${u.nombre}`} />}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
