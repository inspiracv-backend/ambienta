import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FormularioIso } from './FormularioIso';
import type { CampoIso } from './IsoForms.types';

/**
 * El formulario comun de las pantallas ISO. Lo que se prueba aca es que **lo que
 * se ve sea lo que se valida**: el 21-sep la pantalla mostraba "Planta Calama"
 * elegida y al guardar respondia "Planta es obligatorio".
 */

const CAMPOS: CampoIso[] = [
  {
    nombre: 'facility_id',
    etiqueta: 'Planta',
    tipo: 'select',
    requerido: true,
    opciones: [
      { value: 'p1', label: 'Planta Calama' },
      { value: 'p2', label: 'Faena Antofagasta' },
    ],
  },
  { nombre: 'process_id', etiqueta: 'Proceso', tipo: 'select', opciones: [{ value: 'pr1', label: 'Chancado' }] },
];

function montar(onGuardar = vi.fn().mockResolvedValue(true)) {
  render(<FormularioIso open onOpenChange={vi.fn()} titulo="Nuevo" campos={CAMPOS} onGuardar={onGuardar} />);
  return onGuardar;
}

describe('un select obligatorio', () => {
  it('sin elegir no muestra ninguna opcion como elegida', () => {
    montar();

    const planta = screen.getByLabelText(/Planta/) as HTMLSelectElement;
    expect(planta.value).toBe('');
    expect(planta.selectedOptions[0].textContent).toBe('Elige una opción');
  });

  it('si no se elige, lo dice y no guarda', async () => {
    const onGuardar = montar();

    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(screen.getByText('Planta es obligatorio.')).toBeTruthy();
    expect(onGuardar).not.toHaveBeenCalled();
  });

  it('elegido, guarda lo que se ve', async () => {
    const onGuardar = montar();

    await userEvent.selectOptions(screen.getByLabelText(/Planta/), 'p1');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(onGuardar).toHaveBeenCalledWith({ facility_id: 'p1', process_id: null });
  });
});

it('un select opcional vacio viaja como null', async () => {
  const onGuardar = montar();

  await userEvent.selectOptions(screen.getByLabelText(/Planta/), 'p2');
  await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));

  expect(onGuardar.mock.calls[0][0].process_id).toBeNull();
});
