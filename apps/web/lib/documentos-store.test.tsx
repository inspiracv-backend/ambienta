/**
 * Documentos, revisiones y el flujo de subida (RF-102 a RF-106).
 *
 * ## Lo que estas pruebas protegen
 *
 * 1. **Que cero documentos se vea como cero documentos.** Nueve stores de esta
 *    aplicación caían a `mocks/` cuando la API respondía vacío. En un módulo
 *    documental ese error es peor que en cualquier otro: una persona que ve
 *    "Procedimiento · Vigente" en la lista asume que existe y que puede
 *    mostrarlo en una fiscalización.
 * 2. **Que la subida sea de verdad tres pasos**, y que el `PUT` al bucket
 *    **no lleve el token de Clerk**: va a un tercero, y mandárselo sería
 *    filtrar la sesión.
 * 3. **Que publicar recargue todas las revisiones del documento**, no sólo la
 *    tocada: poner una en vigencia deja obsoleta a la anterior en el mismo
 *    paso, y parchear sólo una dejaría a la otra mintiendo en pantalla.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import type { ReactNode } from 'react';
import { DocumentosProvider, useDocumentos } from './documentos-store';
import { SessionProvider } from './session';
import { ToastProvider } from './toast-store';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/documentos',
}));

const get = vi.fn();
const post = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return {
    ...real,
    api: {
      get: (...a: unknown[]) => get(...a),
      post: (...a: unknown[]) => post(...a),
      patch: vi.fn(),
      delete: vi.fn(),
    },
  };
});

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>
          <DocumentosProvider>{children}</DocumentosProvider>
        </SessionProvider>
      </UsersProvider>
    </ToastProvider>
  );
}

function documentoApi(over: Record<string, unknown> = {}) {
  return {
    id: 'doc-1',
    tenant_id: 't-1',
    code: 'PR-07',
    title: 'Manejo de residuos peligrosos',
    document_type: 'procedimiento',
    status: 'vigente',
    classification: 'internal',
    tags: [],
    current_version_id: 'rev-2',
    created_at: '2026-08-01T12:00:00Z',
    updated_at: '2026-08-20T12:00:00Z',
    ...over,
  };
}

function revisionApi(over: Record<string, unknown> = {}) {
  return {
    id: 'rev-1',
    document_id: 'doc-1',
    version_no: 1,
    lifecycle_status: 'borrador',
    file_name: 'manual.pdf',
    mime_type: 'application/pdf',
    size_bytes: 2048,
    storage_provider: 'backblaze',
    created_at: '2026-08-01T12:00:00Z',
    approved_by: null,
    approved_at: null,
    valid_from: null,
    valid_to: null,
    obsoleted_at: null,
    obsoleted_reason: null,
    ...over,
  };
}

/**
 * Monta el store **y espera a que la sesión esté cargada**.
 *
 * Dos trampas que esta función evita, y las dos ya mordieron antes en este
 * repositorio:
 *
 * 1. **`waitFor(cargando === false)` a secas no sirve.** Sin sesión el efecto
 *    sale temprano y `cargando` pasa a `false` de inmediato, así que las
 *    afirmaciones correrían sin que la API se llame nunca.
 * 2. **El mock se enruta por ruta, no por orden.** `mockResolvedValueOnce` se
 *    lo lleva el primer `get` que ocurra, y los otros providers del árbol
 *    —usuarios, sesión— piden lo suyo antes. La primera versión de estas
 *    pruebas fallaba con "expected [] to have a length of 1" por eso: los
 *    documentos se los había comido `/users/`.
 */
async function montar(documentos: unknown[] = [], revisiones?: unknown[]) {
  get.mockImplementation((ruta: string) => {
    const r = String(ruta);
    if (r.includes('/versions')) return Promise.resolve(revisiones ?? []);
    if (r.startsWith('/documents')) return Promise.resolve(documentos);
    return Promise.resolve([]);
  });

  const vista = renderHook(() => useDocumentos(), { wrapper });
  await waitFor(() =>
    expect(
      get.mock.calls.some(([ruta]) => String(ruta).startsWith('/documents')),
    ).toBe(true),
  );
  await waitFor(() => expect(vista.result.current.cargando).toBe(false));
  return vista;
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  iniciarSesionComo('admin_empresa');
  get.mockResolvedValue([]);
  post.mockResolvedValue({});
  vi.unstubAllGlobals();
});

