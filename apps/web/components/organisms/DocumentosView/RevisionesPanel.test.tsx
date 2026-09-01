/**
 * Lo que se VE en el panel de revisiones.
 *
 * Afirma sobre texto visible y no sobre funciones, por la lección de
 * `NormDetailView.test.tsx`: allá había una prueba que fijaba `toBe(0)` sin
 * preguntar qué significaba ese cero, y la que traducía el cero a "No cumple"
 * estaba en otro `describe`. Las dos en verde y el error entre las dos.
 *
 * La pregunta que esta pantalla tiene que contestar de un vistazo es **cuál
 * revisión sirve como evidencia**, y eso sólo se comprueba mirando lo que
 * queda escrito.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Documento, RevisionDocumental } from '@ambienta/shared';
import { RevisionesPanel } from './RevisionesPanel';

const subir = vi.fn();
const mover = vi.fn();
const descargar = vi.fn();

vi.mock('@/lib/documentos-store', () => ({
  useDocumentos: () => ({
    subir,
    mover,
    descargar,
    subiendo: null,
  }),
}));

const DOCUMENTO: Documento = {
  id: 'doc-1',
  tenantId: 't-1',
  codigo: 'PR-07',
  titulo: 'Manejo de residuos peligrosos',
  tipo: 'procedimiento',
  estado: 'vigente',
  clasificacion: 'internal',
  etiquetas: [],
  revisionVigenteId: 'rev-2',
  creadoEn: '2026-08-01T12:00:00Z',
  actualizadoEn: '2026-08-20T12:00:00Z',
};

function revision(over: Partial<RevisionDocumental> = {}): RevisionDocumental {
  return {
    id: 'rev-1',
    documentoId: 'doc-1',
    numero: 1,
    estado: 'borrador',
    nombreArchivo: 'manual.pdf',
    tipoMime: 'application/pdf',
    tamanoBytes: 2048,
    proveedor: 'backblaze',
    creadaEn: '2026-08-01T12:00:00Z',
    aprobadaPor: null,
    aprobadaEn: null,
    rigeDesde: null,
    rigeHasta: null,
    obsoletaEn: null,
    motivoObsolescencia: null,
    ...over,
  };
}

describe('cuál sirve como evidencia', () => {
  it('la vigente lo dice con todas sus letras', () => {
    render(
      <RevisionesPanel
        documento={DOCUMENTO}
        revisiones={[revision({ estado: 'vigente', rigeDesde: '2026-08-11' })]}
        cargando={false}
      />,
    );

    expect(screen.getByText(/sirve como evidencia/i)).toBeInTheDocument();
  });

  it('la APROBADA no lo dice', () => {
    // Aprobada pero sin entrar en vigencia significa que todavía rige la
    // anterior. Si esto dijera que sirve, alguien le mostraría a un
    // fiscalizador el documento equivocado.
    render(
      <RevisionesPanel
        documento={DOCUMENTO}
        revisiones={[revision({ estado: 'aprobado', aprobadaEn: '2026-08-10T00:00:00Z' })]}
        cargando={false}
      />,
    );

    expect(screen.queryByText(/sirve como evidencia/i)).not.toBeInTheDocument();
    expect(screen.getByText('Aprobada')).toBeInTheDocument();
  });

  it('el borrador tampoco', () => {
    render(
      <RevisionesPanel documento={DOCUMENTO} revisiones={[revision()]} cargando={false} />,
    );
    expect(screen.queryByText(/sirve como evidencia/i)).not.toBeInTheDocument();
  });
});

describe('las acciones que se ofrecen', () => {
  it('un borrador puede enviarse a revisión, no aprobarse', () => {
    render(
      <RevisionesPanel documento={DOCUMENTO} revisiones={[revision()]} cargando={false} />,
    );

    expect(screen.getByRole('button', { name: /enviar a revisión/i })).toBeInTheDocument();
    // Saltarse la revisión no es una transición que exista.
    expect(screen.queryByRole('button', { name: /^aprobar$/i })).not.toBeInTheDocument();
  });

  it('una en revisión puede aprobarse Y devolverse a borrador', () => {
    render(
      <RevisionesPanel
        documento={DOCUMENTO}
        revisiones={[revision({ estado: 'en_revision' })]}
        cargando={false}
      />,
    );

    expect(screen.getByRole('button', { name: /aprobar/i })).toBeInTheDocument();
    // La salida que faltaba: sin ella, revisar algo incompleto obliga a
    // aprobarlo igual o a marcarlo obsoleto.
    expect(screen.getByRole('button', { name: /devolver a borrador/i })).toBeInTheDocument();
  });

  it('una obsoleta no ofrece NINGUNA transición', () => {
    render(
      <RevisionesPanel
        documento={DOCUMENTO}
        revisiones={[
          revision({ estado: 'obsoleto', motivoObsolescencia: 'cambió la normativa' }),
        ]}
        cargando={false}
      />,
    );

    for (const nombre of [/enviar a revisión/i, /aprobar/i, /poner en vigencia/i]) {
      expect(screen.queryByRole('button', { name: nombre })).not.toBeInTheDocument();
    }
    // Descargar sí: se conserva a propósito (RF-106).
    expect(screen.getByRole('button', { name: /descargar/i })).toBeInTheDocument();
  });

  it('un tipo NO controlado no ofrece ciclo de vida', () => {
    render(
      <RevisionesPanel
        documento={{ ...DOCUMENTO, tipo: 'receipt' }}
        revisiones={[revision()]}
        cargando={false}
      />,
    );

    expect(screen.queryByRole('button', { name: /enviar a revisión/i })).not.toBeInTheDocument();
    expect(screen.getByText(/no lleva ciclo de vida/i)).toBeInTheDocument();
  });
});

describe('el formulario de retiro', () => {
  it('el botón de confirmar NO se llama igual que el que abre el formulario', async () => {
    /**
     * Dos botones con el mismo nombre en la misma fila suenan idénticos en un
     * lector de pantalla, y `getByRole('button', {name})` tampoco los
     * distingue. Se vio manejando la pantalla, no leyendo el código.
     */
    const usuario = userEvent.setup();
    render(
      <RevisionesPanel
        documento={DOCUMENTO}
        revisiones={[revision({ estado: 'vigente' })]}
        cargando={false}
      />,
    );

    await usuario.click(screen.getByRole('button', { name: /marcar obsoleta/i }));

    expect(screen.getByText(/por qué deja de regir/i)).toBeInTheDocument();
    // Si vuelve a haber dos, esto falla con "found multiple elements".
    expect(screen.getByRole('button', { name: /marcar obsoleta/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /confirmar retiro/i })).toBeInTheDocument();
  });

  it('no se puede confirmar sin escribir el motivo', async () => {
    const usuario = userEvent.setup();
    render(
      <RevisionesPanel
        documento={DOCUMENTO}
        revisiones={[revision({ estado: 'vigente' })]}
        cargando={false}
      />,
    );

    await usuario.click(screen.getByRole('button', { name: /marcar obsoleta/i }));

    // Un obsoleto sin explicación obliga a quien lo encuentre a adivinar si
    // todavía sirve, y en la duda se usa.
    expect(screen.getByRole('button', { name: /confirmar retiro/i })).toBeDisabled();

    await usuario.type(screen.getByLabelText(/por qué deja de regir/i), 'cambió la norma');
    expect(screen.getByRole('button', { name: /confirmar retiro/i })).toBeEnabled();
  });
});

