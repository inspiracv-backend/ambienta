import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { api, ApiError, mensajeDeError } from './api-client';
import { marcarSesionSinEmpresa, useSesionSinEmpresa } from './sesion-sin-empresa';
import { SinEmpresaScreen } from '@/components/organisms/SinEmpresaScreen';

/**
 * Una sesión válida sin empresa (acceso-por-sso, Fase 4). Antes era un 403 más:
 * la persona veía errores en cada pantalla y no tenía cómo salir.
 */

const SIN_EMPRESA = { detail: { codigo: 'sesion_sin_empresa', mensaje: 'Tu cuenta no esta asociada a ninguna empresa.' } };

function Espejo() {
  return <p>{useSesionSinEmpresa() ? 'sin empresa' : 'con empresa'}</p>;
}

beforeEach(() => {
  vi.unstubAllGlobals();
  marcarSesionSinEmpresa(false);
});

describe('la detección en api-client', () => {
  it('ese 403 marca la sesión', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 403, statusText: 'Forbidden', json: async () => SIN_EMPRESA }));
    render(<Espejo />);
    await expect(api.get('/obligations/')).rejects.toBeInstanceOf(ApiError);
    expect(await screen.findByText('sin empresa')).toBeInTheDocument();
  });

  it('otro 403 no la marca: se decide por el código, no por el estado', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 403, statusText: 'Forbidden', json: async () => ({ detail: { codigo: 'permiso_insuficiente', mensaje: 'x' } }) }),
    );
    render(<Espejo />);
    await expect(api.get('/obligations/')).rejects.toBeInstanceOf(ApiError);
    expect(screen.getByText('con empresa')).toBeInTheDocument();
  });

  it('un detail objeto con mensaje se muestra, en vez de "el servidor rechazó"', () => {
    expect(mensajeDeError(new ApiError(403, 'Forbidden', SIN_EMPRESA))).toBe('Tu cuenta no esta asociada a ninguna empresa.');
  });
});

describe('la pantalla', () => {
  it('dice con qué correo pedir el alta y deja cerrar sesión', async () => {
    const cerrar = vi.fn();
    render(<SinEmpresaScreen correo="persona@empresa.cl" onCerrarSesion={cerrar} />);
    expect(screen.getByText('persona@empresa.cl')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }));
    expect(cerrar).toHaveBeenCalledTimes(1);
  });

  it('no insinúa si la empresa de ese dominio existe', () => {
    render(<SinEmpresaScreen correo="persona@minera-andes.cl" onCerrarSesion={vi.fn()} />);
    // Decir "tu empresa no existe" o "ya está registrada" le confirmaría a
    // cualquiera con un correo de ese dominio si esa empresa es cliente.
    const texto = document.body.textContent ?? '';
    expect(texto).not.toMatch(/existe|registrad/i);
  });
});
