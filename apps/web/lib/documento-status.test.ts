/**
 * El estado documental dicho con el semáforo de la plataforma.
 *
 * Las dos decisiones de color que se fijan acá no son de gusto: cambian lo que
 * una persona hace al mirar la pantalla.
 */
import { describe, expect, it } from 'vitest';
import {
  SIRVE_COMO_EVIDENCIA,
  TRANSICIONES_REVISION,
  esControlado,
  sirveComoEvidencia,
  tamanoLegible,
  transicionesDesde,
  type EstadoRevision,
} from '@ambienta/shared';
import {
  estadoDocumentoSemaforo,
  estadoRevisionSemaforo,
  etiquetaEstadoDocumento,
  etiquetaEstadoRevision,
} from './documento-status';

describe('el color de una revisión', () => {
  it('sólo la vigente va en verde', () => {
    expect(estadoRevisionSemaforo('vigente')).toBe('vigente');
  });

  it('APROBADA no va en verde', () => {
    /**
     * Aprobada pero sin entrar en vigencia significa que **todavía rige la
     * anterior**. En verde, alguien la descargaría para mostrársela a un
     * fiscalizador y estaría mostrando el documento equivocado.
     *
     * La API dice lo mismo: `SIRVE_COMO_EVIDENCIA` es sólo `vigente`.
     */
    expect(estadoRevisionSemaforo('aprobado')).not.toBe('vigente');
    expect(estadoRevisionSemaforo('aprobado')).not.toBe('cumple');
    expect(sirveComoEvidencia('aprobado')).toBe(false);
  });

  it('OBSOLETA no va en rojo', () => {
    /**
     * Retirar un documento es el final normal de su vida, no un
     * incumplimiento. En rojo, una carpeta con diez años de historial se vería
     * como un desastre y el rojo dejaría de significar algo.
     */
    expect(estadoRevisionSemaforo('obsoleto')).not.toBe('no_cumple');
    expect(estadoRevisionSemaforo('obsoleto')).toBe('na');
  });

  it('todos los estados tienen color y etiqueta', () => {
    const estados: EstadoRevision[] = [
      'borrador',
      'en_revision',
      'aprobado',
      'vigente',
      'obsoleto',
    ];
    for (const e of estados) {
      expect(estadoRevisionSemaforo(e)).toBeTruthy();
      expect(etiquetaEstadoRevision(e)).toBeTruthy();
      // La etiqueta no puede ser el valor crudo: "en_revision" con guión bajo
      // en pantalla delata la tabla de la base.
      expect(etiquetaEstadoRevision(e)).not.toBe(e);
    }
  });
});

describe('el estado del documento entero', () => {
  it('no tiene "aprobado", y por eso se mapea aparte', () => {
    /**
     * `db/18` dejó `documents.status` en cuatro valores. Un documento no está
     * "aprobado": lo está una revisión suya. Mapearlos con la misma función
     * escondería que son dos conjuntos distintos.
     */
    expect(etiquetaEstadoDocumento('vigente')).toBe('Vigente');
    expect(estadoDocumentoSemaforo('vigente')).toBe('vigente');
    expect(estadoDocumentoSemaforo('obsoleto')).toBe('na');
  });

  it('"borrador" en el documento significa que NADA rige', () => {
    // No es lo mismo que una revisión en borrador. Acá quiere decir que el
    // documento existe y no tiene ninguna revisión vigente — o sea que no
    // sirve como evidencia todavía.
    expect(etiquetaEstadoDocumento('borrador')).toBe('Sin nada vigente');
  });

  it('un estado desconocido no rompe la pantalla ni parece vigente', () => {
    expect(estadoDocumentoSemaforo('lo_que_sea')).toBe('pendiente');
    expect(etiquetaEstadoDocumento('lo_que_sea')).toBe('lo_que_sea');
  });
});

describe('la máquina de estados compartida', () => {
  it('obsoleto no tiene salida', () => {
    // Un obsoleto que "revive" deja a quien lo citó sin saber si en ese momento
    // regía. Para volver se emite una revisión nueva.
    expect(transicionesDesde('obsoleto')).toEqual([]);
  });

  it('desde en_revision se puede volver a borrador', () => {
    // La salida que faltaba: sin ella, revisar algo incompleto obliga a
    // aprobarlo igual o a marcarlo obsoleto, y ninguna corresponde.
    expect(transicionesDesde('en_revision')).toContain('borrador');
  });

  it('a vigente sólo se llega desde aprobado', () => {
    const desdeDonde = (Object.keys(TRANSICIONES_REVISION) as EstadoRevision[]).filter(
      (e) => TRANSICIONES_REVISION[e].includes('vigente'),
    );
    expect(desdeDonde).toEqual(['aprobado']);
  });

  it('sólo vigente sirve como evidencia', () => {
    expect(SIRVE_COMO_EVIDENCIA).toEqual(['vigente']);
  });
});

describe('los tipos', () => {
  it('los controlados llevan ciclo de vida y los operativos no', () => {
    expect(esControlado('procedimiento')).toBe(true);
    expect(esControlado('politica')).toBe(true);
    // Aprobar un comprobante que devolvió un portal del Estado no tiene sentido.
    expect(esControlado('receipt')).toBe(false);
    expect(esControlado('evidence')).toBe(false);
  });
});

describe('el tamaño legible', () => {
  it('usa las unidades del explorador de archivos', () => {
    expect(tamanoLegible(512)).toBe('512 B');
    expect(tamanoLegible(2048)).toBe('2.0 KB');
    expect(tamanoLegible(5 * 1024 * 1024)).toBe('5.0 MB');
  });

  it('no revienta con basura', () => {
    expect(tamanoLegible(Number.NaN)).toBe('—');
    expect(tamanoLegible(-1)).toBe('—');
  });
});
