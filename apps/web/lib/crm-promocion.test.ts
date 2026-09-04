/**
 * Cuándo se puede promover un trato ganado a contrato, y cuándo no (#82).
 *
 * ## Por qué este archivo existe aparte
 *
 * La primera versión de `sePuedePromover` exigía que la empresa **ya tuviera**
 * `client_tenant_id`, y era exactamente al revés: promover es lo que lo fija
 * (`services/crm.py::promover_a_contrato`). Con esa condición el botón se
 * escondía justo en el caso para el que existe —un prospecto al que se le acaba
 * de ganar el trato— y aparecía solo donde ya no hacía falta.
 *
 * No fallaba nada. La acción simplemente no estaba, y quien la buscara habría
 * concluido que el sistema no la tiene. Estas pruebas fijan la condición real,
 * que es la etapa.
 */
import { describe, expect, it } from 'vitest';
import {
  contratosCompatibles,
  mapContratoParaPromover,
  motivoParaNoPromover,
  sePuedePromover,
  type ContratoParaPromover,
  type EmpresaCrm,
  type EtapaCrm,
  type TratoCrm,
} from './crm';

const GANADO: EtapaCrm = { id: 'e-won', codigo: 'won', nombre: 'Ganado', posicion: 3, tipo: 'won' };
const ABIERTA: EtapaCrm = { id: 'e-neg', codigo: 'neg', nombre: 'Negociación', posicion: 2, tipo: 'open' };
const PERDIDO: EtapaCrm = { id: 'e-lost', codigo: 'lost', nombre: 'Perdido', posicion: 4, tipo: 'lost' };

function trato(extra: Partial<TratoCrm> = {}): TratoCrm {
  return {
    id: 't-1',
    empresaId: 'c-1',
    contactoId: null,
    etapaId: GANADO.id,
    titulo: 'Implantación matriz legal',
    monto: 1500000,
    moneda: 'CLP',
    responsableId: null,
    cierreEstimado: '2026-10-01',
    cerradoEn: '2026-09-03T12:00:00Z',
    motivoPerdida: null,
    contratoId: null,
    ...extra,
  };
}

function empresa(extra: Partial<EmpresaCrm> = {}): EmpresaCrm {
  return {
    id: 'c-1',
    nombre: 'Constructora del Sur SpA',
    rut: null,
    rubro: null,
    sitioWeb: null,
    clienteTenantId: null,
    estado: 'prospect',
    responsableId: null,
    notas: null,
    ...extra,
  };
}

describe('sePuedePromover', () => {
  it('un prospecto SIN tenant en la plataforma sí se puede promover', () => {
    // La afirmación que este archivo existe para proteger. Es el caso normal:
    // se gana el trato de alguien que todavía no es cliente, y promover es lo
    // que lo convierte en uno.
    expect(sePuedePromover(trato(), GANADO)).toBe(true);
  });

  it('un trato que no está ganado, no', () => {
    expect(sePuedePromover(trato({ etapaId: ABIERTA.id }), ABIERTA)).toBe(false);
    expect(sePuedePromover(trato({ etapaId: PERDIDO.id }), PERDIDO)).toBe(false);
  });

  it('un trato ya enlazado a un contrato, tampoco', () => {
    expect(sePuedePromover(trato({ contratoId: 'k-1' }), GANADO)).toBe(false);
  });

  it('sin saber la etapa no se ofrece', () => {
    // Ofrecerlo a ciegas daría un 409 que se lee como que el sistema falló.
    expect(sePuedePromover(trato(), null)).toBe(false);
  });
});

describe('motivoParaNoPromover', () => {
  it('cuando sí se puede, no hay motivo que dar', () => {
    expect(motivoParaNoPromover(trato(), GANADO)).toBeNull();
  });

  it('el motivo nombra la etapa en la que está, no dice solo «no se puede»', () => {
    // Sin el nombre, quien lo lee tiene que ir a buscar en qué columna está.
    const motivo = motivoParaNoPromover(trato({ etapaId: ABIERTA.id }), ABIERTA);
    expect(motivo).toContain('Negociación');
  });

  it('un trato ya promovido explica que el enlace anterior se perdería', () => {
    const motivo = motivoParaNoPromover(trato({ contratoId: 'k-1' }), GANADO);
    expect(motivo).toContain('ya está enlazado');
  });

  it('«ya promovido» gana sobre «no ganado»: es el hecho más concreto', () => {
    const motivo = motivoParaNoPromover(
      trato({ contratoId: 'k-1', etapaId: ABIERTA.id }),
      ABIERTA,
    );
    expect(motivo).toContain('ya está enlazado');
  });
});

describe('contratosCompatibles', () => {
  const contratos: ContratoParaPromover[] = [
    { id: 'k-1', numero: 'C-001', titulo: 'Asesoría anual', clienteTenantId: 't-A', estado: 'active' },
    { id: 'k-2', numero: 'C-002', titulo: 'Auditoría', clienteTenantId: 't-B', estado: 'active' },
  ];

  it('una ficha sin tenant asociado puede enlazar con cualquiera', () => {
    // Es el caso del prospecto: el servidor no tiene con qué compararlo, así
    // que filtrar acá escondería opciones que sí funcionan.
    expect(contratosCompatibles(empresa(), contratos)).toHaveLength(2);
  });

  it('una ficha que ya nombra a un cliente solo ve los contratos de ese cliente', () => {
    // El servidor responde 409 con los otros (`ClienteDistinto`). Ofrecerlos
    // sería ofrecer una opción que falla.
    const soloA = contratosCompatibles(empresa({ clienteTenantId: 't-A' }), contratos);
    expect(soloA.map((c) => c.id)).toEqual(['k-1']);
  });

  it('si ninguno corresponde, la lista queda vacía en vez de caer al primero', () => {
    expect(contratosCompatibles(empresa({ clienteTenantId: 't-Z' }), contratos)).toEqual([]);
  });
});

describe('mapContratoParaPromover', () => {
  it('lee los campos que el selector muestra', () => {
    const c = mapContratoParaPromover({
      id: 'k-1',
      contract_number: 'C-001',
      title: 'Asesoría anual',
      client_tenant_id: 't-A',
      status: 'active',
    });
    expect(c).toEqual({
      id: 'k-1',
      numero: 'C-001',
      titulo: 'Asesoría anual',
      clienteTenantId: 't-A',
      estado: 'active',
    });
  });
});
