import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DashboardHeroCard } from './DashboardHeroCard';

/**
 * Cumplimiento y cobertura, lado a lado (ISO 14001, tarea "Dashboard: requisitos
 * por evaluar"). Un 30 % solo no dice si se incumple o si falta evaluar.
 */
describe('la tarjeta de cumplimiento', () => {
  it('muestra la cobertura y cuantos requisitos faltan, con enlace a la matriz', () => {
    render(<DashboardHeroCard obligation={null} cumplimientoPct={0.3} cobertura={0.3} porEvaluar={7} />);

    expect(screen.getByText('30%', { selector: 'p' })).toBeTruthy();
    expect(screen.getByText(/de los requisitos evaluados/)).toBeTruthy();
    const enlace = screen.getByRole('link', { name: '7 por evaluar' });
    expect(enlace.getAttribute('href')).toBe('/matriz-legal');
  });

  it('con todo evaluado no ofrece un "0 por evaluar"', () => {
    render(<DashboardHeroCard obligation={null} cumplimientoPct={0.4} cobertura={1} porEvaluar={0} />);

    expect(screen.getByText(/de los requisitos evaluados/)).toBeTruthy();
    expect(screen.queryByRole('link', { name: /por evaluar/ })).toBeNull();
  });

  it('sin cobertura conocida no la inventa', () => {
    // El respaldo de ejemplo, o una API anterior: no se sabe cuanto se evaluo.
    render(<DashboardHeroCard obligation={null} cumplimientoPct={0.5} />);

    expect(screen.queryByText(/de los requisitos evaluados/)).toBeNull();
  });

  it('nada evaluado: "Sin evaluar" arriba y 0 % de cobertura abajo, que si es un dato', () => {
    render(<DashboardHeroCard obligation={null} cumplimientoPct={null} cobertura={0} porEvaluar={12} />);

    expect(screen.getByText(/Sin evaluar/)).toBeTruthy();
    expect(screen.getByRole('link', { name: '12 por evaluar' })).toBeTruthy();
  });
});
