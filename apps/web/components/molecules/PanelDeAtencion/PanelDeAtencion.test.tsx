/**
 * Los tres estados que se ven casi iguales, y sólo uno significa "todo bien".
 *
 * Este proyecto dibujó un cero sobre algo que nadie midió **cuatro veces**:
 * `normSemaforo(0)`, el tablero pintando en rojo las plantas sin evaluar, la
 * cobertura de auditoría y los reportes. En cada caso el número era correcto
 * como aritmética y falso como afirmación.
 *
 * Estas pruebas afirman sobre **texto visible**, no sobre props, por la lección
 * de `NormDetailView.test.tsx`: hubo una prueba que fijaba `toBe(0)` sin
 * preguntar qué significaba ese cero, y el error vivía entre dos `describe`
 * que estaban los dos en verde.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PanelDeAtencion } from './PanelDeAtencion';

const BASE = {
  titulo: 'Sin operador habilitado',
  explica: 'Equipos que hoy nadie puede operar legalmente',
  vacio: 'Todos los equipos tienen a alguien habilitado.',
};

describe('mientras no se sabe, no afirma nada', () => {
  it('con `null` dice que está comprobando, no que no hay nada', () => {
    render(<PanelDeAtencion {...BASE} filas={null} />);

    expect(screen.getByText('Comprobando…')).toBeInTheDocument();
    expect(screen.queryByText(BASE.vacio)).not.toBeInTheDocument();
  });

  it('con `undefined` hace lo mismo', () => {
    render(<PanelDeAtencion {...BASE} filas={undefined} />);

    expect(screen.getByText('Comprobando…')).toBeInTheDocument();
  });

  it('**no dibuja el contador** mientras no se sabe', () => {
    render(<PanelDeAtencion {...BASE} filas={null} />);

    // Un "0" junto al título es la afirmación más fuerte de la pantalla.
    // Ponerlo antes de tener la respuesta dice "no hay nada que atender" sin
    // haber mirado, que es la lectura más tranquilizadora y la más falsa.
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });
});

describe('si no se pudo preguntar, lo dice', () => {
  it('muestra el motivo y no el estado vacío', () => {
    render(
      <PanelDeAtencion {...BASE} filas={null} error="se cayó la consulta" />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('se cayó la consulta');
    expect(screen.queryByText(BASE.vacio)).not.toBeInTheDocument();
  });

  it('tampoco dibuja el contador con error', () => {
    render(<PanelDeAtencion {...BASE} filas={[]} error="500" />);

    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });
});

describe('cuando de verdad no hay nada, lo afirma', () => {
  it('muestra el mensaje de vacío y el cero', () => {
    render(<PanelDeAtencion {...BASE} filas={[]} />);

    expect(screen.getByText(BASE.vacio)).toBeInTheDocument();
    // Acá el cero **sí** es una afirmación con respaldo: se preguntó.
    expect(screen.getByText('0')).toBeInTheDocument();
    expect(screen.queryByText('Comprobando…')).not.toBeInTheDocument();
  });
});

describe('con filas, las muestra y las cuenta', () => {
  it('una fila por elemento', () => {
    render(
      <PanelDeAtencion
        {...BASE}
        filas={[<span key="a">Caldera de vapor</span>, <span key="b">Estanque diésel</span>]}
      />,
    );

    expect(screen.getByText('Caldera de vapor')).toBeInTheDocument();
    expect(screen.getByText('Estanque diésel')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });

  it('la nota de contexto sale sólo cuando hay respuesta', () => {
    const { rerender } = render(
      <PanelDeAtencion {...BASE} filas={null} nota="ventana de 30 días" />,
    );
    expect(screen.queryByText('ventana de 30 días')).not.toBeInTheDocument();

    rerender(<PanelDeAtencion {...BASE} filas={[]} nota="ventana de 30 días" />);
    expect(screen.getByText('ventana de 30 días')).toBeInTheDocument();
  });
});
