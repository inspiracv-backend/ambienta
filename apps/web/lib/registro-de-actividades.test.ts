import { describe, expect, it } from 'vitest';
import { entradaDesdeLaApi, type FilaDelRegistro } from './registro-de-actividades';

/** Una fila de `audit_log` traducida a lo que la pantalla del registro muestra. */

function fila(over: Partial<FilaDelRegistro>): FilaDelRegistro {
  return {
    id: 1,
    tenant_id: 't1',
    occurred_at: '2026-09-21T15:00:00Z',
    actor_user_id: 'u1',
    actor_nombre: 'Marcelo Fuentes',
    action: 'update',
    entity_type: 'obligations',
    entity_id: 'a0000021-0000-0000-0000-000000000003',
    reason: null,
    before_data: null,
    after_data: null,
    ...over,
  };
}

describe('la traduccion de una fila del registro', () => {
  it('una modificacion dice que campos cambiaron, con el antes y el despues', () => {
    const e = entradaDesdeLaApi(
      fila({ before_data: { status: 'open' }, after_data: { status: 'submitted', title: 'RETC 2026' } }),
    );

    expect(e.entidadTipo).toBe('obligacion');
    expect(e.accion).toBe('actualizado');
    expect(e.entidadLabel).toBe('RETC 2026');
    expect(e.cambios).toContainEqual({ campo: 'status', antes: 'open', despues: 'submitted' });
    expect(e.resumen).toMatch(/^Modificó /);
  });

  it('la emision de un documento se lee como tal', () => {
    const e = entradaDesdeLaApi(
      fila({
        action: 'download',
        entity_type: 'audits',
        after_data: { documento: 'informe_de_auditoria', titulo: 'Informe AUD-2026-001', formato: 'pdf', filas: 5 },
      }),
    );

    expect(e.accion).toBe('exportado');
    expect(e.entidadTipo).toBe('auditoria');
    expect(e.resumen).toBe('Emitió "Informe AUD-2026-001" (PDF, 5 filas)');
  });

  it('una tabla que la pantalla no conoce se muestra igual, como otro', () => {
    // Un evento que no se muestra es lo que un registro de auditoria no puede hacer.
    const e = entradaDesdeLaApi(fila({ entity_type: 'notification_rules', entity_id: 'abcdef12-0000' }));

    expect(e.entidadTipo).toBe('otro');
    expect(e.entidadLabel).toBe('notification_rules abcdef12');
  });

  it('sin actor es el sistema; con actor y sin nombre, alguien de otra empresa', () => {
    expect(entradaDesdeLaApi(fila({ actor_user_id: null, actor_nombre: null })).actorNombre).toBe('Sistema');
    expect(entradaDesdeLaApi(fila({ actor_nombre: null })).actorNombre).toBe('Persona de otra empresa');
  });

  it('las filas de la empresa de la plataforma son de plataforma para el Admin Global', () => {
    expect(entradaDesdeLaApi(fila({ tenant_id: 'plat' }), { tenantDePlataforma: 'plat' }).tenantId).toBeNull();
    expect(entradaDesdeLaApi(fila({ tenant_id: 't1' }), { tenantDePlataforma: 'plat' }).tenantId).toBe('t1');
  });

  it('el id no choca con los del historial de la sesion', () => {
    expect(entradaDesdeLaApi(fila({ id: 42 })).id).toBe('servidor-42');
  });
});
