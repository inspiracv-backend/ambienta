import { describe, expect, it, vi } from 'vitest';
import type { Audit, LegalNorm, NonConformity, Obligation, Plant } from '@ambienta/shared';
import {
  buildAuditFolderContent,
  buildCumplimientoReport,
  buildMatrizLegalReport,
  buildNoConformidadesReport,
  downloadTextFile,
} from './reports';

/**
 * Los reportes son el entregable que sale del sistema hacia una auditoría
 * externa (RF-57, RNF-26). Dos cosas se prueban aquí con especial cuidado:
 * el escapado CSV — un hallazgo con una coma no debe correr las columnas y
 * falsear el reporte — y que el filtro por rango de fechas incluya el día
 * "hasta" completo.
 */

function planta(id: string, nombre: string): Plant {
  return { id, tenantId: 'tenant-1', nombre, comuna: 'C', region: 'R' } as Plant;
}

function obligacion(over: Partial<Obligation> & { id: string; plantId: string }): Obligation {
  return {
    tenantId: 'tenant-1',
    nombre: 'Obligación',
    estado: 'vigente',
    proximoVencimiento: '2026-06-15T00:00:00.000Z',
    ...over,
  } as Obligation;
}

function nc(over: Partial<NonConformity> & { id: string }): NonConformity {
  return {
    tenantId: 'tenant-1',
    plantId: 'p1',
    hallazgo: 'Hallazgo',
    criticidad: 'media',
    estado: 'abierta',
    fechaDeteccion: '2026-06-15T00:00:00.000Z',
    cierre: null,
    auditId: null,
    ...over,
  } as NonConformity;
}

function filas(csv: string): string[] {
  return csv.split('\n');
}

describe('escapado CSV', () => {
  it('entrecomilla los valores que contienen comas', () => {
    // Sin esto, "Derrame, sin contención" se partiría en dos columnas y el
    // reporte mostraría datos corridos.
    const { csv } = buildNoConformidadesReport(
      [planta('p1', 'Planta Uno')],
      [nc({ id: 'n1', hallazgo: 'Derrame, sin contención' })],
      '',
      '',
    );
    expect(csv).toContain('"Derrame, sin contención"');
  });

  it('duplica las comillas internas', () => {
    const { csv } = buildNoConformidadesReport(
      [planta('p1', 'Planta Uno')],
      [nc({ id: 'n1', hallazgo: 'Sector "A" sin señalética' })],
      '',
      '',
    );
    expect(csv).toContain('"Sector ""A"" sin señalética"');
  });

  it('entrecomilla los valores con salto de línea', () => {
    const { csv } = buildNoConformidadesReport(
      [planta('p1', 'Planta Uno')],
      [nc({ id: 'n1', hallazgo: 'Primera línea\nSegunda línea' })],
      '',
      '',
    );
    expect(csv).toContain('"Primera línea\nSegunda línea"');
  });

  it('deja sin comillas los valores simples', () => {
    const { csv } = buildNoConformidadesReport(
      [planta('p1', 'Planta Uno')],
      [nc({ id: 'n1', hallazgo: 'Sin señalética' })],
      '',
      '',
    );
    expect(csv).toContain('Sin señalética');
    expect(csv).not.toContain('"Sin señalética"');
  });
});

