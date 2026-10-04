import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FEATURE_FLAGS } from '@ambienta/shared';
import { PestanasDeIngreso } from './PestanasDeIngreso';

/** El ingreso con RUT, detras de su bandera (decisión 6 del 21-sep). */

vi.mock('@clerk/nextjs', () => ({ SignIn: () => <div data-testid="ingreso-clerk" /> }));
vi.mock('@/components/organisms/IngresoConRut', () => ({ IngresoConRut: () => <div data-testid="ingreso-rut" /> }));

const original = FEATURE_FLAGS.ingresoConRut;
afterEach(() => {
  FEATURE_FLAGS.ingresoConRut = original;
});

describe('las formas de ingresar', () => {
  it('por defecto la bandera esta apagada', () => {
    // Apagada es la decision de v1.0: encenderla por accidente mostraria un
    // ingreso que nadie decidio ofrecer todavia.
    expect(original).toBe(false);
  });

  it('apagada, solo el ingreso de Clerk y sin pestañas', () => {
    FEATURE_FLAGS.ingresoConRut = false;
    render(<PestanasDeIngreso />);

    expect(screen.getByTestId('ingreso-clerk')).toBeTruthy();
    expect(screen.queryByRole('tablist')).toBeNull();
    expect(screen.queryByText('RUT y clave')).toBeNull();
  });

  it('encendida, vuelven las dos pestañas', () => {
    FEATURE_FLAGS.ingresoConRut = true;
    render(<PestanasDeIngreso />);

    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Correo o usuario', 'RUT y clave']);
  });
});
