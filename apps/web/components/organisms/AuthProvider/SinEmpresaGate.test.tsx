import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SinEmpresaGate } from './SinEmpresaGate';
import { marcarSesionSinEmpresa } from '@/lib/sesion-sin-empresa';

const signOut = vi.fn().mockResolvedValue(undefined);
vi.mock('@clerk/nextjs', () => ({
  useClerk: () => ({ signOut }),
  useUser: () => ({ user: { primaryEmailAddress: { emailAddress: 'persona@empresa.cl' } } }),
}));

beforeEach(() => {
  signOut.mockClear();
  marcarSesionSinEmpresa(false);
});

describe('SinEmpresaGate', () => {
  it('con empresa muestra la aplicación', () => {
    render(<SinEmpresaGate><p>tablero</p></SinEmpresaGate>);
    expect(screen.getByText('tablero')).toBeInTheDocument();
  });

  it('cuando la API dice "sin empresa", reemplaza la aplicación por la explicación', () => {
    render(<SinEmpresaGate><p>tablero</p></SinEmpresaGate>);
    act(() => marcarSesionSinEmpresa(true));
    expect(screen.queryByText('tablero')).not.toBeInTheDocument();
    expect(screen.getByText('Tu cuenta todavía no tiene acceso')).toBeInTheDocument();
  });

  it('cerrar sesión llama a Clerk y limpia la marca para la próxima cuenta', async () => {
    render(<SinEmpresaGate><p>tablero</p></SinEmpresaGate>);
    act(() => marcarSesionSinEmpresa(true));
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }));
    expect(signOut).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('tablero')).toBeInTheDocument();
  });
});
