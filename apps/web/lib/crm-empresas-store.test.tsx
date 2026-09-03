/**
 * La ficha de una empresa del CRM: lo que NO puede hacer cuando algo falla.
 *
 * Una ficha comercial se lee para decidir a quién llamar y qué decirle. Sus dos
 * formas de mentir son las que se fijan acá:
 *
 * 1. **Colapsar todo en un solo error.** Si los contactos cargan y la línea de
 *    tiempo no, esconder los contactos borra información que sí llegó.
 * 2. **Mostrar una sección vacía cuando en realidad no se supo.** Una lista
 *    vacía afirma «esta empresa no tiene contactos», y sobre esa afirmación se
 *    deja de llamar a alguien.
 *
 * Y un tercero propio de este store: contactos y tratos se filtran **en el
 * navegador**, porque la API no acepta filtro por empresa. Si la respuesta vino
 * cortada en el tope, «no tiene contactos» puede ser falso — y eso se tiene que
 * poder decir.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { useCrmEmpresas, useFichaDeEmpresa } from './crm-empresas-store';
import { SessionProvider } from './session';
import { ToastProvider } from './toast-store';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
}));

const get = vi.fn();
const getPagina = vi.fn();
const post = vi.fn();
const patch = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      getPagina: (...a: unknown[]) => getPagina(...a),
      post: (...a: unknown[]) => post(...a),
      patch: (...a: unknown[]) => patch(...a),
      delete: vi.fn(),
    },
  };
});

const EMPRESA = 'c0000000-0000-0000-0000-000000000001';

function envoltura({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>{children}</SessionProvider>
      </UsersProvider>
    </ToastProvider>
  );
}

const FICHA = { id: EMPRESA, name: 'Constructora del Sur SpA', status: 'prospect' };
const CONTACTO = { id: 'ct-1', crm_company_id: EMPRESA, full_name: 'Carla Miranda' };
const TRATO = { id: 't-1', crm_company_id: EMPRESA, stage_id: 'e-1', title: 'Implantación' };
const ETAPA = { id: 'e-1', code: 'neg', name: 'Negociación', position: 1, kind: 'open' };
const ACTIVIDAD = { id: 'a-1', kind: 'call', subject: 'Llamada inicial', occurred_at: '2026-09-01T10:00:00Z' };

/** Respuestas normales; cada prueba rompe solo lo que le interesa. */
function todoBien({ cortadas = [] as string[] } = {}) {
  get.mockImplementation((ruta: string) => {
    if (ruta.startsWith('/crm/companies/')) return Promise.resolve(FICHA);
    if (ruta.startsWith('/crm/stages')) return Promise.resolve([ETAPA]);
    if (ruta.startsWith('/crm/activities')) return Promise.resolve([ACTIVIDAD]);
    return Promise.reject(new Error(`ruta no esperada: ${ruta}`));
  });
  getPagina.mockImplementation((ruta: string) => {
    const cual = ruta.includes('/crm/contacts') ? 'contacts' : 'deals';
    return Promise.resolve({
      datos: cual === 'contacts' ? [CONTACTO] : [TRATO],
      hayMas: cortadas.includes(cual),
    });
  });
}

beforeEach(() => {
  window.localStorage.clear();
  get.mockReset();
  getPagina.mockReset();
  post.mockReset();
  patch.mockReset();
  iniciarSesionComo('admin_empresa');
  todoBien();
});

async function montarFicha() {
  const r = renderHook(() => useFichaDeEmpresa(EMPRESA), { wrapper: envoltura });
  await waitFor(() => expect(r.result.current.cargando).toBe(false));
  return r;
}

describe('cuando todo carga', () => {
  it('trae la ficha, sus contactos, sus tratos, las etapas y la línea de tiempo', async () => {
    const { result } = await montarFicha();

    expect(result.current.empresa?.nombre).toBe('Constructora del Sur SpA');
    expect(result.current.contactos).toHaveLength(1);
    expect(result.current.tratos).toHaveLength(1);
    expect(result.current.etapas).toHaveLength(1);
    expect(result.current.actividades).toHaveLength(1);
    expect(result.current.errores).toEqual({});
  });

  it('los contactos y tratos de OTRA empresa no entran en esta ficha', async () => {
    // Los dos listados vienen sin filtrar del servidor. Sin este filtro, la
    // ficha mostraría la cartera entera bajo el nombre de una sola empresa.
    getPagina.mockImplementation((ruta: string) =>
      Promise.resolve({
        datos: ruta.includes('/crm/contacts')
          ? [CONTACTO, { id: 'ct-9', crm_company_id: 'otra', full_name: 'Ajeno' }]
          : [TRATO, { id: 't-9', crm_company_id: 'otra', stage_id: 'e-1', title: 'Ajeno' }],
        hayMas: false,
      }),
    );
    const { result } = await montarFicha();

    expect(result.current.contactos.map((c) => c.id)).toEqual(['ct-1']);
    expect(result.current.tratos.map((t) => t.id)).toEqual(['t-1']);
  });
});

