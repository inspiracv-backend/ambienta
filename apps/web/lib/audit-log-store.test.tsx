import { describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { AuditLogProvider, diffCampos, useAuditLog, useRegistrarAuditoria } from './audit-log-store';
import { SessionProvider } from './session';
import { UsersProvider } from './users-store';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/dashboard',
}));

// El log arranca con eventos semilla; los tests miden el delta, no el total.
vi.mock('@/mocks/audit-log', () => ({ mockAuditLog: [] }));

function wrapper({ children }: { children: ReactNode }) {
  return (
    <AuditLogProvider>
      <UsersProvider>
        <SessionProvider>{children}</SessionProvider>
      </UsersProvider>
    </AuditLogProvider>
  );
}

function montarConSesion(role: Parameters<typeof iniciarSesionComo>[0]) {
  iniciarSesionComo(role);
  return renderHook(
    () => ({ log: useAuditLog(), registrar: useRegistrarAuditoria() }),
    { wrapper },
  );
}

const eventoBase = {
  entidadTipo: 'obligacion' as const,
  entidadId: 'obl-1',
  entidadLabel: 'DAE 2026',
  accion: 'actualizado' as const,
  resumen: 'Actualizó la obligación',
};

describe('useRegistrarAuditoria', () => {
  it('firma el evento con el usuario de la sesión', () => {
    const { result } = montarConSesion('admin_empresa');

    act(() => result.current.registrar(eventoBase));

    const entry = result.current.log.entries.at(-1)!;
    expect(entry.actorNombre).toBe('Marcelo Fuentes');
    expect(entry.actorRol).toBe('admin_empresa');
    expect(entry.tenantId).toBe('tenant-1');
  });

  it('hereda el tenant del actor si el evento no lo especifica', () => {
    const { result } = montarConSesion('gestor');
    act(() => result.current.registrar(eventoBase));
    expect(result.current.log.entries.at(-1)!.tenantId).toBe('tenant-2');
  });

  it('permite marcar un evento como de plataforma con tenantId null', () => {
    const { result } = montarConSesion('superadmin');
    act(() => result.current.registrar({ ...eventoBase, entidadTipo: 'tenant', tenantId: null }));
    expect(result.current.log.entries.at(-1)!.tenantId).toBeNull();
  });

  it('no registra nada sin sesión', () => {
    // Preferible un hueco a un evento con "actor desconocido": un log que
    // miente es peor que uno incompleto.
    const { result } = renderHook(() => ({ log: useAuditLog(), registrar: useRegistrarAuditoria() }), { wrapper });

    act(() => result.current.registrar(eventoBase));

    expect(result.current.log.entries).toHaveLength(0);
  });

  it('conserva motivo y aprobación cuando se entregan (RF-32)', () => {
    const { result } = montarConSesion('admin_empresa');

    act(() =>
      result.current.registrar({
        ...eventoBase,
        motivo: 'La balanza no estaba calibrada',
        aprobadoPorId: 'user-interno',
        aprobadoPorNombre: 'Camila Rojas',
      }),
    );

    const entry = result.current.log.entries.at(-1)!;
    expect(entry.motivo).toBe('La balanza no estaba calibrada');
    expect(entry.aprobadoPorNombre).toBe('Camila Rojas');
  });

  it('omite motivo y aprobación cuando no aplican, en vez de dejarlos vacíos', () => {
    const { result } = montarConSesion('admin_empresa');
    act(() => result.current.registrar(eventoBase));

    const entry = result.current.log.entries.at(-1)!;
    expect(entry).not.toHaveProperty('motivo');
    expect(entry).not.toHaveProperty('aprobadoPorId');
  });

  it('genera ids únicos aunque se registre en el mismo milisegundo', () => {
    const { result } = montarConSesion('admin_empresa');

    act(() => {
      result.current.registrar(eventoBase);
      result.current.registrar(eventoBase);
      result.current.registrar(eventoBase);
    });

    const ids = result.current.log.entries.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe('append-only', () => {
  it('el contexto no expone forma de editar ni borrar', () => {
    // RNF-08: el log debe ser inmutable. Aquí solo se garantiza que la
    // aplicación no ofrezca la operación; la garantía real es del backend
    // (tabla sin permisos de UPDATE/DELETE).
    //
    // Se afirma por lo que NO existe y no por la lista exacta: agregar una
    // función de lectura nueva es legítimo y no debería romper el test, pero
    // aparecer un `editar` o un `borrar` sí.
    const { result } = montarConSesion('admin_empresa');
    const claves = Object.keys(result.current.log);

    for (const prohibida of ['editar', 'borrar', 'eliminar', 'actualizar', 'update', 'delete', 'remove']) {
      expect(
        claves.some((k) => k.toLowerCase().includes(prohibida)),
        `el contexto no debe exponer "${prohibida}"`,
      ).toBe(false);
    }
    // La única escritura permitida es añadir.
    expect(claves.filter((k) => /agregar|añadir|registrar/i.test(k))).toEqual(['agregarEntrada']);
  });

  it('registrar nunca reemplaza eventos anteriores', () => {
    const { result } = montarConSesion('admin_empresa');

    act(() => result.current.registrar({ ...eventoBase, resumen: 'Primero' }));
    act(() => result.current.registrar({ ...eventoBase, resumen: 'Segundo' }));

    expect(result.current.log.entries.map((e) => e.resumen)).toEqual(['Primero', 'Segundo']);
  });
});

describe('historialDe', () => {
  it('trae solo los eventos de esa entidad, del más reciente al más antiguo', () => {
    const { result } = montarConSesion('admin_empresa');

    act(() => {
      result.current.registrar({ ...eventoBase, entidadId: 'obl-1', resumen: 'Antiguo' });
      result.current.registrar({ ...eventoBase, entidadId: 'otra', resumen: 'De otra entidad' });
      result.current.registrar({ ...eventoBase, entidadId: 'obl-1', resumen: 'Reciente' });
    });

    const historial = result.current.log.historialDe('obligacion', 'obl-1');
    expect(historial.map((e) => e.resumen)).toEqual(['Reciente', 'Antiguo']);
  });

  it('no confunde entidades distintas con el mismo id', () => {
    const { result } = montarConSesion('admin_empresa');

    act(() => {
      result.current.registrar({ ...eventoBase, entidadTipo: 'obligacion', entidadId: 'x' });
      result.current.registrar({ ...eventoBase, entidadTipo: 'norma', entidadId: 'x' });
    });

    expect(result.current.log.historialDe('norma', 'x')).toHaveLength(1);
  });
});

describe('diffCampos', () => {
  it('solo reporta los campos que cambiaron', () => {
    const cambios = diffCampos({ a: 1, b: 2 }, { a: 1, b: 3 });
    expect(cambios).toEqual([{ campo: 'b', antes: '2', despues: '3' }]);
  });

  it('usa las etiquetas legibles que se le pasan', () => {
    const cambios = diffCampos({ limiteUsuarios: 5 }, { limiteUsuarios: 10 }, { limiteUsuarios: 'Límite de usuarios' });
    expect(cambios[0]!.campo).toBe('Límite de usuarios');
  });

  it('aplica el formateador por campo', () => {
    const cambios = diffCampos(
      { activo: true },
      { activo: false },
      {},
      { activo: (v) => (v ? 'Sí' : 'No') },
    );
    expect(cambios[0]).toEqual({ campo: 'activo', antes: 'Sí', despues: 'No' });
  });

  it('trata null, undefined y cadena vacía como "sin valor"', () => {
    const cambios = diffCampos({ nota: '' }, { nota: 'algo' });
    expect(cambios[0]!.antes).toBeNull();
  });

  it('no reporta arreglos con el mismo contenido aunque sean instancias distintas', () => {
    // Sin comparación estructural, cada render generaría un evento falso.
    expect(diffCampos({ ids: ['a', 'b'] }, { ids: ['a', 'b'] })).toHaveLength(0);
  });

  it('sí reporta cuando el contenido del arreglo cambia', () => {
    expect(diffCampos({ ids: ['a'] }, { ids: ['a', 'b'] })).toHaveLength(1);
  });
});
