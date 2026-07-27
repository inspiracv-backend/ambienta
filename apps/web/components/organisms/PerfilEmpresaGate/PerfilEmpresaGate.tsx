'use client';

import { useEffect, type ReactNode } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import { useTenants } from '@/lib/tenants-store';

const RUTA_PERFIL_EMPRESA = '/perfil-empresa';

/**
 * RF-10 (v1.7): fuerza el flujo de Perfil Empresa como primer paso del Admin
 * Empresa antes de operar el resto de la plataforma (Matriz Legal,
 * Obligaciones, etc.). Vive como organismo aparte (no dentro de
 * `DashboardLayout`, que se documenta explícitamente sin lógica de negocio)
 * para mantener esa separación.
 */
export function PerfilEmpresaGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user } = useSession();
  const { tenants } = useTenants();

  const tenant = tenants.find((t) => t.id === user?.tenantId);
  const debeCompletarPerfil = user?.role === 'admin_empresa' && tenant && !tenant.perfilEmpresaCompleto;
  const bloqueado = debeCompletarPerfil && pathname !== RUTA_PERFIL_EMPRESA;

  useEffect(() => {
    if (bloqueado) router.replace(RUTA_PERFIL_EMPRESA);
  }, [bloqueado, router]);

  if (bloqueado) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner label="Redirigiendo a Perfil Empresa" />
      </div>
    );
  }

  return <>{children}</>;
}