describe('buildNoConformidadesReport — filtro por rango', () => {
  const plants = [planta('p1', 'Planta Uno')];
  const items = [
    nc({ id: 'antes', fechaDeteccion: '2026-05-31T00:00:00.000Z' }),
    nc({ id: 'dentro', fechaDeteccion: '2026-06-15T00:00:00.000Z' }),
    nc({ id: 'ultimoDia', fechaDeteccion: '2026-06-30T18:00:00.000Z' }),
    nc({ id: 'despues', fechaDeteccion: '2026-07-01T12:00:00.000Z' }),
  ];

  it('incluye el día "hasta" completo, no solo hasta su medianoche', () => {
    const { csv } = buildNoConformidadesReport(plants, items, '2026-06-01', '2026-06-30');
    // 1 encabezado + 2 filas (dentro y ultimoDia).
    expect(filas(csv)).toHaveLength(3);
  });

  it('excluye lo que cae fuera del rango', () => {
    const { csv } = buildNoConformidadesReport(plants, items, '2026-06-01', '2026-06-30');
    expect(csv).not.toContain('antes');
    expect(csv).not.toContain('despues');
  });

  it('sin rango devuelve todo', () => {
    const { csv, empty } = buildNoConformidadesReport(plants, items, '', '');
    expect(filas(csv)).toHaveLength(items.length + 1);
    expect(empty).toBe(false);
  });

  it('marca empty cuando el rango no atrapa nada', () => {
    const { empty } = buildNoConformidadesReport(plants, items, '2027-01-01', '2027-12-31');
    expect(empty).toBe(true);
  });

  it('cae al id de planta cuando la planta ya no existe', () => {
    const { csv } = buildNoConformidadesReport([], [nc({ id: 'n1', plantId: 'p-borrada' })], '', '');
    expect(csv).toContain('p-borrada');
  });
});

describe('buildCumplimientoReport', () => {
  it('emite una fila por planta más el encabezado', () => {
    const { csv } = buildCumplimientoReport(
      [planta('p1', 'Planta Uno'), planta('p2', 'Planta Dos')],
      [],
      [],
      '',
      '',
    );
    expect(filas(csv)).toHaveLength(3);
  });

  it('calcula el % de obligaciones vigentes por planta', () => {
    const { csv } = buildCumplimientoReport(
      [planta('p1', 'Planta Uno')],
      [
        obligacion({ id: 'o1', plantId: 'p1', estado: 'vigente' }),
        obligacion({ id: 'o2', plantId: 'p1', estado: 'vigente' }),
        obligacion({ id: 'o3', plantId: 'p1', estado: 'vencida' }),
        obligacion({ id: 'o4', plantId: 'p1', estado: 'vencida' }),
      ],
      [],
      '',
      '',
    );
    expect(csv).toContain('50%');
    // Dos incumplimientos (vencidas).
    expect(filas(csv)[1]).toMatch(/,2$/);
  });

  it('promedia el cumplimiento de las normas asignadas a la planta', () => {
    const norma = (id: string, respuestas: Array<'SI' | 'NO'>): LegalNorm =>
      ({
        id,
        plantIds: ['p1'],
        articulos: respuestas.map((r, i) => ({
          id: `${id}-${i}`,
          respuesta: r,
          incluidoEnCalculo: true,
        })),
      }) as LegalNorm;

    const { csv } = buildCumplimientoReport(
      [planta('p1', 'Planta Uno')],
      [],
      [norma('n1', ['SI', 'SI']), norma('n2', ['SI', 'NO'])],
      '',
      '',
    );
    // (100% + 50%) / 2 = 75%
    expect(csv).toContain('75%');
  });
});

describe('buildMatrizLegalReport', () => {
  it('resuelve los nombres de las plantas asignadas', () => {
    const norma = { id: 'n1', nombre: 'DS 148', fuente: 'BCN', plantIds: ['p1', 'p2'], articulos: [] } as unknown as LegalNorm;
    const { csv } = buildMatrizLegalReport([norma], [planta('p1', 'Planta Uno'), planta('p2', 'Planta Dos')]);
    expect(csv).toContain('Planta Uno / Planta Dos');
  });

  it('indica "Sin asignar" cuando la norma no tiene plantas', () => {
    const norma = { id: 'n1', nombre: 'DS 148', fuente: 'BCN', plantIds: [], articulos: [] } as unknown as LegalNorm;
    const { csv } = buildMatrizLegalReport([norma], []);
    expect(csv).toContain('Sin asignar');
  });

  it('marca empty sin normas', () => {
    expect(buildMatrizLegalReport([], []).empty).toBe(true);
  });
});