describe('la lista', () => {
  it('muestra lo que devuelve la API', async () => {
    const { result } = await montar([documentoApi()]);

    expect(result.current.documentos).toHaveLength(1);
    expect(result.current.documentos[0].codigo).toBe('PR-07');
    expect(result.current.documentos[0].titulo).toBe('Manejo de residuos peligrosos');
  });

  it('con CERO documentos NO inventa ninguno', async () => {
    const { result } = await montar([]);

    expect(result.current.documentos).toEqual([]);
    expect(result.current.errorDeCarga).toBeNull();
  });

  it('si la API falla deja la lista vacía y lo dice', async () => {
    get.mockImplementation((ruta: string) =>
      String(ruta).startsWith('/documents')
        ? Promise.reject(new Error('sin red'))
        : Promise.resolve([]),
    );
    const vista = renderHook(() => useDocumentos(), { wrapper });
    await waitFor(() => expect(vista.result.current.errorDeCarga).toBeTruthy());

    expect(vista.result.current.documentos).toEqual([]);
  });

  it('un documento sin código no se rompe ni se inventa uno', async () => {
    const { result } = await montar([documentoApi({ code: null })]);
    expect(result.current.documentos[0].codigo).toBeNull();
  });
});

describe('las revisiones', () => {
  it('se piden por documento y llegan de la más nueva a la más vieja', async () => {
    const { result } = await montar([documentoApi()]);

    get.mockResolvedValueOnce([
      revisionApi({ id: 'rev-1', version_no: 1 }),
      revisionApi({ id: 'rev-2', version_no: 2, lifecycle_status: 'vigente' }),
    ]);
    await act(async () => {
      await result.current.cargarRevisiones('doc-1');
    });

    const revisiones = result.current.revisionesDe('doc-1');
    expect(revisiones?.map((r) => r.numero)).toEqual([2, 1]);
  });

  it('mapea el ciclo de vida completo', async () => {
    const { result } = await montar([documentoApi()]);

    get.mockResolvedValueOnce([
      revisionApi({
        lifecycle_status: 'vigente',
        approved_by: 'u-9',
        approved_at: '2026-08-10T00:00:00Z',
        valid_from: '2026-08-11',
      }),
    ]);
    await act(async () => {
      await result.current.cargarRevisiones('doc-1');
    });

    const rev = result.current.revisionesDe('doc-1')![0];
    expect(rev.estado).toBe('vigente');
    expect(rev.aprobadaPor).toBe('u-9');
    expect(rev.rigeDesde).toBe('2026-08-11');
  });
});