describe('lo que queda escrito de una revisión retirada', () => {
  it('se muestra el motivo', () => {
    // Un obsoleto sin explicación obliga a quien lo encuentre a adivinar si
    // todavía sirve, y en la duda se usa.
    render(
      <RevisionesPanel
        documento={DOCUMENTO}
        revisiones={[
          revision({ estado: 'obsoleto', motivoObsolescencia: 'cambió la normativa aplicable' }),
        ]}
        cargando={false}
      />,
    );

    expect(screen.getByText(/cambió la normativa aplicable/i)).toBeInTheDocument();
  });
});

describe('el estado vacío', () => {
  it('dice qué hacer y advierte que un borrador no sirve como evidencia', () => {
    render(<RevisionesPanel documento={DOCUMENTO} revisiones={[]} cargando={false} />);

    expect(screen.getByText(/no tiene archivos todavía/i)).toBeInTheDocument();
    expect(screen.getByText(/no sirve como evidencia hasta que esté vigente/i)).toBeInTheDocument();
  });
});

describe('la identidad del documento', () => {
  it('el código se muestra, porque es lo que se cita en una auditoría', () => {
    render(
      <RevisionesPanel documento={DOCUMENTO} revisiones={[revision()]} cargando={false} />,
    );
    expect(screen.getByText('PR-07')).toBeInTheDocument();
  });

  it('sin código lo dice en vez de dejar un hueco', () => {
    render(
      <RevisionesPanel
        documento={{ ...DOCUMENTO, codigo: null }}
        revisiones={[revision()]}
        cargando={false}
      />,
    );
    expect(screen.getByText(/sin código asignado/i)).toBeInTheDocument();
  });
});