describe('cuando falla UNA parte', () => {
  it('un fallo de la línea de tiempo no se lleva los contactos ni los tratos', async () => {
    // La afirmación central. Colapsar las cuatro peticiones en un solo error
    // escondería datos que sí llegaron.
    get.mockImplementation((ruta: string) => {
      if (ruta.startsWith('/crm/activities')) return Promise.reject(new Error('caída'));
      if (ruta.startsWith('/crm/companies/')) return Promise.resolve(FICHA);
      return Promise.resolve([ETAPA]);
    });
    const { result } = await montarFicha();

    expect(result.current.contactos).toHaveLength(1);
    expect(result.current.tratos).toHaveLength(1);
    expect(result.current.errores.actividades).toBeTruthy();
    expect(result.current.errores.contactos).toBeUndefined();
  });

  it('un fallo de los contactos no vacía la línea de tiempo', async () => {
    getPagina.mockImplementation((ruta: string) =>
      ruta.includes('/crm/contacts')
        ? Promise.reject(new Error('caída'))
        : Promise.resolve({ datos: [TRATO], hayMas: false }),
    );
    const { result } = await montarFicha();

    expect(result.current.actividades).toHaveLength(1);
    expect(result.current.tratos).toHaveLength(1);
    expect(result.current.errores.contactos).toBeTruthy();
  });

  it('si la ficha misma no carga, `empresa` queda en null y se dice por qué', async () => {
    // La pantalla necesita distinguir «no existe» de «no se pudo preguntar»:
    // sin el mensaje, un corte de red se ve igual que una empresa borrada.
    get.mockImplementation((ruta: string) => {
      if (ruta.startsWith('/crm/companies/')) return Promise.reject(new Error('caída'));
      if (ruta.startsWith('/crm/stages')) return Promise.resolve([ETAPA]);
      return Promise.resolve([ACTIVIDAD]);
    });
    const { result } = await montarFicha();

    expect(result.current.empresa).toBeNull();
    expect(result.current.errores.empresa).toBeTruthy();
  });
});

describe('cuando la API cortó una lista', () => {
  it('se nombra CUÁL vino cortada', async () => {
    // Sin nombrarla, «puede faltar algo» obliga a revisar las dos secciones
    // para encontrar dónde.
    todoBien({ cortadas: ['contacts'] });
    const { result } = await montarFicha();

    expect(result.current.listasCortadas).toEqual(['contactos']);
  });

  it('las dos cuando las dos se cortaron', async () => {
    todoBien({ cortadas: ['contacts', 'deals'] });
    const { result } = await montarFicha();

    expect(result.current.listasCortadas).toEqual(['contactos', 'oportunidades']);
  });

  it('y nada que avisar cuando no cortó', async () => {
    const { result } = await montarFicha();

    expect(result.current.listasCortadas).toEqual([]);
  });
});

