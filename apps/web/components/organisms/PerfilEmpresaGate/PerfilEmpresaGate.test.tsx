import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { PerfilEmpresaGate } from './PerfilEmpresaGate';

/**
 * **Este archivo no existía, y por eso el gate estuvo muerto sin que nadie lo
 * notara.**
 *
 * `PerfilEmpresaGate` leía `tenant.perfilEmpresaCompleto`, que el navegador
 * derivaba de `business_activity && rut_tax_id`. Como el RUT es `NOT NULL` en
 * la base, la condición colapsaba a «tiene giro» — y las dos empresas del seed
 * lo tienen. El gate evaluaba `false` para todo el mundo.
 *
 * El propio análisis lo confiesa: decía que el bloqueo «se verifica en vivo
 * alternando ese flag vía la consola del navegador». Nunca se comprobó contra
 * datos.
 *
 * Las pruebas de abajo cubren las cuatro decisiones del gate, incluidas las dos
 * que evitan que se vuelva un estorbo: no redirigir mientras carga, y no
 * bloquear si la API no responde.
 */

const replace = vi.fn();
let ruta = '/dashboard';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace, push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => ruta,
}));

let sesion: { tenantId: string; role: string } | null = {
  tenantId: 'a0000000-0000-0000-0000-000000000001',
  role: 'admin_empresa',
};

vi.mock('@/lib/session', () => ({
  useSession: () => ({ user: sesion, cargando: false }),
}));

const get = vi.fn();

vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return { ...real, api: { get: (...a: unknown[]) => get(...a), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } };
});

function Contenido() {
  return <p>contenido protegido</p>;
}

function montar(children: ReactNode = <Contenido />) {
  return render(<PerfilEmpresaGate>{children}</PerfilEmpresaGate>);
}

function respuesta(completo: boolean) {
  return {
    perfil_empresa: {
      completo,
      faltantes: completo ? [] : ['Declara el sector economico (CIIU) de la empresa.'],
      tiene_giro: true,
      tiene_instalaciones: true,
      tiene_departamentos: true,
      tiene_sector: completo,
    },
  };
}

beforeEach(() => {
  replace.mockReset();
  get.mockReset();
  ruta = '/dashboard';
  sesion = { tenantId: 'a0000000-0000-0000-0000-000000000001', role: 'admin_empresa' };
});

describe('cuando el perfil está incompleto', () => {
  it('bloquea y manda al wizard', async () => {
    get.mockResolvedValue(respuesta(false));

    montar();

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/perfil-empresa'));
    expect(screen.queryByText('contenido protegido')).toBeNull();
  });

  it('no se redirige a sí mismo', async () => {
    // Sin esto el wizard entra en un bucle de redirección contra su propia ruta.
    ruta = '/perfil-empresa';
    get.mockResolvedValue(respuesta(false));

    montar();

    await waitFor(() => expect(get).toHaveBeenCalled());
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByText('contenido protegido')).toBeTruthy();
  });
});

describe('cuando NO debe bloquear', () => {
  it('deja pasar con el perfil completo', async () => {
    get.mockResolvedValue(respuesta(true));

    montar();

    await waitFor(() => expect(screen.getByText('contenido protegido')).toBeTruthy());
    expect(replace).not.toHaveBeenCalled();
  });

  it('no bloquea a quien no es Admin Empresa', async () => {
    /**
     * Es el texto literal de RF-10. Bloquear a un Encargado sería castigarlo por
     * algo que **no puede arreglar**: completar el perfil no está entre sus
     * atribuciones.
     */
    sesion = { tenantId: 'a0000000-0000-0000-0000-000000000001', role: 'encargado' };
    get.mockResolvedValue(respuesta(false));

    montar();

    await waitFor(() => expect(screen.getByText('contenido protegido')).toBeTruthy());
    expect(replace).not.toHaveBeenCalled();
  });

  it('no bloquea si la API no responde', async () => {
    /**
     * **Una caída no puede convertirse en un bloqueo total.** Sin respuesta el
     * gate no sabe si el perfil está completo, y tratar «no sé» como
     * «incompleto» dejaría a toda la empresa encerrada en el wizard.
     *
     * El servidor sigue rechazando las escrituras con 409, así que no bloquear
     * acá no abre nada.
     */
    get.mockRejectedValue(new Error('sin red'));

    montar();

    await waitFor(() => expect(screen.getByText('contenido protegido')).toBeTruthy());
    expect(replace).not.toHaveBeenCalled();
  });
});