describe('buildAuditFolderContent', () => {
  const audit = {
    id: 'a1',
    plantId: 'p1',
    tipo: 'interna',
    fecha: '2026-06-15T00:00:00.000Z',
    estado: 'cerrada',
    procesos: ['Residuos', 'Riles'],
    normativaIds: ['DS-148'],
  } as unknown as Audit;

  it('incluye la cabecera con planta, tipo y procesos', () => {
    const texto = buildAuditFolderContent(audit, planta('p1', 'Planta Uno'), []);
    expect(texto).toContain('Planta Uno');
    expect(texto).toContain('Interna');
    expect(texto).toContain('Residuos, Riles');
  });

  it('solo incluye las no conformidades de esa auditoría', () => {
    const texto = buildAuditFolderContent(audit, planta('p1', 'Planta Uno'), [
      nc({ id: 'propia', hallazgo: 'Hallazgo propio', auditId: 'a1' }),
      nc({ id: 'ajena', hallazgo: 'Hallazgo de otra auditoría', auditId: 'a2' }),
    ]);
    expect(texto).toContain('Hallazgo propio');
    expect(texto).not.toContain('Hallazgo de otra auditoría');
    expect(texto).toContain('NO CONFORMIDADES ASOCIADAS (1)');
  });

  it('dice explícitamente cuando no hay hallazgos, en vez de dejar la sección vacía', () => {
    const texto = buildAuditFolderContent(audit, planta('p1', 'Planta Uno'), []);
    expect(texto).toContain('Sin no conformidades registradas');
  });

  it('no rompe si la planta ya no existe', () => {
    const texto = buildAuditFolderContent(audit, undefined, []);
    expect(texto).toContain('p1');
  });
});

describe('downloadTextFile', () => {
  it('crea un enlace con el nombre pedido y limpia el object URL', () => {
    const createObjectURL = vi.fn(() => 'blob:fake');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    downloadTextFile('reporte.csv', 'a,b', 'text/csv');

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    // Sin revoke se filtra memoria en cada exportación.
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:fake');
    // Y no debe dejar el <a> colgando en el DOM.
    expect(document.querySelectorAll('a[download]')).toHaveLength(0);

    vi.unstubAllGlobals();
    click.mockRestore();
  });
});

/**
 * Que el documento entregable no acuse a la empresa de algo que no pasó (#205).
 *
 * **El informe imprimía `0%` sobre normas que nadie había evaluado.** Con el
 * catálogo sembrado apenas se veía; con el articulado real de la BCN, cada
 * norma importada entra con sus artículos en `N_E` y el reporte la declaraba
 * incumplida — en el archivo que se le entrega a un fiscalizador.
 *
 * La causa es la misma que ya se corrigió en la pantalla: `computeNormCompliance`
 * devuelve `0` tanto para "todo evaluado y todo NO" como para "nada evaluado".
 * Estas pruebas afirman sobre **el texto que sale en el archivo**.
 */
function articulo(over: Partial<import('@ambienta/shared').Articulo> = {}) {
  return {
    id: 'a1',
    numero: 'Art. 1',
    descripcion: 'Texto',
    respuesta: 'N_E',
    incluidoEnCalculo: true,
    ...over,
  } as import('@ambienta/shared').Articulo;
}

function norma(over: Partial<LegalNorm> = {}): LegalNorm {
  return {
    id: 'n1',
    tenantId: 'tenant-1',
    nombre: 'DS 1/2013 RETC',
    fuente: 'BCN',
    plantIds: ['p1'],
    articulos: [],
    ...over,
  } as LegalNorm;
}

