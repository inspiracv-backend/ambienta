/**
 * Configurar el pipeline sin que la pantalla ofrezca lo que el servidor rechaza.
 *
 * Las dos reglas que `services/crm.py::comprobar_cambio_de_etapa` impone viven
 * también acá, y eso normalmente sería duplicar lógica de negocio — que es
 * justo lo que el resto de este módulo evita. La diferencia: **acá no son la
 * barrera**. El servidor responde 409 igual, y estas funciones existen para no
 * mostrar un botón que va a fallar y para explicar la salida antes de que
 * alguien la busque probando.
 *
 * Si alguna vez se separan, lo que gana es el servidor. Lo que se pierde acá es
 * cortesía; lo que se perdería allá es la integridad del pipeline.
 */
import { describe, expect, it } from 'vitest';
import {
  TIPO_DE_ETAPA,
  codigoDeEtapa,
  motivoParaNoRetirarEtapa,
  nombreDelResponsable,
  type EtapaCrm,
} from './crm';

function etapa(extra: Partial<EtapaCrm> & { id: string }): EtapaCrm {
  return {
    codigo: extra.id,
    nombre: 'Etapa',
    posicion: 0,
    tipo: 'open',
    ...extra,
  };
}

const PIPELINE: EtapaCrm[] = [
  etapa({ id: 'e1', nombre: 'Prospecto', tipo: 'open', posicion: 0 }),
  etapa({ id: 'e2', nombre: 'Propuesta', tipo: 'open', posicion: 1 }),
  etapa({ id: 'e3', nombre: 'Ganado', tipo: 'won', posicion: 2 }),
  etapa({ id: 'e4', nombre: 'Perdido', tipo: 'lost', posicion: 3 }),
];

describe('motivoParaNoRetirarEtapa', () => {
  it('una etapa vacía y con hermanas de su tipo se puede retirar', () => {
    expect(motivoParaNoRetirarEtapa(PIPELINE[0], PIPELINE, 0)).toBeNull();
  });

  it('con tratos dentro no, y el motivo dice CUÁNTOS', () => {
    // El número importa porque la salida es moverlos: sin saber cuántos son no
    // se puede decidir si vale la pena.
    const motivo = motivoParaNoRetirarEtapa(PIPELINE[0], PIPELINE, 7);
    expect(motivo).toContain('7');
    expect(motivo).toContain('Muévelas');
  });

  it('un solo trato se dice en singular', () => {
    expect(motivoParaNoRetirarEtapa(PIPELINE[0], PIPELINE, 1)).toContain('1 oportunidad ');
  });

  it('la última de su tipo no, aunque esté vacía', () => {
    // `Ganado` es la única `won`: sin ella no se puede promover a contrato.
    const motivo = motivoParaNoRetirarEtapa(PIPELINE[2], PIPELINE, 0);
    expect(motivo).toContain(TIPO_DE_ETAPA.won);
  });

  it('y el motivo ofrece la salida real: renombrarla', () => {
    // Sin eso, la única lectura posible es que el sistema no deja configurar
    // el pipeline — cuando lo que no deja es quedarse sin una de cada tipo.
    expect(motivoParaNoRetirarEtapa(PIPELINE[2], PIPELINE, 0)).toContain('renombrar');
  });

  it('«tiene tratos» gana sobre «es la última»: es lo que se puede arreglar hoy', () => {
    const motivo = motivoParaNoRetirarEtapa(PIPELINE[2], PIPELINE, 3);
    expect(motivo).toContain('3');
  });
});

describe('codigoDeEtapa', () => {
  it('deriva un identificador del nombre', () => {
    expect(codigoDeEtapa('Visita técnica')).toBe('visita_tecnica');
  });

  it('los acentos se quitan, no se pierden con la letra', () => {
    // `ñ` → `n` es lo que se espera de un identificador; dejar la letra fuera
    // daría `maana` para «mañana».
    expect(codigoDeEtapa('Órdenes de mañana')).toBe('ordenes_de_manana');
  });

  it('un nombre que ya existe se numera en vez de chocar', () => {
    // Hay índice único por `(tenant_id, code)`: sin esto la segunda etapa
    // respondería 409 hablando de una columna que la persona no sabe que hay.
    expect(codigoDeEtapa('Propuesta', ['propuesta'])).toBe('propuesta_2');
    expect(codigoDeEtapa('Propuesta', ['propuesta', 'propuesta_2'])).toBe('propuesta_3');
  });

  it('un nombre sin nada utilizable devuelve vacío, y no un código raro', () => {
    // La pantalla no deja guardar con esto. Mandar `___` o `` sería que la
    // base lo rechace por una razón que no se parece a la causa.
    expect(codigoDeEtapa('¿?!')).toBe('');
    expect(codigoDeEtapa('   ')).toBe('');
  });

  it('no se pasa del largo de la columna', () => {
    expect(codigoDeEtapa('a'.repeat(120)).length).toBeLessThanOrEqual(40);
  });
});

describe('nombreDelResponsable', () => {
  const personas = [{ id: 'u1', nombre: 'Carla Miranda' }];

  it('sin responsable lo dice', () => {
    expect(nombreDelResponsable(null, personas)).toBe('Sin responsable');
  });

  it('con responsable da su nombre', () => {
    expect(nombreDelResponsable('u1', personas)).toBe('Carla Miranda');
  });

  it('un responsable que no está en la lista NO se muestra como «sin responsable»', () => {
    // Son cosas distintas: alguien está a cargo y no sabemos quién, contra
    // nadie está a cargo. La segunda es la que hay que repartir; confundirlas
    // haría reasignar tratos que ya tienen dueño.
    expect(nombreDelResponsable('u9', personas)).toBe('Responsable desconocido');
  });
});
