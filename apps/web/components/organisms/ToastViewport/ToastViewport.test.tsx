import { describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ToastProvider, useToast } from '@/lib/toast-store';
import { ToastViewport } from './ToastViewport';

/**
 * Los toasts son la única confirmación de que una acción ocurrió (H1). Se
 * prueba sobre todo lo que rompería su utilidad: que los errores interrumpan
 * al lector de pantalla y los éxitos no, y que "Deshacer" realmente ejecute
 * la reversión (H3).
 */

function Disparador({ onUndo }: { onUndo?: () => void }) {
  const { mostrarToast } = useToast();
  return (
    <div>
      <button onClick={() => mostrarToast({ tipo: 'exito', mensaje: 'Guardado', descripcion: 'Todo bien' })}>
        exito
      </button>
      <button onClick={() => mostrarToast({ tipo: 'error', mensaje: 'Falló' })}>error</button>
      <button onClick={() => mostrarToast({ tipo: 'info', mensaje: 'Suspendida', onUndo })}>con-undo</button>
    </div>
  );
}

function montar(onUndo?: () => void) {
  return render(
    <ToastProvider>
      <Disparador onUndo={onUndo} />
      <ToastViewport />
    </ToastProvider>,
  );
}

describe('ToastViewport', () => {
  it('no renderiza nada cuando no hay avisos', () => {
    montar();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('muestra mensaje y descripción', async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByText('exito'));

    expect(await screen.findByText('Guardado')).toBeInTheDocument();
    expect(screen.getByText('Todo bien')).toBeInTheDocument();
  });

  it('usa role="alert" en errores para que interrumpan al lector de pantalla', async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByText('error'));

    expect(await screen.findByRole('alert')).toHaveTextContent('Falló');
  });

  it('usa role="status" en éxitos para no interrumpir', async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByText('exito'));

    expect(await screen.findByRole('status')).toHaveTextContent('Guardado');
  });

  it('permite cerrar un aviso a mano', async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByText('exito'));
    await screen.findByText('Guardado');

    await user.click(screen.getByRole('button', { name: /cerrar aviso/i }));
    await waitFor(() => expect(screen.queryByText('Guardado')).not.toBeInTheDocument());
  });

  it('ejecuta la reversión al pulsar Deshacer y cierra el aviso', async () => {
    const user = userEvent.setup();
    const revertir = vi.fn();
    montar(revertir);

    await user.click(screen.getByText('con-undo'));
    await user.click(await screen.findByRole('button', { name: /deshacer/i }));

    expect(revertir).toHaveBeenCalledOnce();
    await waitFor(() => expect(screen.queryByText('Suspendida')).not.toBeInTheDocument());
  });

  it('no muestra Deshacer si la acción no ofrece reversión', async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByText('exito'));
    await screen.findByText('Guardado');

    expect(screen.queryByRole('button', { name: /deshacer/i })).not.toBeInTheDocument();
  });

  it('apila varios avisos a la vez', async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByText('exito'));
    await user.click(screen.getByText('error'));

    expect(await screen.findByText('Guardado')).toBeInTheDocument();
    expect(screen.getByText('Falló')).toBeInTheDocument();
  });

  it('se desvanece solo pasado su tiempo, y el error dura más que el éxito', async () => {
    vi.useFakeTimers();
    montar();

    // `fireEvent` en vez de `userEvent`: userEvent encola su trabajo en
    // promesas que los timers falsos también interceptan, y el test se cuelga.
    act(() => {
      fireEvent.click(screen.getByText('exito'));
      fireEvent.click(screen.getByText('error'));
    });
    expect(screen.getByText('Guardado')).toBeInTheDocument();
    expect(screen.getByText('Falló')).toBeInTheDocument();

    // A los 4s se va el éxito. El error se queda: suele traer información que
    // hay que alcanzar a leer.
    // Se avanza dentro de `act` en vez de `waitFor` porque waitFor usa timers
    // reales internamente y con timers falsos nunca resolvería.
    await act(async () => {
      vi.advanceTimersByTime(4100);
    });
    expect(screen.queryByText('Guardado')).not.toBeInTheDocument();
    expect(screen.getByText('Falló')).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(4100);
    });
    expect(screen.queryByText('Falló')).not.toBeInTheDocument();

    vi.useRealTimers();
  });
});
