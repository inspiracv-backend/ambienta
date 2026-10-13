import { describe, expect, it } from 'vitest';
import { ventanasDe } from './NotificationPreferencesForm';

/** Mismo cálculo que `ventanas_de` en `services/avisos_de_vencimiento.py`. */
describe('ventanasDe', () => {
  it('sin reglas usa los valores por defecto del generador, no 30/15/7', () => {
    expect(ventanasDe([])).toEqual({ dias: [15, 7, 3, 1], porDefecto: true });
  });

  it('usa las reglas activas del evento, de mayor a menor y sin repetidos', () => {
    const r = ventanasDe([
      { event_type: 'obligation_due', lead_minutes: 7 * 1440, active: true },
      { event_type: 'obligation_due', lead_minutes: 30 * 1440, active: true },
      { event_type: 'obligation_due', lead_minutes: 7 * 1440, active: true },
    ]);
    expect(r).toEqual({ dias: [30, 7], porDefecto: false });
  });

  it('ignora inactivas, otros eventos, avisos posteriores y plazos de menos de un día', () => {
    const r = ventanasDe([
      { event_type: 'obligation_due', lead_minutes: 10 * 1440, active: false },
      { event_type: 'audit_due', lead_minutes: 5 * 1440, active: true },
      { event_type: 'obligation_due', lead_minutes: -1440, active: true },
      { event_type: 'obligation_due', lead_minutes: 600, active: true },
    ]);
    expect(r.porDefecto).toBe(true);
  });
});
