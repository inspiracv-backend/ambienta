/**
 * Asignar el rol que decide qué puede hacer una persona (#140, RF-08).
 *
 * ## Lo que había antes
 *
 * Cambiar el rol mostraba un aviso diciendo que **no se guardaba** — y era
 * verdad: `user_roles` no tenía ni una ruta, así que el RBAC funcionaba y no se
 * podía administrar. La API entró en el PR #216 y nada la usaba.
 *
 * ## Lo que estas pruebas protegen
 *
 * 1. **Que lo que se guarda sea el estado final**, no una adición. Si acumulara,
 *    bajar a alguien de administradora a operadora le dejaría los permisos de
 *    administradora — lo contrario de lo que quiso quien hizo el cambio.
 * 2. **Que el 409 del servidor se muestre tal cual.** Dice qué hacer para poder
 *    seguir —asignarle antes ese permiso a alguien más— y uno genérico no.
 * 3. **Que quitarle todos los roles avise.** Sin ninguno la persona no puede
 *    hacer nada, y eso debería verse antes de guardar, no después.
 *
 * Las afirmaciones son sobre **texto visible y roles accesibles**.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { SessionProvider } from '@/lib/session';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { RolDePermisosModal } from './RolDePermisosModal';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
}));

const get = vi.fn();
const put = vi.fn();

vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      put: (...a: unknown[]) => put(...a),
      post: vi.fn(),
      patch: vi.fn(),
      delete: vi.fn(),
      getPagina: vi.fn(),
    },
  };
});

const ADMIN = { id: 'r-admin', code: 'admin_empresa', name: 'Administrador de Empresa', description: null };
const ENCARGADO = { id: 'r-enc', code: 'encargado_ambiental', name: 'Encargado Ambiental', description: 'Opera el cumplimiento' };

const PERSONA = {
  id: 'u-1',
  tenantId: 'a0000000-0000-0000-0000-000000000001',
  nombre: 'Paula Rivas',
  email: 'paula@ejemplo.cl',
  role: 'usuario_interno' as const,
  permisos: [],
  plantIds: [],
  departamentoId: null,
  estado: 'activo' as const,
  ultimaActividad: null,
};

function envoltura({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>{children}</SessionProvider>
      </UsersProvider>
    </ToastProvider>
  );
}

/** Enruta por ruta: el catálogo y los roles de la persona son consultas distintas. */
function responder(suyos: string[] = []) {
  get.mockImplementation((ruta: string) => {
    if (String(ruta).startsWith('/roles')) return Promise.resolve([ADMIN, ENCARGADO]);
    if (String(ruta).includes('/roles')) {
      return Promise.resolve({ role_ids: suyos, codigos: [] });
    }
    if (String(ruta).startsWith('/tenants')) return Promise.resolve([{ id: PERSONA.tenantId }]);
    return Promise.resolve([]);
  });
}

async function abrir(suyos: string[] = []) {
  responder(suyos);
  render(<RolDePermisosModal open onOpenChange={vi.fn()} user={PERSONA as never} />, {
    wrapper: envoltura,
  });
  await screen.findByText(/Encargado Ambiental/);
}

beforeEach(() => {
  window.localStorage.clear();
  get.mockReset();
  put.mockReset();
  iniciarSesionComo('admin_empresa');
  put.mockResolvedValue({ role_ids: [], codigos: [], efectos: [] });
});

describe('lo que muestra', () => {
  it('lista los roles de la empresa', async () => {
    await abrir();

    expect(screen.getByText('Administrador de Empresa')).toBeInTheDocument();
    expect(screen.getByText('Encargado Ambiental')).toBeInTheDocument();
  });

  it('deja marcados los que la persona ya tiene', async () => {
    await abrir([ENCARGADO.id]);

    const casillas = screen.getAllByRole('checkbox');
    expect(casillas.some((c) => (c as HTMLInputElement).checked)).toBe(true);
  });

  it('dice que es distinto del tipo de cuenta', async () => {
    // Es la confusión que cuesta cara: la columna de la tabla sale de
    // `user_type` y dice qué clase de cuenta es; esto dice qué puede hacer.
    await abrir();

    expect(screen.getByText(/distinto del tipo de cuenta/i)).toBeInTheDocument();
  });
});

