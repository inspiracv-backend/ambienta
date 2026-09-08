/**
 * El respaldo documental de un registro, en el navegador (RF-108).
 *
 * ## Lo que vigila
 *
 * Que **una lista vacía no afirme nunca «este requisito no tiene evidencia»**
 * cuando lo que pasó fue que no se pudo preguntar. Son tres estados que se ven
 * casi iguales en la pantalla y sólo uno es una respuesta:
 *
 * | estado | significa |
 * |---|---|
 * | `null` | la consulta no volvió |
 * | error | no se pudo preguntar |
 * | `[]` | se preguntó y no hay ninguno |
 *
 * La distinción decide qué se le muestra a un fiscalizador, que es exactamente
 * quien lee esta sección.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { usarDocumentosVinculados } from './usar-documentos-vinculados';
import { SessionProvider } from './session';
import { ToastProvider } from './toast-store';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';
import { mockUsers } from '@/mocks/users';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
}));

const get = vi.fn();

vi.mock('./api-client', async (importarReal) => {
  const real = await importarReal<typeof import('./api-client')>();
  return { ...real, api: { ...real.api, get: (...a: unknown[]) => get(...a) } };
});

function envoltura({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>{children}</SessionProvider>
      </UsersProvider>
    </ToastProvider>
  );
}

const UN_PROCEDIMIENTO = [
  {
    id: 'd-1',
    code: 'PR-AMB-004',
    title: 'Procedimiento de manejo de residuos peligrosos',
    document_type: 'procedimiento',
    status: 'vigente',
  },
];

function responder(respuesta: unknown) {
  get.mockImplementation((ruta: string) => {
    if (ruta.includes('/documents/vinculados')) {
      return respuesta instanceof Error
        ? Promise.reject(respuesta)
        : Promise.resolve(respuesta);
    }
    if (ruta.startsWith('/users/')) return Promise.resolve(mockUsers);
    if (ruta.startsWith('/tenants/')) return Promise.reject(new Error('401'));
    return Promise.resolve([]);
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  iniciarSesionComo('admin_empresa');
});

describe('la consulta', () => {
  it('manda la entidad como parámetros y mapea el código, que es lo que se cita', async () => {
    responder(UN_PROCEDIMIENTO);
    const { result } = renderHook(
      () => usarDocumentosVinculados('obligation', 'o-1'),
      { wrapper: envoltura },
    );

    await waitFor(() => expect(result.current.documentos).not.toBeNull());

    const ruta = String(
      get.mock.calls.find((c) => String(c[0]).includes('/documents/vinculados'))?.[0],
    );
    expect(ruta).toContain('entity_type=obligation');
    expect(ruta).toContain('entity_id=o-1');

    const [doc] = result.current.documentos!;
    expect(doc.codigo).toBe('PR-AMB-004');
    expect(doc.titulo).toContain('residuos');
  });

  it('un documento sin código no se descarta ni se rompe', async () => {
    // El `code` es nulable en la base: un documento sin codificar todavía sigue
    // siendo un respaldo real, y esconderlo diría que no existe.
    responder([{ ...UN_PROCEDIMIENTO[0], code: null }]);
    const { result } = renderHook(
      () => usarDocumentosVinculados('obligation', 'o-1'),
      { wrapper: envoltura },
    );

    await waitFor(() => expect(result.current.documentos).not.toBeNull());
    expect(result.current.documentos).toHaveLength(1);
    expect(result.current.documentos![0].codigo).toBeNull();
  });
});

describe('una lista vacía nunca puede leerse como "no hay evidencia"', () => {
  it('mientras no vuelve la consulta, no hay lista', async () => {
    get.mockImplementation(() => new Promise(() => {}));
    const { result } = renderHook(
      () => usarDocumentosVinculados('obligation', 'o-1'),
      { wrapper: envoltura },
    );

    await new Promise((r) => setTimeout(r, 30));

    expect(result.current.documentos).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('si falla, lo dice', async () => {
    responder(new Error('se cayó la consulta'));
    const { result } = renderHook(
      () => usarDocumentosVinculados('obligation', 'o-1'),
      { wrapper: envoltura },
    );

    await waitFor(() => expect(result.current.error).not.toBeNull());
    // Se afirma que **hay** mensaje, no cuál: `mensajeDeError` normaliza el
    // texto, y fijar su redacción rompería la prueba cada vez que alguien lo
    // mejore sin cambiar el comportamiento.
    expect(result.current.error).toBeTruthy();
    // La lista queda vacía, pero acompañada del error: vacía **a secas** es lo
    // que afirmaría que este requisito no tiene con qué sostenerse.
    expect(result.current.documentos).toEqual([]);
  });

  it('sin ningún documento, la lista vacía sí es una respuesta', async () => {
    responder([]);
    const { result } = renderHook(
      () => usarDocumentosVinculados('obligation', 'o-1'),
      { wrapper: envoltura },
    );

    await waitFor(() => expect(result.current.documentos).not.toBeNull());
    expect(result.current.documentos).toEqual([]);
    expect(result.current.error).toBeNull();
  });
});
