/**
 * Que la pantalla de reportes ofrezca **PDF por defecto** (RF-50).
 *
 * Hasta ahora exportaba solo CSV y avisaba que *"la generación de PDF queda
 * pendiente de una librería aprobada"*. **Esa frase ya era falsa**: el informe
 * imprimible existía y producía un PDF de verdad con el motor del navegador.
 * Lo que faltaba era que el selector lo ofreciera.
 *
 * Las afirmaciones son sobre **lo que ve la persona**: qué opción viene
 * marcada, qué dice el botón, y qué archivo se descarga.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { LegalNorm, NonConformity, Obligation, Plant, Tenant, User } from '@ambienta/shared';
import { ReportGenerator } from './ReportGenerator';

const descargar = vi.fn();
vi.mock('@/lib/reports', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/reports')>();
  return { ...real, downloadTextFile: (...a: unknown[]) => descargar(...a) };
});
vi.mock('@/lib/audit-log-store', () => ({ useRegistrarAuditoria: () => vi.fn() }));

const TENANT = {
  id: 't-1',
  nombre: 'Minera Andes SpA',
  pais: 'CL',
  // El encabezado del documento la imprime: un informe sin la identificacion
  // de la empresa no le sirve a nadie ante un fiscalizador.
  identificacion: { tipo: 'RUT', numero: '76.543.210-K' },
} as Tenant;
const USUARIO = { id: 'u-1', nombre: 'Fabrizzio Gomez' } as User;
const PLANTA = { id: 'p1', tenantId: 't-1', nombre: 'Planta Norte' } as Plant;

const NORMA = {
  id: 'n1',
  tenantId: 't-1',
  nombre: 'DS 1/2013 RETC',
  fuente: 'BCN',
  plantIds: ['p1'],
  articulos: [
    { id: 'a1', numero: 'Art. 1', descripcion: 'T', respuesta: 'SI', incluidoEnCalculo: true },
  ],
} as LegalNorm;

const OBLIGACION = {
  id: 'o1',
  tenantId: 't-1',
  plantId: 'p1',
  nombre: 'Declaración',
  estado: 'vigente',
  proximoVencimiento: '2026-06-15T00:00:00.000Z',
} as Obligation;

function pintar(props: Partial<React.ComponentProps<typeof ReportGenerator>> = {}) {
  return render(
    <ReportGenerator
      plants={[PLANTA]}
      obligations={[OBLIGACION]}
      norms={[NORMA]}
      nonConformities={[] as NonConformity[]}
      tenant={TENANT}
      usuario={USUARIO}
      {...props}
    />,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  window.print = vi.fn();
});

describe('el formato por defecto', () => {
  it('viene PDF marcado, no CSV', () => {
    pintar();

    expect(screen.getByRole('button', { name: /PDF/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /CSV/ })).toHaveAttribute('aria-pressed', 'false');
  });

  it('el botón principal dice que genera un documento', () => {
    pintar();

    expect(screen.getByRole('button', { name: /Generar documento/ })).toBeInTheDocument();
  });

  it('ya no dice que el PDF esté pendiente de una librería', () => {
    // La frase era falsa y desalentaba usar lo que sí funcionaba.
    pintar();

    expect(screen.queryByText(/pendiente de una librer/i)).not.toBeInTheDocument();
  });

  it('generar con el defecto NO descarga una planilla', () => {
    pintar();

    screen.getByRole('button', { name: /Generar documento/ }).click();

    expect(descargar).not.toHaveBeenCalled();
  });
});

describe('el CSV sigue estando a un clic', () => {
  it('cambiar a CSV y generar descarga el archivo', async () => {
    // Cambiar el defecto no puede ser quitar la opción: quien procesa los datos
    // en otra herramienta la necesita igual.
    pintar();

    await userEvent.click(screen.getByRole('button', { name: /CSV/ }));
    await userEvent.click(screen.getByRole('button', { name: /Exportar planilla/ }));

    expect(descargar).toHaveBeenCalledOnce();
    expect(descargar.mock.calls[0]![0]).toMatch(/\.csv$/);
  });
});

describe('el documento', () => {
  it('se muestra antes de imprimir, para poder revisarlo', async () => {
    // El diálogo del navegador tapa la pantalla: disparar `print()` de una no
    // deja mirar lo que se va a entregar.
    pintar();

    await userEvent.click(screen.getByRole('button', { name: /Generar documento/ }));

    expect(window.print).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /Imprimir . Guardar PDF/ })).toBeInTheDocument();
  });

  it('lleva el nombre de la empresa auditada', async () => {
    // Un informe sin la marca de la empresa no parece un documento suyo ante un
    // fiscalizador.
    pintar();

    await userEvent.click(screen.getByRole('button', { name: /Generar documento/ }));

    expect(screen.getAllByText(/Minera Andes SpA/).length).toBeGreaterThan(0);
  });

  it('imprime recién al pedirlo', async () => {
    pintar();

    await userEvent.click(screen.getByRole('button', { name: /Generar documento/ }));
    await userEvent.click(screen.getByRole('button', { name: /Imprimir . Guardar PDF/ }));

    expect(window.print).toHaveBeenCalledOnce();
  });

  it('sin empresa cargada el PDF queda deshabilitado', () => {
    // **No se emite un documento sin identificación.** Los stores cargan async
    // y la pantalla se pinta antes; emitir igual daría un informe que no sirve.
    pintar({ tenant: undefined, usuario: undefined });

    expect(screen.getByRole('button', { name: /PDF/ })).toBeDisabled();
  });

  it('cambiar de tipo descarta el documento ya generado', async () => {
    // Si no, quedaría en pantalla un documento de Cumplimiento mientras el
    // selector dice "Matriz Legal", y se imprime el que no era.
    pintar();
    await userEvent.click(screen.getByRole('button', { name: /Generar documento/ }));

    await userEvent.selectOptions(screen.getByLabelText(/Tipo de reporte/), 'matriz-legal');

    expect(screen.queryByRole('button', { name: /Imprimir . Guardar PDF/ })).not.toBeInTheDocument();
  });
});
