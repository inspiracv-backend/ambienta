'use client';

import { useEffect, type ReactNode } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import { usePerfilEmpresa } from '@/lib/perfil-empresa';

const RUTA_PERFIL_EMPRESA = '/perfil-empresa';

/**
 * RF-10 (v1.7): fuerza el flujo de Perfil Empresa como primer paso del Admin
 * Empresa antes de operar el resto de la plataforma (Matriz Legal,
 * Obligaciones, etc.). Vive como organismo aparte (no dentro de
 * `DashboardLayout`, que se documenta explícitamente sin lógica de negocio)
 * para mantener esa separación.
 *
 * ## Qué cambió el 25-ago-2026, y por qué importa
 *
 * Antes leía `tenant.perfilEmpresaCompleto`, que el navegador derivaba de
 * `business_activity && rut_tax_id`. Como el RUT es `NOT NULL` en la base, eso
 * colapsaba a «tiene giro» — y las dos empresas del seed lo tienen. **Este gate
 * nunca bloqueó a nadie**, y el propio análisis lo confiesa: decía que el
 * bloqueo se verificaba alternando el valor por la consola del navegador.
 *
 * Ahora el criterio lo decide el servidor (`GET /me`) y este componente solo
 * obedece. Y **no es la única barrera**: la API rechaza con 409 las escrituras
 * de Matriz Legal y Obligaciones con el perfil incompleto, así que saltarse
 * esta pantalla ya no sirve de nada.
 *
 * ## Mientras no se sabe, no se redirige
 *
 * Tratar «todavía no cargó» como «incompleto» mandaría a todo el mundo al
 * wizard en cada carga de página. Y si la API no responde tampoco se bloquea:
 * una caída no puede convertirse en un bloqueo total.
 */
export function PerfilEmpresaGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user } = useSession();
  const { perfil, cargando } = usePerfilEmpresa(user?.tenantId);

  const debeCompletarPerfil =
    user?.role === 'admin_empresa' && !cargando && perfil !== null && !perfil.completo;
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
