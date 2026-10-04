import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { esRutaPublica } from '@/lib/rutas-publicas';
import { ClerkApiBridge } from './ClerkApiBridge';

const replace = vi.fn();
let alPerderLaSesion: (() => void) | null = null;

vi.mock('@clerk/nextjs', () => ({
  useAuth: () => ({ getToken: vi.fn(), isLoaded: true, isSignedIn: false }),
}));
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace }) }));
vi.mock('@/lib/api-client', () => ({
  registrarProveedorDeToken: vi.fn(),
  registrarSesionExpirada: (f: (() => void) | null) => {
    if (f) alPerderLaSesion = f;
  },
}));

beforeEach(() => {
  replace.mockClear();
  alPerderLaSesion = null;
});

function unaPeticionRespondio401En(pathname: string) {
  window.history.pushState({}, '', pathname);
  render(<ClerkApiBridge />);
  alPerderLaSesion!();
}

describe('un 401 sin sesion de Clerk', () => {
  it('en una pantalla del sistema manda al ingreso', () => {
    unaPeticionRespondio401En('/dashboard');
    expect(replace).toHaveBeenCalledWith('/login');
  });

  it.each(['/acceso-invitado', '/signup', '/crear-ticket', '/login'])(
    'en %s no: ahi no tener sesion es lo normal',
    (ruta) => {
      // Medido el 22-sep con Clerk activo: el acceso de invitado y el registro
      // con invitacion rebotaban a /login, porque la lista de usuarios se pide
      // al montar la aplicacion y responde 401 sin sesion.
      unaPeticionRespondio401En(ruta);
      expect(replace).not.toHaveBeenCalled();
    },
  );
});

describe('que pantalla es publica', () => {
  it('se decide por segmento, no por prefijo de texto', () => {
    expect(esRutaPublica('/acceso-invitado/seguimiento')).toBe(true);
    expect(esRutaPublica('/signups')).toBe(false);
    expect(esRutaPublica('/dashboard')).toBe(false);
  });
});