describe('guardar', () => {
  it('manda el estado FINAL, no una adición', async () => {
    // Si acumulara, bajar a alguien de administradora a operadora le dejaría
    // los permisos de administradora.
    await abrir([ADMIN.id]);

    await userEvent.click(screen.getAllByRole('checkbox')[0]!); // desmarca admin
    await userEvent.click(screen.getByRole('button', { name: /Guardar/i }));

    await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    expect(put.mock.calls[0][1]).toEqual({ role_ids: [] });
  });

  it('manda el rol elegido', async () => {
    await abrir();

    await userEvent.click(screen.getAllByRole('checkbox')[1]!); // marca encargado
    await userEvent.click(screen.getByRole('button', { name: /Guardar/i }));

    await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    expect(put.mock.calls[0][1]).toEqual({ role_ids: [ENCARGADO.id] });
  });

  it('muestra qué cambió, en vez de cerrar en silencio', async () => {
    // Retirar un rol quita accesos que la persona tenía, y quien lo hace
    // debería verlo escrito.
    put.mockResolvedValue({
      role_ids: [ENCARGADO.id],
      codigos: ['encargado_ambiental'],
      efectos: ['se asigno un rol nuevo'],
    });
    await abrir();

    await userEvent.click(screen.getAllByRole('checkbox')[1]!);
    await userEvent.click(screen.getByRole('button', { name: /Guardar/i }));

    expect(await screen.findByText(/se asigno un rol nuevo/)).toBeInTheDocument();
  });
});

describe('cuando el servidor rechaza', () => {
  it('muestra el motivo TAL CUAL', async () => {
    // El 409 de #141/#140: dejaría a la empresa sin nadie que administre
    // usuarios. Ese mensaje dice qué hacer; uno genérico no.
    const { ApiError } = await import('@/lib/api-client');
    put.mockRejectedValue(
      new ApiError(409, 'Conflict', {
        detail:
          'Paula Rivas es la unica persona activa que puede administrar usuarios. Asignale antes ese permiso a alguien mas.',
      }),
    );
    await abrir([ADMIN.id]);

    await userEvent.click(screen.getAllByRole('checkbox')[0]!);
    await userEvent.click(screen.getByRole('button', { name: /Guardar/i }));

    expect(
      await screen.findByText(/unica persona activa que puede administrar usuarios/),
    ).toBeInTheDocument();
  });

  it('y no dice que cambió nada', async () => {
    const { ApiError } = await import('@/lib/api-client');
    put.mockRejectedValue(new ApiError(409, 'Conflict', { detail: 'no se puede' }));
    await abrir([ADMIN.id]);

    await userEvent.click(screen.getAllByRole('checkbox')[0]!);
    await userEvent.click(screen.getByRole('button', { name: /Guardar/i }));

    await screen.findByText(/no se puede/);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});

describe('quedarse sin ningún rol', () => {
  it('se avisa ANTES de guardar', async () => {
    // Sin ningún rol la persona no puede hacer nada. Es legítimo —así se
    // retira el acceso sin sacarla de la nómina— pero tiene que verse.
    await abrir([ADMIN.id]);

    await userEvent.click(screen.getAllByRole('checkbox')[0]!);

    expect(screen.getByText(/no podrá hacer nada en el sistema/i)).toBeInTheDocument();
  });

  it('con algún rol marcado NO aparece el aviso', async () => {
    // La otra mitad: un aviso que sale siempre deja de leerse.
    await abrir([ADMIN.id]);

    expect(screen.queryByText(/no podrá hacer nada/i)).not.toBeInTheDocument();
  });
});

describe('cuando la carga falla', () => {
  it('lo dice, en vez de parecer que la empresa no tiene roles', async () => {
    const { ApiError } = await import('@/lib/api-client');
    get.mockRejectedValue(new ApiError(500, 'Error', { detail: 'se cayo' }));
    render(<RolDePermisosModal open onOpenChange={vi.fn()} user={PERSONA as never} />, {
      wrapper: envoltura,
    });

    expect(await screen.findByText(/No se pudieron cargar los roles/i)).toBeInTheDocument();
  });
});
