import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { LegalNorm } from '@ambienta/shared';
import { ComplianceConfigModal } from './ComplianceConfigModal';

const setIncluidoEnCalculo = vi.fn();
vi.mock('@/lib/legal-matrix-store', () => ({ useLegalMatrix: () => ({ setIncluidoEnCalculo }) }));

const articulos = Array.from({ length: 5 }, (_, i) => ({
  id: `a-${i}`,
  normId: 'n-1',
  numero: `Articulo ${i + 1}`,
  descripcion: `Texto ${i + 1}`,
  respuesta: 'N_E',
  incluidoEnCalculo: true,
})) as LegalNorm['articulos'];

const norma = { id: 'n-1', tenantId: 't', plantIds: [], tipoDocumento: 'Ley', nombre: 'Ley 19.300', fuente: 'BCN', articulos } as LegalNorm;

describe('guardar la configuracion del calculo', () => {
  it('escribe solo el articulo que cambio, no todos los de la norma', async () => {
    // Hasta el 21-sep, desmarcar uno de los 151 articulos de la Ley 19.300
    // mandaba 151 escrituras: 150 evaluaciones nuevas que nadie toco.
    render(<ComplianceConfigModal norm={norma} open onOpenChange={() => {}} />);

    await userEvent.click(screen.getAllByRole('checkbox')[0]!);
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(setIncluidoEnCalculo).toHaveBeenCalledTimes(1);
    expect(setIncluidoEnCalculo).toHaveBeenCalledWith('n-1', 'a-0', false);
  });
});
