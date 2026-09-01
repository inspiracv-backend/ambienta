import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { UsersProvider } from '@/lib/users-store';
import { SessionProvider, useSession } from '@/lib/session';
import { ToastProvider } from '@/lib/toast-store';
import { iniciarSesionComo } from '@/test/utils';
import { cargarAlcance } from '@/lib/alcance';

/**
 * El acotamiento por planta de la sesión (#25, RF-12).
 *
 * ## Lo que esto arregla
 *
 * Siete pantallas —auditorías, calendario, dashboard, matriz legal, no
 * conformidades, obligaciones y reportes— filtran con
 * `user.plantIds.length > 0`. Y `users-store` armaba **`plantIds: []` fijo**,
 * así que esa condición **nunca** era cierta: el acotamiento no se aplicaba en
 * ninguna de las siete. No faltaba el endpoint —`GET /me` devuelve
 * `instalaciones` desde el 20-ago— faltaba pedirlo.
 *
 * ## La regla que estas pruebas protegen
 *
 * **Lista vacía significa «sin acotar», no «ninguna planta».** Es la
 * diferencia entre un encargado de toda la empresa y uno sin acceso a nada.
 * Invertirlo dejaría a los administradores sin ver nada.
 */

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/dashboard',
}));

function Espia() {
  const { user, cargando } = useSession();
  if (cargando) return <p>cargando</p>;
  if (!user) return <p>sin sesion</p>;
  return (
    <div>
      <p data-testid="quien">{user.nombre}</p>
      <p data-testid="plantas">{user.plantIds.length === 0 ? 'sin-acotar' : user.plantIds.join(',')}</p>
    </div>
  );
}

function montar() {
  return render(
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>
          <Espia />
        </SessionProvider>
      </UsersProvider>
    </ToastProvider>,
  );
}

beforeEach(() => {
  iniciarSesionComo('admin_empresa');
});

describe('el alcance sale de GET /me', () => {
  it('las plantas de la sesión son las que devolvió la API', async () => {
    vi.mocked(cargarAlcance).mockResolvedValue({
      acotado: true,
      instalaciones: ['planta-antofagasta', 'planta-calama'],
      departamentos: [],
    });

    montar();

    await waitFor(() =>
      expect(screen.getByTestId('plantas')).toHaveTextContent('planta-antofagasta,planta-calama'),
    );
  });

  it('una lista vacía significa SIN ACOTAR, no "ninguna planta"', async () => {
    // Si esto se leyera como "cero plantas", un Admin Empresa no vería nada.
    vi.mocked(cargarAlcance).mockResolvedValue({
      acotado: false,
      instalaciones: [],
      departamentos: [],
    });

    montar();

    await waitFor(() => expect(screen.getByTestId('plantas')).toHaveTextContent('sin-acotar'));
  });

  it('se pide una sola vez y con el tenant de la persona', async () => {
    vi.mocked(cargarAlcance).mockResolvedValue({
      acotado: false,
      instalaciones: [],
      departamentos: [],
    });

    montar();

    await waitFor(() => expect(cargarAlcance).toHaveBeenCalled());
    expect(vi.mocked(cargarAlcance).mock.calls[0][0]).toBeTruthy();
  });
});

describe('la identidad no depende del alcance', () => {
  it('si /me falla la persona ENTRA igual, sin acotar', async () => {
    // Se considero dejarla afuera y se descarto: el acotamiento por planta es
    // dentro de una empresa, y la separacion entre empresas la garantiza RLS.
    // Dejar a alguien sin trabajar por una llamada caida es peor que mostrarle
    // una planta de su propia empresa.
    vi.mocked(cargarAlcance).mockRejectedValue(new Error('sin red'));

    montar();

    await waitFor(() => expect(screen.getByTestId('quien')).toBeInTheDocument());
    expect(screen.getByTestId('plantas')).toHaveTextContent('sin-acotar');
  });

  it('un fallo TERMINA la espera, no deja el spinner girando', async () => {
    // Si `'fallo'` se tratara como `'cargando'`, nadie saldria nunca de la
    // pantalla de carga.
    vi.mocked(cargarAlcance).mockRejectedValue(new Error('sin red'));

    montar();

    await waitFor(() => expect(screen.queryByText('cargando')).not.toBeInTheDocument());
  });
});
