import { describe, expect, it } from 'vitest';
import {
  formatearFecha,
  formatearMonto,
  mapPipeline,
  necesitaMotivo,
  resumenDeColumna,
  type ColumnaPipeline,
  type EtapaCrm,
} from '@/lib/crm';

function etapa(over: Partial<EtapaCrm> = {}): EtapaCrm {
  return { id: 'e1', codigo: 'nuevo', nombre: 'Nuevo', posicion: 0, tipo: 'open', ...over };
}

function columna(over: Partial<ColumnaPipeline> = {}): ColumnaPipeline {
  return { etapa: etapa(), tratos: [], totalTratos: 0, montos: [], ...over };
}

describe('formatearFecha', () => {
  it('NO retrocede un dia con una fecha de calendario', () => {
    // La trampa que ya costo tiempo en este repositorio: `expected_close_date`
    // es un `date` de Postgres, y `new Date('2026-09-01')` lo lee como
    // medianoche UTC. En Chile (UTC-3/-4) eso se muestra como el 31 de agosto:
    // la fecha retrocede un dia sola, y en un cierre de trato eso lo cambia de
    // mes — y de trimestre cuando cae en un limite.
    expect(formatearFecha('2026-09-01')).toContain('01');
    expect(formatearFecha('2026-09-01')).toContain('sep');
    expect(formatearFecha('2026-01-01')).toContain('2026');
  });

  it('el 1 de enero no se va al ano anterior', () => {
    const r = formatearFecha('2026-01-01');
    expect(r).toBe('01 ene 2026');
    expect(r).not.toContain('2025');
  });

  it('una marca de tiempo SI se convierte a hora local', () => {
    // `closed_at` es un timestamp: ahi convertir es lo correcto, y por eso el
    // formateo distingue las dos formas en vez de tratar todo igual.
    expect(formatearFecha('2026-09-01T12:00:00Z')).toMatch(/\d/);
  });

  it('sin fecha lo dice, no muestra "Invalid Date"', () => {
    expect(formatearFecha(null)).toBe('Sin fecha');
    expect(formatearFecha('')).toBe('Sin fecha');
    expect(formatearFecha('cualquier cosa')).toBe('Sin fecha');
  });
});

describe('formatearMonto', () => {
  it('SIEMPRE nombra la moneda', () => {
    // "$ 1.000" no distingue un peso de un dolar, y un pipeline en dolares
    // leido como pesos es un error de 900 mil leido como un dato normal.
    expect(formatearMonto(1000, 'CLP')).toContain('CLP');
    expect(formatearMonto(1000, 'USD')).toContain('USD');
  });

  it('los pesos van sin decimales y los dolares con', () => {
    expect(formatearMonto(1500, 'CLP')).toBe('CLP 1.500');
    expect(formatearMonto(1500, 'USD')).toBe('USD 1.500,00');
  });
});

describe('resumenDeColumna', () => {
  it('lista las dos monedas y NO las suma', () => {
    const r = resumenDeColumna(
      columna({
        totalTratos: 2,
        montos: [
          { moneda: 'CLP', total: 1000 },
          { moneda: 'USD', total: 7 },
        ],
      }),
    );
    expect(r).toContain('CLP 1.000');
    expect(r).toContain('USD 7,00');
    // La afirmacion que importa: en ningun lado aparece la suma cruda.
    expect(r).not.toContain('1.007');
  });

  it('con tratos pero sin cifra dice "Sin valorar", no cero', () => {
    // Un trato al que nadie le puso valor no es un trato que no vale nada.
    const r = resumenDeColumna(columna({ totalTratos: 3, montos: [] }));
    expect(r).toBe('Sin valorar');
    expect(r).not.toContain('0');
  });

  it('una columna de verdad vacia lo dice distinto', () => {
    expect(resumenDeColumna(columna({ totalTratos: 0, montos: [] }))).toBe(
      'Sin oportunidades',
    );
  });
});

describe('necesitaMotivo', () => {
  it('solo perder exige motivo', () => {
    expect(necesitaMotivo(etapa({ tipo: 'lost' }))).toBe(true);
    expect(necesitaMotivo(etapa({ tipo: 'won' }))).toBe(false);
    expect(necesitaMotivo(etapa({ tipo: 'open' }))).toBe(false);
  });
});

describe('mapPipeline', () => {
  const crudo = {
    truncado: true,
    columnas: [
      {
        stage: { id: 'e1', code: 'nuevo', name: 'Nuevo', position: 0, kind: 'open' },
        deals: [
          {
            id: 'd1',
            crm_company_id: 'c1',
            stage_id: 'e1',
            title: 'Implantacion',
            amount: '1000.00',
            currency: 'CLP',
            expected_close_date: '2026-09-01',
          },
        ],
        total_deals: 40,
        montos: [{ moneda: 'CLP', total: '40000.00' }],
      },
    ],
  };

  it('el total sale del SERVIDOR, no de cuantas tarjetas vinieron', () => {
    // Es la afirmacion que impide que el tablero informe 1 cuando hay 40. La
    // lista viene cortada en el tope del servidor, asi que contar lo visible
    // daria un numero menor que el real sin que nada lo diga.
    const p = mapPipeline(crudo);
    expect(p.columnas[0].tratos).toHaveLength(1);
    expect(p.columnas[0].totalTratos).toBe(40);
  });

  it('se conserva el aviso de que la lista vino cortada', () => {
    expect(mapPipeline(crudo).truncado).toBe(true);
  });

  it('`amount` viaja como string y se convierte a numero', () => {
    expect(mapPipeline(crudo).columnas[0].tratos[0].monto).toBe(1000);
  });

  it('un trato sin `amount` queda en null, no en cero', () => {
    const sinMonto = {
      ...crudo,
      columnas: [
        {
          ...crudo.columnas[0],
          deals: [{ id: 'd2', crm_company_id: 'c1', stage_id: 'e1', title: 'X', amount: null }],
        },
      ],
    };
    expect(mapPipeline(sinMonto).columnas[0].tratos[0].monto).toBeNull();
  });

  it('una etapa con `kind` desconocido no desaparece del tablero', () => {
    // Descartarla se llevaria sus tratos de la vista, y parecerian borrados.
    const raro = {
      ...crudo,
      columnas: [
        { ...crudo.columnas[0], stage: { ...crudo.columnas[0].stage, kind: 'inventado' } },
      ],
    };
    const p = mapPipeline(raro);
    expect(p.columnas).toHaveLength(1);
    expect(p.columnas[0].etapa.tipo).toBe('open');
  });

  it('una respuesta vacia da un pipeline vacio y no revienta', () => {
    expect(mapPipeline({}).columnas).toEqual([]);
    expect(mapPipeline({}).truncado).toBe(false);
  });
});
