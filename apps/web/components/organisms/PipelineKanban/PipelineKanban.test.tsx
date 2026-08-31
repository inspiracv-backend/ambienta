/**
 * Lo que se lee y lo que se puede hacer en el kanban del pipeline (#81).
 *
 * Las afirmaciones son sobre **texto visible y roles accesibles**, no sobre
 * funciones internas. Es la lección de `NormDetailView.test.tsx`: había dos
 * pruebas en verde, cada una correcta por su lado, y el error vivía entre las
 * dos porque ninguna miraba la pantalla.
 *
 * Lo que este archivo protege, en orden de gravedad:
 *
 * 1. **Que se pueda mover sin arrastrar.** `dragstart` no existe en táctil ni
 *    con teclado. Ambienta es una PWA: sin el selector, el módulo entero es
 *    inutilizable en un teléfono y nada lo diría.
 * 2. **Que perder pida el motivo antes de mandar**, y que cancelar no mueva
 *    nada.
 * 3. **Que se diga qué más pasó.** Mover a "Ganado" cierra el trato; en
 *    silencio, la persona lo descubre cuando el trato ya no está en sus
 *    pendientes.
 * 4. **Que los números de la cabecera sean los del servidor**, no los de las
 *    tarjetas visibles.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ColumnaPipeline, EtapaCrm, Pipeline, TratoCrm } from '@/lib/crm';
import { PipelineKanban } from './PipelineKanban';

const NUEVO: EtapaCrm = { id: 'e1', codigo: 'nuevo', nombre: 'Nuevo', posicion: 0, tipo: 'open' };
const GANADO: EtapaCrm = { id: 'e2', codigo: 'ganado', nombre: 'Ganado', posicion: 1, tipo: 'won' };
const PERDIDO: EtapaCrm = { id: 'e3', codigo: 'perdido', nombre: 'Perdido', posicion: 2, tipo: 'lost' };

function trato(over: Partial<TratoCrm> = {}): TratoCrm {
  return {
    id: 'd1',
    empresaId: 'c1',
    contactoId: null,
    etapaId: 'e1',
    titulo: 'Implantación Ambienta',
    monto: 1000,
    moneda: 'CLP',
    responsableId: null,
    cierreEstimado: '2026-09-01',
    cerradoEn: null,
    motivoPerdida: null,
    contratoId: null,
    ...over,
  };
}

function columna(etapa: EtapaCrm, over: Partial<ColumnaPipeline> = {}): ColumnaPipeline {
  return { etapa, tratos: [], totalTratos: 0, montos: [], ...over };
}

function pipeline(over: Partial<Pipeline> = {}): Pipeline {
  return {
    columnas: [
      columna(NUEVO, { tratos: [trato()], totalTratos: 1, montos: [{ moneda: 'CLP', total: 1000 }] }),
      columna(GANADO),
      columna(PERDIDO),
    ],
    truncado: false,
    ...over,
  };
}

const exito = () => vi.fn().mockResolvedValue({ ok: true, efectos: [] });

describe('mover sin arrastrar', () => {
  it('cada tarjeta ofrece un selector con las OTRAS etapas', () => {
    // Sin esto el tablero no se puede usar con dedo ni con teclado.
    render(<PipelineKanban pipeline={pipeline()} onMover={exito()} />);

    const selector = screen.getByLabelText(/Mover Implantación Ambienta a otra etapa/i);
    const opciones = within(selector).getAllByRole('option').map((o) => o.textContent);

    expect(opciones).toContain('Ganado');
    expect(opciones).toContain('Perdido');
    // La etapa donde ya está no se ofrece: mover algo a donde está es un no-op
    // que igual dispararía una petición.
    expect(opciones).not.toContain('Nuevo');
  });

  it('elegir una etapa abierta mueve el trato sin preguntar nada', async () => {
    const onMover = exito();
    render(<PipelineKanban pipeline={pipeline()} onMover={onMover} />);

    await userEvent.selectOptions(
      screen.getByLabelText(/Mover Implantación Ambienta a otra etapa/i),
      'e2',
    );

    expect(onMover).toHaveBeenCalledTimes(1);
    expect(onMover.mock.calls[0][1]).toMatchObject({ id: 'e2' });
  });
});

describe('perder exige motivo', () => {
  it('mover a Perdido NO manda nada hasta que se escribe la razón', async () => {
    const onMover = exito();
    render(<PipelineKanban pipeline={pipeline()} onMover={onMover} />);

    await userEvent.selectOptions(
      screen.getByLabelText(/Mover Implantación Ambienta a otra etapa/i),
      'e3',
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(onMover).not.toHaveBeenCalled();
  });

  it('el botón de confirmar está apagado mientras el motivo esté en blanco', async () => {
    render(<PipelineKanban pipeline={pipeline()} onMover={exito()} />);
    await userEvent.selectOptions(
      screen.getByLabelText(/Mover Implantación Ambienta a otra etapa/i),
      'e3',
    );

    expect(screen.getByRole('button', { name: /Marcar como perdido/i })).toBeDisabled();
  });

  it('con motivo escrito, la razón viaja al servidor', async () => {
    const onMover = exito();
    render(<PipelineKanban pipeline={pipeline()} onMover={onMover} />);
    await userEvent.selectOptions(
      screen.getByLabelText(/Mover Implantación Ambienta a otra etapa/i),
      'e3',
    );

    await userEvent.type(
      screen.getByLabelText(/Motivo de la pérdida/i),
      'eligieron a la competencia',
    );
    await userEvent.click(screen.getByRole('button', { name: /Marcar como perdido/i }));

    expect(onMover).toHaveBeenCalledTimes(1);
    expect(onMover.mock.calls[0][2]).toBe('eligieron a la competencia');
  });

  it('cancelar no mueve nada', async () => {
    const onMover = exito();
    render(<PipelineKanban pipeline={pipeline()} onMover={onMover} />);
    await userEvent.selectOptions(
      screen.getByLabelText(/Mover Implantación Ambienta a otra etapa/i),
      'e3',
    );
    await userEvent.click(screen.getByRole('button', { name: /Cancelar/i }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(onMover).not.toHaveBeenCalled();
  });
});

describe('se dice qué más pasó', () => {
  it('los efectos del movimiento se muestran, no ocurren en silencio', async () => {
    const onMover = vi
      .fn()
      .mockResolvedValue({ ok: true, efectos: ['El trato quedo cerrado'] });
    render(<PipelineKanban pipeline={pipeline()} onMover={onMover} />);

    await userEvent.selectOptions(
      screen.getByLabelText(/Mover Implantación Ambienta a otra etapa/i),
      'e2',
    );

    expect(await screen.findByText(/El trato quedo cerrado/)).toBeInTheDocument();
  });

  it('un rechazo del servidor se muestra tal cual lo explicó', async () => {
    const onMover = vi
      .fn()
      .mockResolvedValue({ ok: false, efectos: [], error: 'Perder un trato exige decir por que.' });
    render(<PipelineKanban pipeline={pipeline()} onMover={onMover} />);

    await userEvent.selectOptions(
      screen.getByLabelText(/Mover Implantación Ambienta a otra etapa/i),
      'e2',
    );

    expect(await screen.findByText(/exige decir por que/i)).toBeInTheDocument();
  });
});

describe('los números de la cabecera', () => {
  it('cuentan lo que hay en el servidor, no las tarjetas visibles', () => {
    // Con el tope del servidor, una columna puede traer 2 tarjetas de 40. Si
    // la cabecera contara lo visible, el tablero informaría 2.
    const p = pipeline({
      columnas: [
        columna(NUEVO, {
          tratos: [trato({ id: 'd1' }), trato({ id: 'd2' })],
          totalTratos: 40,
          montos: [{ moneda: 'CLP', total: 40000 }],
        }),
        columna(GANADO),
        columna(PERDIDO),
      ],
    });
    render(<PipelineKanban pipeline={p} onMover={exito()} />);

    const col = screen.getByRole('region', { name: /Nuevo, 40 oportunidades/i });
    expect(within(col).getByText('40')).toBeInTheDocument();
    expect(within(col).getByText(/38 más que no caben acá/)).toBeInTheDocument();
  });

  it('muestran las dos monedas por separado y nunca su suma', () => {
    const p = pipeline({
      columnas: [
        columna(NUEVO, {
          tratos: [trato()],
          totalTratos: 2,
          montos: [
            { moneda: 'CLP', total: 1000 },
            { moneda: 'USD', total: 7 },
          ],
        }),
      ],
    });
    render(<PipelineKanban pipeline={p} onMover={exito()} />);

    expect(screen.getByText(/CLP 1\.000 · USD 7,00/)).toBeInTheDocument();
    expect(screen.queryByText(/1\.007/)).not.toBeInTheDocument();
  });

  it('un trato sin cifra dice "Sin valorar", no "CLP 0"', () => {
    const p = pipeline({
      columnas: [columna(NUEVO, { tratos: [trato({ monto: null })], totalTratos: 1 })],
    });
    render(<PipelineKanban pipeline={p} onMover={exito()} />);

    expect(screen.getAllByText(/Sin valorar/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/CLP 0/)).not.toBeInTheDocument();
  });

  it('avisa cuando alguna columna vino cortada', () => {
    render(<PipelineKanban pipeline={pipeline({ truncado: true })} onMover={exito()} />);
    expect(screen.getByText(/más oportunidades de las que caben/i)).toBeInTheDocument();
  });

  it('sin truncar NO aparece el aviso, o estaría siempre', () => {
    render(<PipelineKanban pipeline={pipeline({ truncado: false })} onMover={exito()} />);
    expect(screen.queryByText(/más oportunidades de las que caben/i)).not.toBeInTheDocument();
  });
});

describe('la fecha de cierre', () => {
  it('no retrocede un día', () => {
    // `expected_close_date` es un `date`: pasarlo por `new Date` lo movería al
    // 31 de agosto en Chile.
    render(<PipelineKanban pipeline={pipeline()} onMover={exito()} />);
    expect(screen.getByText(/01 sep 2026/)).toBeInTheDocument();
  });
});