describe('las escrituras', () => {
  it('un trato nuevo se crea SIN `stage_id`', async () => {
    // La etapa la elige la API: la primera **abierta**. Elegirla acá repetiría
    // esa regla, y si alguien reordena y deja «Perdido» arriba, un trato nuevo
    // nacería perdido.
    const { result } = await montarFicha();
    post.mockResolvedValue({});

    await act(async () => {
      await result.current.crearTrato({ titulo: 'Nuevo', monto: '1000', moneda: 'CLP' });
    });

    const [ruta, cuerpo] = post.mock.calls[0] as [string, Record<string, unknown>];
    expect(ruta).toBe('/crm/deals');
    expect(cuerpo).not.toHaveProperty('stage_id');
    expect(cuerpo.crm_company_id).toBe(EMPRESA);
  });

  it('el monto viaja como texto, no como número', async () => {
    // `amount` es un `numeric` de Postgres. Pasarlo por `Number` pierde
    // precisión en montos grandes, y eso es plata que después no cuadra.
    const { result } = await montarFicha();
    post.mockResolvedValue({});

    await act(async () => {
      await result.current.crearTrato({ titulo: 'Nuevo', monto: '99999999999999.99' });
    });

    const [, cuerpo] = post.mock.calls[0] as [string, Record<string, unknown>];
    expect(cuerpo.amount).toBe('99999999999999.99');
  });

  it('un monto vacío va como null, no como 0', async () => {
    // `null` es **sin valorar**; `0` es un trato que no vale nada. El pipeline
    // suma los montos, así que confundirlos cambia el total de una columna.
    const { result } = await montarFicha();
    post.mockResolvedValue({});

    await act(async () => {
      await result.current.crearTrato({ titulo: 'Nuevo', monto: '' });
    });

    const [, cuerpo] = post.mock.calls[0] as [string, Record<string, unknown>];
    expect(cuerpo.amount).toBeNull();
  });

  it('editar un trato NO manda `stage_id`', async () => {
    // Mover de columna cierra el trato, exige motivo al perder o lo reabre.
    // Un PATCH genérico se llevaría todo eso por delante.
    const { result } = await montarFicha();
    patch.mockResolvedValue({});

    await act(async () => {
      await result.current.editarTrato('t-1', { titulo: 'Otro' });
    });

    const [, cuerpo] = patch.mock.calls[0] as [string, Record<string, unknown>];
    expect(cuerpo).not.toHaveProperty('stage_id');
  });

  it('una actividad cuelga SOLO de la empresa', async () => {
    // La base exige exactamente un padre: dos la rechazan, ninguno deja una
    // actividad que no aparece en ninguna ficha.
    const { result } = await montarFicha();
    post.mockResolvedValue({});

    await act(async () => {
      await result.current.registrarActividad({ tipo: 'call', asunto: 'Llamada' });
    });

    const [ruta, cuerpo] = post.mock.calls[0] as [string, Record<string, unknown>];
    expect(ruta).toBe('/crm/activities');
    expect(cuerpo.crm_company_id).toBe(EMPRESA);
    expect(cuerpo.crm_contact_id).toBeUndefined();
    expect(cuerpo.crm_deal_id).toBeUndefined();
  });

  it('mover un trato devuelve los efectos que informó el servidor', async () => {
    // Mover puede cerrar el trato o reabrirlo. Sin decirlo, la persona lo
    // descubre cuando el trato desaparece de sus pendientes.
    const { result } = await montarFicha();
    post.mockResolvedValue({ efectos: ['El trato quedó cerrado'] });

    let r!: Awaited<ReturnType<typeof result.current.moverTrato>>;
    await act(async () => {
      r = await result.current.moverTrato('t-1', 'e-2');
    });

    expect(r.ok).toBe(true);
    expect(r.efectos).toEqual(['El trato quedó cerrado']);
  });

  it('una escritura rechazada devuelve el motivo y no revienta', async () => {
    const { result } = await montarFicha();
    post.mockRejectedValue(new Error('no'));

    let r!: Awaited<ReturnType<typeof result.current.crearTrato>>;
    await act(async () => {
      r = await result.current.crearTrato({ titulo: 'Nuevo' });
    });

    expect(r.ok).toBe(false);
    expect(r.error).toBeTruthy();
  });
});

describe('el listado de la cartera', () => {
  it('se pide con `getPagina`, para que el corte no sea invisible', async () => {
    // Con `get` la cabecera `X-Has-More` se pierde antes de llegar acá, y una
    // cartera de 500 de 640 se ve exactamente igual que una completa.
    getPagina.mockResolvedValue({ datos: [FICHA], hayMas: true });
    const r = renderHook(() => useCrmEmpresas(), { wrapper: envoltura });
    await waitFor(() => expect(r.result.current.cargando).toBe(false));

    expect(getPagina).toHaveBeenCalled();
    expect(r.result.current.hayMas).toBe(true);
    expect(r.result.current.empresas).toHaveLength(1);
  });

  it('un fallo deja la lista VACÍA y con su motivo, no con lo último conocido', async () => {
    // Una lista que sobrevive a una petición fallida se lee como el estado
    // actual de la cartera.
    getPagina.mockRejectedValue(new Error('caída'));
    const r = renderHook(() => useCrmEmpresas(), { wrapper: envoltura });
    await waitFor(() => expect(r.result.current.cargando).toBe(false));

    expect(r.result.current.empresas).toEqual([]);
    expect(r.result.current.errorDeCarga).toBeTruthy();
  });
});