describe('la subida', () => {
  function archivo(nombre = 'manual.pdf', tipo = 'application/pdf') {
    return new File(['contenido'], nombre, { type: tipo });
  }

  it('son tres pasos y el del medio va DIRECTO al bucket', async () => {
    const { result } = await montar([documentoApi()]);

    post.mockResolvedValueOnce({
      url: 'https://s3.us-east-005.backblazeb2.com/Ambienta/tenants/t/x.pdf?firma',
      storage_key: 'tenants/t/documents/doc-1/v1/manual.pdf',
      expires_in: 900,
      headers: { 'Content-Type': 'application/pdf' },
    });
    post.mockResolvedValueOnce(revisionApi());

    const fetchFalso = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal('fetch', fetchFalso);

    await act(async () => {
      await result.current.subir('doc-1', archivo());
    });

    // 1. pedir el permiso, 3. confirmar → nuestra API
    expect(post).toHaveBeenCalledTimes(2);
    expect(post.mock.calls[0][0]).toBe('/documents/doc-1/upload-url');
    expect(post.mock.calls[1][0]).toBe('/documents/doc-1/confirm-upload');

    // 2. subir → el bucket, con `fetch` pelado
    expect(fetchFalso).toHaveBeenCalledTimes(1);
    const [url, opciones] = fetchFalso.mock.calls[0];
    expect(String(url)).toContain('backblazeb2.com');
    expect(opciones.method).toBe('PUT');
  });

  it('el PUT al bucket NO lleva la sesión', async () => {
    const { result } = await montar([documentoApi()]);

    post.mockResolvedValueOnce({
      url: 'https://s3.us-east-005.backblazeb2.com/x?firma',
      storage_key: 'k',
      expires_in: 900,
      headers: { 'Content-Type': 'application/pdf' },
    });
    post.mockResolvedValueOnce(revisionApi());
    const fetchFalso = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal('fetch', fetchFalso);

    await act(async () => {
      await result.current.subir('doc-1', archivo());
    });

    const cabeceras = fetchFalso.mock.calls[0][1].headers as Record<string, string>;
    expect(Object.keys(cabeceras).map((k) => k.toLowerCase())).not.toContain(
      'authorization',
    );
    expect(JSON.stringify(cabeceras)).not.toContain('Bearer');
  });

  it('manda las cabeceras firmadas TAL CUAL', async () => {
    const { result } = await montar([documentoApi()]);

    const firmadas = { 'Content-Type': 'application/pdf' };
    post.mockResolvedValueOnce({
      url: 'https://b2/x',
      storage_key: 'k',
      expires_in: 900,
      headers: firmadas,
    });
    post.mockResolvedValueOnce(revisionApi());
    const fetchFalso = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal('fetch', fetchFalso);

    await act(async () => {
      await result.current.subir('doc-1', archivo());
    });

    // Van **dentro de la firma**: con otras, B2 responde 403 y se lee como un
    // problema de credenciales que no lo es.
    expect(fetchFalso.mock.calls[0][1].headers).toEqual(firmadas);
  });

  it('un archivo sin tipo declarado NO se manda con tipo vacío', async () => {
    const { result } = await montar([documentoApi()]);

    post.mockResolvedValueOnce({
      url: 'https://b2/x',
      storage_key: 'k',
      expires_in: 900,
      headers: {},
    });
    post.mockResolvedValueOnce(revisionApi());
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200 }));

    await act(async () => {
      await result.current.subir('doc-1', archivo('raro.xyz', ''));
    });

    // La API valida el tipo contra una lista blanca, y `''` no está: mandarlo
    // vacío haría que rechazara la subida por un dato que el navegador no supo
    // completar.
    const cuerpo = post.mock.calls[0][1] as { mime_type: string };
    expect(cuerpo.mime_type).toBe('application/octet-stream');
  });

  it('si el bucket rechaza, NO se confirma la subida', async () => {
    const { result } = await montar([documentoApi()]);

    post.mockResolvedValueOnce({
      url: 'https://b2/x',
      storage_key: 'k',
      expires_in: 900,
      headers: {},
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 403 }));

    let ok = true;
    await act(async () => {
      ok = await result.current.subir('doc-1', archivo());
    });

    expect(ok).toBe(false);
    // Sólo el `upload-url`. Confirmar una subida que falló crearía una revisión
    // apuntando a un objeto que no existe.
    expect(post).toHaveBeenCalledTimes(1);
    expect(result.current.revisionesDe('doc-1')).toBeUndefined();
  });

  it('va contando en qué paso está', async () => {
    const { result } = await montar([documentoApi()]);

    post.mockResolvedValueOnce({
      url: 'https://b2/x',
      storage_key: 'k',
      expires_in: 900,
      headers: {},
    });
    post.mockResolvedValueOnce(revisionApi());

    // Se detiene el `PUT` a mitad para poder mirar el estado **mientras** sube.
    //
    // La primera versión leía `result.current.subiendo` desde dentro del mock y
    // salía siempre `null`: `result.current` es una foto del último render, y
    // dentro del mock todavía no hubo re-render. Fallaba con
    // `[ 'sin-estado', 'sin-estado' ]`, que no dice nada del código.
    let soltarElPut: () => void = () => {};
    const putEnCurso = new Promise<void>((resolver) => {
      soltarElPut = resolver;
    });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async () => {
        await putEnCurso;
        return { ok: true, status: 200 };
      }),
    );

    let subida: Promise<boolean>;
    await act(async () => {
      subida = result.current.subir('doc-1', archivo());
      // Deja correr los pasos previos al `PUT`.
      await Promise.resolve();
    });

    // Pedir el permiso son milisegundos; subir puede ser un minuto. Una sola
    // rueda girando durante todo eso no distingue "está subiendo" de "se colgó".
    await waitFor(() => expect(result.current.subiendo?.paso).toBe('subiendo'));
    expect(result.current.subiendo?.nombreArchivo).toBe('manual.pdf');
    expect(result.current.subiendo?.documentoId).toBe('doc-1');

    await act(async () => {
      soltarElPut();
      await subida!;
    });

    expect(result.current.subiendo).toBeNull();
  });
});

