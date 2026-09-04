/**
 * Anotar una actividad en la ficha: lo escrito no se pierde si falla.
 *
 * Es la acción más frecuente del CRM y la más fácil de abandonar. Si la API
 * rechaza y el formulario se limpia, hay que volver a tipear el resumen de una
 * llamada que ya terminó — y ese es exactamente el momento en que se deja de
 * anotar y el CRM se queda sin historial.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RegistrarActividadCrm } from './RegistrarActividadCrm';

describe('cuando se guarda bien', () => {
  it('manda el tipo, el asunto y el detalle', async () => {
    const onRegistrar = vi.fn().mockResolvedValue({ ok: true });
    render(<RegistrarActividadCrm onRegistrar={onRegistrar} />);
    const usuario = userEvent.setup();

    await usuario.selectOptions(screen.getByLabelText('Tipo'), 'meeting');
    await usuario.type(screen.getByLabelText('Asunto'), 'Reunión de kickoff');
    await usuario.type(screen.getByLabelText('Detalle'), 'Quedaron de mandar el alcance');
    await usuario.click(screen.getByRole('button', { name: 'Anotar' }));

    await waitFor(() =>
      expect(onRegistrar).toHaveBeenCalledWith({
        tipo: 'meeting',
        asunto: 'Reunión de kickoff',
        detalle: 'Quedaron de mandar el alcance',
      }),
    );
  });

  it('el formulario queda limpio para la siguiente', async () => {
    render(<RegistrarActividadCrm onRegistrar={vi.fn().mockResolvedValue({ ok: true })} />);
    const usuario = userEvent.setup();

    await usuario.type(screen.getByLabelText('Asunto'), 'Llamada');
    await usuario.click(screen.getByRole('button', { name: 'Anotar' }));

    await waitFor(() => expect(screen.getByLabelText('Asunto')).toHaveValue(''));
  });
});

describe('cuando el servidor rechaza', () => {
  it('lo escrito SE QUEDA', async () => {
    // La afirmación que este archivo existe para proteger.
    render(
      <RegistrarActividadCrm
        onRegistrar={vi.fn().mockResolvedValue({ ok: false, error: 'No se pudo.' })}
      />,
    );
    const usuario = userEvent.setup();

    await usuario.type(screen.getByLabelText('Asunto'), 'Llamada de seguimiento');
    await usuario.click(screen.getByRole('button', { name: 'Anotar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo.');
    expect(screen.getByLabelText('Asunto')).toHaveValue('Llamada de seguimiento');
  });
});

describe('sin asunto', () => {
  it('no se puede anotar', async () => {
    // Una actividad sin asunto aparece en la línea de tiempo como una fila en
    // blanco: ocupa lugar y no dice nada.
    render(<RegistrarActividadCrm onRegistrar={vi.fn()} />);

    expect(screen.getByRole('button', { name: 'Anotar' })).toBeDisabled();
  });
});
