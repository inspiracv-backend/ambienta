/**
 * La línea de tiempo de un registro (RF-113, #75).
 *
 * ## Qué vigila, y por qué no existía antes
 *
 * Este componente estaba en cinco pantallas de detalle **sin una sola prueba**,
 * y mostrando siempre lo mismo: nada. El store del que leía nunca le
 * preguntaba a la API, así que al recargar la página el historial quedaba
 * vacío — sobre registros con miles de eventos guardados (9.575 filas en
 * `audit_log` el día que se midió).
 *
 * Lo que se prueba acá no es que pinte una lista, es que **no mienta**:
 *
 * | situación | lo que NO puede decir |
 * |---|---|
 * | la consulta no volvió | «sin movimientos registrados» |
 * | la consulta falló | «sin movimientos registrados» |
 * | faltan los correos | nada — tiene que decirlo |
 * | la lista vino cortada | que eso es todo lo que pasó |
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { HistorialTimeline } from './HistorialTimeline';
import { AuditLogProvider } from '@/lib/audit-log-store';
import { SessionProvider } from '@/lib/session';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { iniciarSesionComo } from '@/test/utils';
import { mockUsers } from '@/mocks/users';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
}));

const get = vi.fn();

vi.mock('@/lib/api-client', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/api-client')>();
  return { ...real, api: { ...real.api, get: (...a: unknown[]) => get(...a) } };
});

function envoltura({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>
          <AuditLogProvider>{children}</AuditLogProvider>
        </SessionProvider>
      </UsersProvider>
    </ToastProvider>
  );
}

const HISTORIA = {
  eventos: [
    {
      tipo: 'actividad',
      ocurrido_el: '2026-09-05T12:00:00Z',
      actor_id: 'u-1',
      actor: 'Carlos Mendoza',
      resumen: 'Modificado',
      detalle: { accion: 'update', campos: ['due_at', 'status'], motivo: null },
    },
    {
      tipo: 'comentario',
      ocurrido_el: '2026-09-04T12:00:00Z',
      actor_id: 'u-2',
      actor: 'Ana Rojas',
      resumen: 'Comento',
      detalle: { cuerpo: 'El folio del portal llego con otro periodo' },
    },
    {
      tipo: 'adjunto',
      ocurrido_el: '2026-09-03T12:00:00Z',
      actor_id: null,
      actor: null,
      resumen: 'Adjunto un documento',
      detalle: { titulo: 'Comprobante SIDREP', codigo: 'DOC-014' },
    },
  ],
  fuentes: ['actividad', 'comentario', 'adjunto'],
  fuentes_pendientes: ['correo'],
  hay_mas: false,
};

function responder(respuesta: unknown) {
  get.mockImplementation((ruta: string) => {
    if (ruta.includes('/historial/')) {
      return respuesta instanceof Error
        ? Promise.reject(respuesta)
        : Promise.resolve(respuesta);
    }
    if (ruta.startsWith('/users/')) return Promise.resolve(mockUsers);
    if (ruta.startsWith('/tenants/')) return Promise.reject(new Error('401'));
    return Promise.resolve([]);
  });
}

function pintar() {
  return render(
    <HistorialTimeline entidadTipo="obligacion" entidadId="o-1" />,
    { wrapper: envoltura },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  iniciarSesionComo('admin_empresa');
});

describe('la historia guardada aparece', () => {
  it('pinta los tres orígenes, cada uno con lo suyo', async () => {
    responder(HISTORIA);
    pintar();

    // Actividad: los campos tocados, no sus valores.
    expect(await screen.findByText(/Campos: due_at, status/)).toBeInTheDocument();
    // Conversación: el texto del comentario.
    expect(screen.getByText(/otro periodo/)).toBeInTheDocument();
    // Adjunto: el documento.
    expect(screen.getByText('Comprobante SIDREP')).toBeInTheDocument();
  });

  it('pide la entidad traducida al vocabulario de la API', async () => {
    responder(HISTORIA);
    pintar();

    await screen.findByText(/Campos:/);
    const ruta = String(
      get.mock.calls.find((c) => String(c[0]).includes('/historial/'))?.[0],
    );
    // La pantalla dice `obligacion`; la API entiende `obligation`. Sin la
    // traducción esto respondería 422 en cada carga de la ficha.
    expect(ruta).toContain('entity_type=obligation');
  });

  it('un evento sin actor dice «Alguien», no un nombre inventado', async () => {
    responder(HISTORIA);
    pintar();

    expect(await screen.findByText('Alguien')).toBeInTheDocument();
  });
});

describe('lo que no puede leerse como "no pasó nada"', () => {
  it('mientras la consulta no vuelve, no dice que no hay movimientos', async () => {
    get.mockImplementation(() => new Promise(() => {}));
    pintar();

    expect(await screen.findByText('Comprobando…')).toBeInTheDocument();
    expect(screen.queryByText(/Sin movimientos registrados/)).not.toBeInTheDocument();
  });

  it('si falla, lo dice — y tampoco muestra el vacío', async () => {
    responder(new Error('se cayó'));
    pintar();

    const alerta = await screen.findByRole('alert');
    expect(alerta).toHaveTextContent(/No se pudo cargar el historial/);
    expect(screen.queryByText(/Sin movimientos registrados/)).not.toBeInTheDocument();
  });

  it('sin nada guardado sí muestra el vacío, que es una respuesta', async () => {
    responder({ ...HISTORIA, eventos: [] });
    pintar();

    expect(await screen.findByText(/Sin movimientos registrados/)).toBeInTheDocument();
  });
});

describe('lo que se declara en vez de callarse', () => {
  it('avisa que los correos todavía no se capturan', async () => {
    responder(HISTORIA);
    pintar();

    // RF-113 nombra cuatro fuentes. Mostrar tres y callar la cuarta deja una
    // línea de tiempo que se ve completa, en un módulo que existe porque la
    // información se pierde justamente por correo.
    expect(
      await screen.findByText(/Todavía no se muestran los correo/),
    ).toBeInTheDocument();
  });

  it('avisa cuando la lista vino cortada', async () => {
    responder({ ...HISTORIA, hay_mas: true });
    pintar();

    expect(
      await screen.findByText(/tiene historia anterior/),
    ).toBeInTheDocument();
  });
});
