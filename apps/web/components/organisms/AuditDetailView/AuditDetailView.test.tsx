import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { Audit, NonConformity } from '@ambienta/shared';
import { AuditDetailView } from './AuditDetailView';

/**
 * Lo que la ficha de una auditoría afirma sobre sus hallazgos y normativas.
 * Antes decía «Sin hallazgos registrados todavía» siempre —filtraba por un campo
 * que la API no trae— y sacaba las normativas de `mocks/`.
 */

const AUDIT: Audit = {
  id: 'aud-1', tenantId: 't-1', plantId: 'p-1', tipo: 'interna', fecha: '2026-09-01',
  estado: 'en_curso', procesos: ['Gestión de residuos'], normativaIds: [],
};

const NC = {
  id: 'nc-1', tenantId: 't-1', plantId: 'p-1', hallazgo: 'Derrame sin contención', criticidad: 'media',
  estado: 'abierta', fechaDeteccion: '2026-09-02', responsableId: 'u-1', cincoPorques: [], auditItemId: 'item-1',
} as NonConformity;

describe('hallazgos', () => {
  it('mientras carga no dice que no hay', () => {
    render(<AuditDetailView audit={AUDIT} plant={undefined} normativas={null} hallazgos={null} />);
    expect(screen.getByText('Cargando hallazgos…')).toBeInTheDocument();
    expect(screen.queryByText(/Sin hallazgos registrados/)).not.toBeInTheDocument();
  });

  it('si no se pudo preguntar, lo dice', () => {
    render(<AuditDetailView audit={AUDIT} plant={undefined} normativas={null} hallazgos={null} errorHallazgos="sin conexión" />);
    expect(screen.getByText(/No se pudieron cargar los hallazgos/)).toBeInTheDocument();
  });

  it('muestra los que tiene', () => {
    render(<AuditDetailView audit={AUDIT} plant={undefined} normativas={null} hallazgos={[NC]} />);
    expect(screen.getByText('Derrame sin contención')).toBeInTheDocument();
  });
});

describe('normativas', () => {
  it('sin saber cuáles son, no se afirma «Sin normativas vinculadas»', () => {
    render(<AuditDetailView audit={AUDIT} plant={undefined} normativas={null} hallazgos={[]} />);
    expect(screen.queryByText('Normativas asociadas')).not.toBeInTheDocument();
    expect(screen.queryByText(/Sin normativas vinculadas/)).not.toBeInTheDocument();
  });
});