describe('el ciclo de vida', () => {
  it('publicar recarga TODAS las revisiones del documento', async () => {
    const { result } = await montar([documentoApi()]);

    post.mockResolvedValueOnce(revisionApi({ lifecycle_status: 'vigente' }));
    get.mockResolvedValueOnce([
      revisionApi({ id: 'rev-1', version_no: 1, lifecycle_status: 'obsoleto' }),
      revisionApi({ id: 'rev-2', version_no: 2, lifecycle_status: 'vigente' }),
    ]);
    get.mockResolvedValue([documentoApi()]);

    await act(async () => {
      await result.current.mover('doc-1', 'rev-2', 'publish');
    });

    // Poner una en vigencia deja obsoleta a la anterior **en el mismo paso**.
    // Parchear en memoria sólo la tocada dejaría a la otra diciendo "vigente"
    // en pantalla hasta que alguien recargue.
    const revisiones = result.current.revisionesDe('doc-1');
    expect(revisiones?.find((r) => r.numero === 1)?.estado).toBe('obsoleto');
    expect(revisiones?.find((r) => r.numero === 2)?.estado).toBe('vigente');
  });

  it('marcar obsoleta manda el motivo', async () => {
    const { result } = await montar([documentoApi()]);

    post.mockResolvedValueOnce(revisionApi({ lifecycle_status: 'obsoleto' }));
    get.mockResolvedValue([]);

    await act(async () => {
      await result.current.mover('doc-1', 'rev-1', 'obsolete', {
        motivo: 'cambió la normativa',
      });
    });

    expect(post.mock.calls[0][0]).toBe('/documents/doc-1/versions/rev-1/obsolete');
    expect(post.mock.calls[0][1]).toEqual({ motivo: 'cambió la normativa' });
  });

  it('si la API rechaza la transición, devuelve false', async () => {
    const { result } = await montar([documentoApi()]);

    post.mockRejectedValueOnce(new Error('409'));

    let ok = true;
    await act(async () => {
      ok = await result.current.mover('doc-1', 'rev-1', 'approve');
    });
    expect(ok).toBe(false);
  });
});

describe('la descarga', () => {
  it('abre el enlace firmado en otra pestaña', async () => {
    const { result } = await montar([documentoApi()]);

    get.mockResolvedValueOnce({ url: 'https://b2/firmada', expires_in: 300 });
    const abrir = vi.fn();
    vi.stubGlobal('open', abrir);

    await act(async () => {
      await result.current.descargar('doc-1', 'rev-1');
    });

    // En otra pestaña y no navegando: el enlace vence en minutos, y reemplazar
    // la pantalla actual dejaría a la persona sin dónde volver si ya expiró.
    expect(abrir).toHaveBeenCalledWith(
      'https://b2/firmada',
      '_blank',
      'noopener,noreferrer',
    );
  });
});
