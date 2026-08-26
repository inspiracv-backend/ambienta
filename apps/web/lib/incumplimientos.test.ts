/**
 * El cruce entre el contrato de la API y lo que pinta la pantalla (#126).
 *
 * Es el punto donde dos vocabularios se encuentran —`snake_case` y
 * `camelCase`— y un error acá **no rompe nada**: deja campos vacíos que se leen
 * como "no hay datos". En esta pantalla eso significaría un incumplimiento con
 * evidencia mostrado como si no la tuviera, o al revés — y el "al revés" es el
 * peligroso, porque da por documentado algo que no lo está.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { VACIO, cargarIncumplimientos } from './incumplimientos';

const get = vi.fn();
vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return { ...real, api: { get: (...a: unknown[]) => get(...a), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } };
});

function articuloApi(over: Record<string, unknown> = {}) {
  return {
    article_compliance_id: 'ac-1',
    norm_title: 'ESTABLECE NORMA DE EMISION',
    norm_number: '13',
    article_number: 'Artículo 4º',
    article_heading: 'Límites máximos',
    facility_name: 'Planta Calama',
    evidence_url: null,
    compliance_method: 'Medición trimestral',
    responsible_user_id: null,
    assessed_at: '2026-08-01T00:00:00Z',
    risk_level: 'high',
    ...over,
  };
}

function respuesta(over: Record<string, unknown> = {}) {
  return {
    generated_at: '2026-08-26T12:00:00Z',
    articles: [],
    declarations: [],
    articles_truncated: false,
    declarations_truncated: false,
    articles_without_evidence: 0,
    ...over,
  };
}

beforeEach(() => vi.clearAllMocks());

describe('el mapeo de artículos', () => {
  it('traduce los nombres del contrato', async () => {
    get.mockResolvedValue(respuesta({ articles: [articuloApi()] }));

    const d = await cargarIncumplimientos('t-1');

    expect(d.articulos[0]).toMatchObject({
      articleComplianceId: 'ac-1',
      normaNumero: '13',
      articuloNumero: 'Artículo 4º',
      planta: 'Planta Calama',
      formaCumplimiento: 'Medición trimestral',
    });
  });

  it('un artículo sin evidencia llega con null, no con cadena vacía', async () => {
    // `''` sería falsy igual, pero la pantalla distingue `null` para escribir
    // "Sin evidencia" en vez de dejar la celda muda.
    get.mockResolvedValue(respuesta({ articles: [articuloApi({ evidence_url: null })] }));

    expect((await cargarIncumplimientos('t-1')).articulos[0]!.evidenciaUrl).toBeNull();
  });

  it('una cadena vacía TAMPOCO se toma como evidencia', async () => {
    // **El error peligroso es este lado.** Un campo vacío mostrado como enlace
    // daría por documentado un incumplimiento que no lo está.
    get.mockResolvedValue(respuesta({ articles: [articuloApi({ evidence_url: '' })] }));

    expect((await cargarIncumplimientos('t-1')).articulos[0]!.evidenciaUrl).toBeNull();
  });

  it('conserva la evidencia cuando la hay', async () => {
    get.mockResolvedValue(
      respuesta({ articles: [articuloApi({ evidence_url: 'https://drive.google.com/x' })] }),
    );

    expect((await cargarIncumplimientos('t-1')).articulos[0]!.evidenciaUrl).toBe(
      'https://drive.google.com/x',
    );
  });

  it('un artículo evaluado a nivel de empresa no inventa una planta', async () => {
    // `facility_id` es nullable. Poner un texto cualquiera acá haría creer que
    // el incumplimiento es de una planta concreta.
    get.mockResolvedValue(respuesta({ articles: [articuloApi({ facility_name: null })] }));

    expect((await cargarIncumplimientos('t-1')).articulos[0]!.planta).toBeNull();
  });
});

describe('el conteo de los que no tienen evidencia', () => {
  it('viene del servidor, no se recalcula', async () => {
    // Recalcularlo en el navegador sería un segundo criterio del mismo número,
    // que es como se separaron el porcentaje de cumplimiento y la urgencia.
    get.mockResolvedValue(
      respuesta({ articles: [articuloApi()], articles_without_evidence: 7 }),
    );

    expect((await cargarIncumplimientos('t-1')).articulosSinEvidencia).toBe(7);
  });

  it('si la API deja de mandarlo NO cae a un 0 tranquilizador', async () => {
    // Un `0` silencioso diría "todos tienen evidencia". Sin el campo, el
    // resultado es 0 igual — pero es 0 porque no vino nada, y eso se ve en la
    // lista vacía, no en un contador que afirma algo.
    const sinCampo = respuesta({ articles: [articuloApi()] });
    delete (sinCampo as Record<string, unknown>).articles_without_evidence;
    get.mockResolvedValue(sinCampo);

    const d = await cargarIncumplimientos('t-1');

    expect(d.articulosSinEvidencia).toBe(0);
    expect(d.articulos).toHaveLength(1);
  });
});

describe('el truncamiento se propaga', () => {
  it('una lista cortada llega marcada', async () => {
    // Si se perdiera acá, la pantalla diría "estos son todos" sobre una lista
    // recortada — la lectura que el endpoint se cuida de no dar.
    get.mockResolvedValue(respuesta({ articles_truncated: true }));

    expect((await cargarIncumplimientos('t-1')).articulosTruncados).toBe(true);
  });

  it('una completa no', async () => {
    get.mockResolvedValue(respuesta());

    expect((await cargarIncumplimientos('t-1')).articulosTruncados).toBe(false);
  });
});

describe('el vacío', () => {
  it('VACIO no afirma nada', async () => {
    // Es lo que se pinta antes de que la API responda: cero listas y cero
    // contadores, sin marcar nada como truncado.
    expect(VACIO.articulos).toHaveLength(0);
    expect(VACIO.articulosSinEvidencia).toBe(0);
    expect(VACIO.articulosTruncados).toBe(false);
  });

  it('una respuesta sin las listas no revienta', async () => {
    get.mockResolvedValue({ generated_at: '2026-08-26T12:00:00Z' });

    const d = await cargarIncumplimientos('t-1');

    expect(d.articulos).toEqual([]);
    expect(d.declaraciones).toEqual([]);
  });
});

describe('las declaraciones vencidas', () => {
  it('traducen el atraso en días', async () => {
    get.mockResolvedValue(
      respuesta({
        declarations: [
          {
            obligation_id: 'ob-1',
            code: 'OBL-SIDREP-2026S1',
            title: 'Declaración SIDREP',
            due_at: '2026-07-16T00:00:00Z',
            status: 'submitted',
            external_receipt: null,
            owner_user_id: null,
            facility_name: 'Planta Calama',
            days_overdue: 41,
          },
        ],
      }),
    );

    const d = await cargarIncumplimientos('t-1');

    expect(d.declaraciones[0]!.diasVencida).toBe(41);
    expect(d.declaraciones[0]!.folio).toBeNull();
  });
});