describe('sin evaluar no se imprime como 0%', () => {
  it('la matriz legal dice "Sin evaluar", no 0%', () => {
    const r = buildMatrizLegalReport([norma({ articulos: [articulo(), articulo({ id: 'a2' })] })], [
      planta('p1', 'Planta Norte'),
    ]);

    expect(r.rows[0]).toContain('Sin evaluar');
    expect(r.rows[0]).not.toContain('0%');
  });

  it('un cero medido SÍ se imprime como 0%', () => {
    // El otro lado: arreglar el falso positivo no puede tapar el incumplimiento
    // real. Todo evaluado y todo NO es un 0 % que corresponde.
    const r = buildMatrizLegalReport(
      [norma({ articulos: [articulo({ respuesta: 'NO' }), articulo({ id: 'a2', respuesta: 'NO' })] })],
      [planta('p1', 'Planta Norte')],
    );

    expect(r.rows[0]).toContain('0%');
  });

  it('dice cuántos artículos faltan por evaluar', () => {
    // Sin esta columna, "Sin evaluar" no dice cuánto falta, y un 100 % sobre un
    // artículo de doscientos se lee igual que uno sobre los doscientos.
    const r = buildMatrizLegalReport(
      [norma({ articulos: [articulo({ respuesta: 'SI' }), articulo({ id: 'a2' }), articulo({ id: 'a3' })] })],
      [planta('p1', 'Planta Norte')],
    );

    expect(r.headers).toContain('Artículos sin evaluar');
    expect(r.rows[0]![r.headers.indexOf('Artículos sin evaluar')]).toBe('2');
  });

  it('el promedio por planta ignora las normas sin evaluar', () => {
    // **El error que más engañaba.** Una planta con dos normas, una al 100 % y
    // otra sin evaluar, salía en 50 % — como si incumpliera la mitad.
    const r = buildCumplimientoReport(
      [planta('p1', 'Planta Norte')],
      [obligacion({ id: 'o1', plantId: 'p1' })],
      [
        norma({ id: 'n1', articulos: [articulo({ respuesta: 'SI' })] }),
        norma({ id: 'n2', articulos: [articulo({ id: 'a9' })] }),
      ],
      '',
      '',
    );

    expect(r.rows[0]![1]).toBe('100%');
  });

  it('y avisa al pie que el promedio dejó normas fuera', () => {
    const r = buildCumplimientoReport(
      [planta('p1', 'Planta Norte')],
      [obligacion({ id: 'o1', plantId: 'p1' })],
      [
        norma({ id: 'n1', articulos: [articulo({ respuesta: 'SI' })] }),
        norma({ id: 'n2', articulos: [articulo({ id: 'a9' })] }),
      ],
      '',
      '',
    );

    expect(r.notas.join(' ')).toMatch(/no cuentan como incumplidas/i);
  });

  it('una planta con todas sus normas sin evaluar tampoco marca 0%', () => {
    const r = buildCumplimientoReport(
      [planta('p1', 'Planta Norte')],
      [obligacion({ id: 'o1', plantId: 'p1' })],
      [norma({ id: 'n1', articulos: [articulo()] })],
      '',
      '',
    );

    expect(r.rows[0]![1]).toBe('Sin evaluar');
  });
});

describe('los dos formatos salen del mismo reporte', () => {
  it('el CSV se deriva de las mismas filas que ve el PDF', () => {
    // **La propiedad que impide que diverjan.** Si el CSV y el documento se
    // construyeran por separado, agregar una columna a uno dejaría al otro
    // diciendo otra cosa sobre la misma empresa — y nadie compara los dos
    // archivos hasta que lo hace alguien de afuera.
    const r = buildMatrizLegalReport([norma({ articulos: [articulo({ respuesta: 'SI' })] })], [
      planta('p1', 'Planta Norte'),
    ]);

    const lineas = filas(r.csv);
    expect(lineas[0]).toBe(r.headers.join(','));
    expect(lineas).toHaveLength(r.rows.length + 1);
    for (const celda of r.rows[0]!) {
      expect(lineas[1]).toContain(celda.includes(',') ? `"${celda}"` : celda);
    }
  });

  it('cada reporte lleva su propio título para el documento', () => {
    expect(buildMatrizLegalReport([], []).titulo).toMatch(/Matriz Legal/);
    expect(buildNoConformidadesReport([], [], '', '').titulo).toMatch(/No Conformidades/);
    expect(buildCumplimientoReport([], [], [], '', '').titulo).toMatch(/Cumplimiento/);
  });
});
