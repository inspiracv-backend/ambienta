import { describe, expect, it } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { UsersProvider, useUsers } from './users-store';
import { ToastProvider } from './toast-store';
import { nombreDeUsuario, useNombreDeUsuario } from './get-user-name';

const PERSONAS = [{ id: 'u-1', nombre: 'Camila Rojas' }];

describe('nombreDeUsuario', () => {
  it('con responsable conocido, su nombre', () => {
    expect(nombreDeUsuario(PERSONAS, 'u-1')).toBe('Camila Rojas');
  });

  it('sin responsable, "Sin asignar"', () => {
    expect(nombreDeUsuario(PERSONAS, undefined)).toBe('Sin asignar');
    expect(nombreDeUsuario(PERSONAS, null)).toBe('Sin asignar');
    expect(nombreDeUsuario(PERSONAS, '')).toBe('Sin asignar');
  });

  it('con un id que no está cargado NO dice "Sin asignar": hay alguien asignado', () => {
    // Era el defecto: buscaba solo en `mockUsers`, y todo UUID real salía
    // "Sin asignar" en doce pantallas.
    expect(nombreDeUsuario(PERSONAS, 'a0000000-0000-0000-0000-00000000dead')).toBe('Responsable no identificado');
  });
});

describe('useNombreDeUsuario', () => {
  it('fuera del UsersProvider no revienta', () => {
    const { result } = renderHook(() => useNombreDeUsuario());
    expect(result.current(undefined)).toBe('Sin asignar');
    expect(result.current('u-1')).toBe('Responsable no identificado');
  });
});

describe('dentro del UsersProvider', () => {
  it('resuelve con las personas que tiene el store, y no con una lista fija', async () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ToastProvider>
        <UsersProvider>{children}</UsersProvider>
      </ToastProvider>
    );
    const { result } = renderHook(() => ({ nombre: useNombreDeUsuario(), store: useUsers() }), { wrapper });
    await waitFor(() => expect(result.current.store.users.length).toBeGreaterThan(0));
    const alguien = result.current.store.users[0];
    expect(result.current.nombre(alguien.id)).toBe(alguien.nombre);
  });
});
