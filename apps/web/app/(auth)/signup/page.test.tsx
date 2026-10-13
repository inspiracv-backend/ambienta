import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import SignUpPage from './page';

vi.mock('@/lib/clerk-config', () => ({ CLERK_HABILITADO: true }));
vi.mock('@clerk/nextjs', () => ({ SignUp: () => <div>formulario de registro de Clerk</div> }));

describe('el registro', () => {
  it('sin invitacion no ofrece crear una cuenta: dice que el acceso lo habilita la empresa', () => {
    // Hasta el 22-sep montaba el formulario de Clerk para cualquiera.
    render(<SignUpPage searchParams={{}} />);

    expect(screen.getByRole('heading', { name: 'El acceso lo habilita tu empresa' })).toBeTruthy();
    expect(screen.queryByText('formulario de registro de Clerk')).toBeNull();
  });

  it('con el ticket de una invitacion si: es como la persona invitada crea su cuenta', () => {
    render(<SignUpPage searchParams={{ __clerk_ticket: 'tkt_123' }} />);

    expect(screen.getByText('formulario de registro de Clerk')).toBeTruthy();
  });
});
