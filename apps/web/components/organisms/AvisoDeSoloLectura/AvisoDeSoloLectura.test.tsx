import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AvisoDeSoloLectura } from './AvisoDeSoloLectura';

/** El aviso de empresa en solo lectura (spec de RBAC, 21-sep). */

let estado = 'activo';
vi.mock('@/lib/session', () => ({ useSession: () => ({ user: { tenantId: 't1' } }) }));
vi.mock('@/lib/tenants-store', () => ({ useTenants: () => ({ tenants: [{ id: 't1', estado }] }) }));

describe('el aviso de solo lectura', () => {
  it('una empresa suspendida lo ve, con como reactivarla', () => {
    estado = 'suspendido';
    render(<AvisoDeSoloLectura />);

    expect(screen.getByRole('status').textContent).toMatch(/Empresa suspendida/);
    expect(screen.getByRole('status').textContent).toMatch(/consultar y exportar/);
    expect(screen.getByRole('status').textContent).toMatch(/contacta a Ambienta/);
  });

  it('una cerrada tambien, sin ofrecer reactivarla', () => {
    estado = 'cerrado';
    render(<AvisoDeSoloLectura />);

    expect(screen.getByRole('status').textContent).toMatch(/Empresa cerrada/);
    expect(screen.getByRole('status').textContent).not.toMatch(/reactivarla/);
  });

  it('una activa no ve nada', () => {
    estado = 'activo';
    const { container } = render(<AvisoDeSoloLectura />);

    expect(container.textContent).toBe('');
  });
});
