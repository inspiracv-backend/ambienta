import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiError } from '@/lib/api-client';
import type { CitaDelAsistente } from '@/lib/chatbot';
import { ChatbotPanel } from './ChatbotPanel';
import type { Responder } from './ChatbotPanel.types';

/**
 * El panel del asistente.
 *
 * Lo que se mide acá es lo que **no se puede deducir del texto** de una
 * respuesta: si el asistente se abstuvo, si lo que se muestra es una falla y
 * no una respuesta, y si el hilo de conversación se mantiene.
 */

const CITA: CitaDelAsistente = {
  norma: 'Ley 20.920',
  articulo: '12',
  texto: 'Los productores deberán...',
  ruta: 'titulo-ii/articulo-12',
  norm_id: 'norm-1',
  article_id: 'art-1',
  norm_version_id: null,
  official_url: null,
  origen: 'catalogo',
};

function preguntar(texto = '¿Qué exige la Ley REP?') {
  return async () => {
    await userEvent.type(screen.getByLabelText('Mensaje para el chatbot'), texto);
    await userEvent.click(screen.getByLabelText('Enviar'));
  };
}

describe('el panel del chatbot', () => {
  it('muestra la respuesta y enlaza cada cita a su norma', async () => {
    const responder: Responder = vi.fn().mockResolvedValue({
      texto: 'La Ley REP exige metas de valorización.',
      conversacionId: 'c-1',
      seAbstuvo: false,
      citas: [CITA],
    });

    render(<ChatbotPanel responder={responder} examplePrompts={['¿Cuándo vence SIDREP?']} />);
    await preguntar()();

    expect(await screen.findByText('La Ley REP exige metas de valorización.')).toBeTruthy();
    const enlace = screen.getByRole('link', { name: /Ley 20.920, artículo 12/ });
    expect(enlace.getAttribute('href')).toBe('/matriz-legal/norm-1');
  });

  it('una abstención se marca, y no se deduce leyendo el texto', async () => {
    /** El campo lo declara el servicio. Mostrar un «no tengo información
     * suficiente» igual que un hecho comprobado es el error que esto evita. */
    const responder: Responder = vi.fn().mockResolvedValue({
      texto: 'No tengo información suficiente para responder eso.',
      seAbstuvo: true,
      citas: [],
    });

    render(<ChatbotPanel responder={responder} examplePrompts={[]} />);
    await preguntar()();

    expect(await screen.findByText('Sin evidencia suficiente')).toBeTruthy();
  });

  it('una respuesta fundamentada NO lleva esa marca', async () => {
    const responder: Responder = vi.fn().mockResolvedValue({
      texto: 'Vence el 31 de marzo.',
      seAbstuvo: false,
      citas: [CITA],
    });

    render(<ChatbotPanel responder={responder} examplePrompts={[]} />);
    await preguntar()();

    await screen.findByText('Vence el 31 de marzo.');
    expect(screen.queryByText('Sin evidencia suficiente')).toBeNull();
    // Y tampoco es una falla: una respuesta buena no se anuncia como alerta.
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('el segundo turno viaja con la conversación que abrió el primero', async () => {
    /** Sin esto cada pregunta empieza un hilo nuevo y el asistente contesta
     * sin recordar la anterior — y el síntoma se lee como que "no entiende". */
    const responder = vi.fn().mockResolvedValue({ texto: 'ok', conversacionId: 'c-9', citas: [] });

    render(<ChatbotPanel responder={responder} examplePrompts={[]} />);
    await preguntar('primera')();
    await screen.findByText('ok');
    await preguntar('segunda')();

    await waitFor(() => expect(responder).toHaveBeenCalledTimes(2));
    expect(responder.mock.calls[0][0]).toEqual({ pregunta: 'primera', conversacionId: null });
    expect(responder.mock.calls[1][0]).toEqual({ pregunta: 'segunda', conversacionId: 'c-9' });
  });

  it('una respuesta sin conversación no borra la que ya había', async () => {
    const responder = vi
      .fn()
      .mockResolvedValueOnce({ texto: 'uno', conversacionId: 'c-9', citas: [] })
      .mockResolvedValueOnce({ texto: 'dos', conversacionId: null, citas: [] })
      .mockResolvedValue({ texto: 'tres', citas: [] });

    render(<ChatbotPanel responder={responder} examplePrompts={[]} />);
    await preguntar('a')();
    await screen.findByText('uno');
    await preguntar('b')();
    await screen.findByText('dos');
    await preguntar('c')();

    await waitFor(() => expect(responder).toHaveBeenCalledTimes(3));
    expect(responder.mock.calls[2][0]).toEqual({ pregunta: 'c', conversacionId: 'c-9' });
  });

  it('cuando el asistente no está configurado lo dice, y no parece una respuesta', async () => {
    const responder: Responder = vi
      .fn()
      .mockRejectedValue(
        new ApiError(503, 'Service Unavailable', {
          detail: { codigo: 'ai_service_sin_configurar', mensaje: 'Falta AI_SERVICE_URL.' },
        }),
      );

    render(<ChatbotPanel responder={responder} examplePrompts={[]} />);
    await preguntar()();

    expect(await screen.findByText(/todavía no está disponible/)).toBeTruthy();
    // **No se le presta la cara del asistente a un error.** Va como alerta, no
    // como un turno mas de la conversacion.
    expect(screen.getByRole('alert').textContent).toContain('todavía no está disponible');
    expect(screen.queryByText('Sin evidencia suficiente')).toBeNull();
  });

  it('si el hilo se perdio, la siguiente pregunta empieza uno nuevo', async () => {
    /** La API valida que la conversacion sea de esta empresa. Si se retiro,
     * arrastrar su id deja **todas** las preguntas siguientes fallando igual y
     * el chat roto hasta recargar. Visto en el navegador. */
    const responder = vi
      .fn()
      .mockResolvedValueOnce({ texto: 'uno', conversacionId: 'c-perdida', citas: [] })
      .mockRejectedValueOnce(new ApiError(404, 'Not Found', { detail: 'ChatbotConversation not found' }))
      .mockResolvedValue({ texto: 'tres', conversacionId: 'c-nueva', citas: [] });

    render(<ChatbotPanel responder={responder} examplePrompts={[]} />);
    await preguntar('a')();
    await screen.findByText('uno');
    await preguntar('b')();
    await screen.findByRole('alert');
    await preguntar('c')();

    await waitFor(() => expect(responder).toHaveBeenCalledTimes(3));
    expect(responder.mock.calls[1][0]).toEqual({ pregunta: 'b', conversacionId: 'c-perdida' });
    expect(responder.mock.calls[2][0]).toEqual({ pregunta: 'c', conversacionId: null });
  });

  it('y lo dice con palabras, no con el nombre de una clase', async () => {
    /** La API contesta `ChatbotConversation not found`. Eso es para un log. */
    const responder: Responder = vi
      .fn()
      .mockRejectedValue(new ApiError(404, 'Not Found', { detail: 'ChatbotConversation not found' }));

    render(<ChatbotPanel responder={responder} examplePrompts={[]} />);
    await preguntar()();

    expect(await screen.findByText(/Esa conversación ya no existe/)).toBeTruthy();
    expect(screen.queryByText(/ChatbotConversation/)).toBeNull();
  });

  it('la pregunta queda en pantalla aunque la consulta falle', async () => {
    const responder: Responder = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    render(<ChatbotPanel responder={responder} examplePrompts={[]} />);
    await preguntar('¿Y la RCA?')();

    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByText(/No se pudo contactar/)).toBeTruthy();
    expect(screen.getByText('¿Y la RCA?')).toBeTruthy();
  });

  it('no manda una segunda pregunta mientras la primera está en vuelo', async () => {
    /** Dos consultas en vuelo vuelven en cualquier orden y el hilo queda con
     * las respuestas cruzadas. El campo **sigue habilitado** —se puede ir
     * escribiendo la siguiente— asi que la regla la sostiene el envío. */
    let resolver: ((v: unknown) => void) | undefined;
    const responder: Responder = vi.fn().mockImplementation(
      () =>
        new Promise((r) => {
          resolver = r;
        }),
    );

    render(<ChatbotPanel responder={responder} examplePrompts={[]} />);
    await preguntar('primera')();
    await waitFor(() => expect(responder).toHaveBeenCalledTimes(1));

    await preguntar('segunda')();

    expect(responder).toHaveBeenCalledTimes(1);
    // Y el borrador no se perdió: no se envió, así que sigue escrito.
    expect(screen.getByLabelText('Mensaje para el chatbot')).toHaveProperty('value', 'segunda');

    resolver?.({ texto: 'lista', citas: [] });
    expect(await screen.findByText('lista')).toBeTruthy();
  });

  it('mientras espera, el formulario lo dice', async () => {
    let resolver: ((v: unknown) => void) | undefined;
    const responder: Responder = vi.fn().mockImplementation(
      () =>
        new Promise((r) => {
          resolver = r;
        }),
    );

    const { container } = render(<ChatbotPanel responder={responder} examplePrompts={[]} />);
    await preguntar('primera')();

    await waitFor(() =>
      expect(container.querySelector('form')?.getAttribute('aria-busy')).toBe('true'),
    );
    expect(screen.getByText('Escribiendo…')).toBeTruthy();

    resolver?.({ texto: 'lista', citas: [] });
    await screen.findByText('lista');
    expect(container.querySelector('form')?.getAttribute('aria-busy')).toBe('false');
  });

  it('un ejemplo llena el campo en vez de preguntar solo', async () => {
    const responder: Responder = vi.fn().mockResolvedValue({ texto: 'x', citas: [] });

    render(<ChatbotPanel responder={responder} examplePrompts={['¿Cuándo vence SIDREP?']} />);
    await userEvent.click(screen.getByText('¿Cuándo vence SIDREP?'));

    expect(screen.getByLabelText('Mensaje para el chatbot')).toHaveProperty(
      'value',
      '¿Cuándo vence SIDREP?',
    );
    expect(responder).not.toHaveBeenCalled();
  });
});
