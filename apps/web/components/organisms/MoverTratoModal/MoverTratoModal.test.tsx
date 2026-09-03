/**
 * Mover un trato de etapa desde la ficha: el motivo se pide antes del 422.
 *
 * El servidor exige motivo al mover a una etapa de tipo `lost` y rechaza sin
 * él. Preguntarlo acá es cortesía, no la barrera — pero es la diferencia entre
 * que la persona escriba por qué se perdió el trato y que reciba un error de
 * validación sobre un campo que la pantalla nunca le mostró.
 *
 * Las pruebas afirman sobre **lo que se ve**, no sobre `necesitaMotivo`: esa
 * función ya tiene sus propias pruebas, y comprobarla otra vez no diría nada
 * sobre si el formulario la usa.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MoverTratoModal } from './MoverTratoModal';
import type { EtapaCrm, TratoCrm } from '@/lib/crm';

const ETAPAS: EtapaCrm[] = [
  { id: 'e-1', codigo: 'neg', nombre: 'Negociación', posicion: 1, tipo: 'open' },
  { id: 'e-2', codigo: 'won', nombre: 'Ganado', posicion: 2, tipo: 'won' },
  { id: 'e-3', codigo: 'lost', nombre: 'Perdido', posicion: 3, tipo: 'lost' },
];

const TRATO: TratoCrm = {
  id: 't-1',
  empresaId: 'c-1',
  contactoId: null,
  etapaId: 'e-1',
  titulo: 'Implantación matriz legal',
  monto: 1000,
  moneda: 'CLP',
  responsableId: null,
  cierreEstimado: null,
  cerradoEn: null,
  motivoPerdida: null,
  contratoId: null,
};

function montar(onMover = vi.fn().mockResolvedValue({ ok: true, efectos: [] })) {
  render(
    <MoverTratoModal
      open
      onOpenChange={vi.fn()}
      trato={TRATO}
      etapas={ETAPAS}
      onMover={onMover}
    />,
  );
  return onMover;
}

describe('mover a una etapa que pierde', () => {
  it('aparece el campo de motivo', async () => {
    montar();
    const usuario = userEvent.setup();

    await usuario.selectOptions(screen.getByLabelText('Etapa'), 'e-3');

    expect(screen.getByLabelText(/Motivo de la pérdida/)).toBeInTheDocument();
  });

  it('sin motivo NO se puede mover', async () => {
    // La afirmación central: sin esto el botón manda, el servidor responde 422
    // y el error habla de un campo que nunca se mostró.
    montar();
    const usuario = userEvent.setup();

    await usuario.selectOptions(screen.getByLabelText('Etapa'), 'e-3');

    expect(screen.getByRole('button', { name: 'Mover' })).toBeDisabled();
  });

  it('con motivo se manda, y el motivo viaja', async () => {
    const onMover = montar();
    const usuario = userEvent.setup();

    await usuario.selectOptions(screen.getByLabelText('Etapa'), 'e-3');
    await usuario.type(screen.getByLabelText(/Motivo de la pérdida/), 'Se fue por precio');
    await usuario.click(screen.getByRole('button', { name: 'Mover' }));

    await waitFor(() =>
      expect(onMover).toHaveBeenCalledWith('t-1', 'e-3', 'Se fue por precio'),
    );
  });
});

describe('mover a una etapa que no pierde', () => {
  it('no se pide motivo y se puede mover directo', async () => {
    // La otra mitad: pedir motivo siempre convertiría cada movimiento en un
    // trámite, y se dejaría de mover las tarjetas.
    const onMover = montar();
    const usuario = userEvent.setup();

    await usuario.selectOptions(screen.getByLabelText('Etapa'), 'e-2');

    expect(screen.queryByLabelText(/Motivo de la pérdida/)).not.toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: 'Mover' }));
    await waitFor(() => expect(onMover).toHaveBeenCalledWith('t-1', 'e-2', undefined));
  });
});

describe('la etapa en la que ya está', () => {
  it('no se puede «mover» a la misma columna', async () => {
    // Sería una petición que no cambia nada y que, en una etapa de perdido,
    // pediría motivo de nuevo por un movimiento que no ocurre.
    montar();

    expect(screen.getByRole('button', { name: 'Mover' })).toBeDisabled();
  });
});

describe('cuando el servidor rechaza', () => {
  it('el error se queda en el formulario y no cierra el modal', async () => {
    const onOpenChange = vi.fn();
    render(
      <MoverTratoModal
        open
        onOpenChange={onOpenChange}
        trato={TRATO}
        etapas={ETAPAS}
        onMover={vi.fn().mockResolvedValue({ ok: false, error: 'El trato ya está cerrado.' })}
      />,
    );
    const usuario = userEvent.setup();

    await usuario.selectOptions(screen.getByLabelText('Etapa'), 'e-2');
    await usuario.click(screen.getByRole('button', { name: 'Mover' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('El trato ya está cerrado.');
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });
});
