import { describe, expect, it } from 'vitest';
import * as compartido from '@ambienta/shared';
import { estadoDe, nombreDeRespaldo, porModulo, type PermisosDelUsuario } from './permisos';

/**
 * Un solo vocabulario de permisos (#217).
 *
 * Medido el 1-sep-2026, la pantalla y la API **no compartían ni una clave**:
 * 13 escritas a mano en `packages/shared` contra los 39 que la guarda
 * verifica. Lo único que había evitado el daño es que la pantalla nunca
 * llegaba a guardar.
 *
 * Estas pruebas son el candado: la primera impide que la segunda lista vuelva
 * a nacer, y el resto cubre la lógica que la pantalla necesita para no
 * inventar nada por su cuenta.
 */

describe('la segunda lista no vuelve', () => {
  /**
   * **La prueba que importa.**
   *
   * No comprueba una función: comprueba que un artefacto **no exista**. Si
   * alguien vuelve a escribir el catálogo a mano en `packages/shared` —que es
   * exactamente lo que pasó— esto se pone rojo el mismo día, y no seis meses
   * después cuando un Admin Empresa descubra que restringir no restringía.
   */
  it.each(['CATALOGO_PERMISOS', 'PermisoSchema', 'PERMISOS_POR_DEFECTO', 'permisosEfectivos', 'nombrePermiso'])(
    'shared NO exporta %s',
    (nombre) => {
      expect(compartido).not.toHaveProperty(nombre);
    },
  );

  it('el catálogo se pide a la API y no se importa de ningún lado', async () => {
    const modulo = await import('./permisos');
    expect(typeof modulo.cargarCatalogo).toBe('function');
    // Si esto dejara de ser cierto, la pantalla tendría una fuente propia otra
    // vez y la divergencia podría empezar de nuevo sin que nadie la note.
    expect(modulo).not.toHaveProperty('CATALOGO');
  });
});

describe('estadoDe distingue los tres casos que no son lo mismo', () => {
  const base: PermisosDelUsuario = {
    user_id: 'u1',
    permisos: [
      { codigo: 'obligation.write', modulo: 'obligation', descripcion: 'Crear obligaciones', origen: 'rol' },
      { codigo: 'audit.read', modulo: 'audit', descripcion: 'Ver auditorías', origen: 'individual' },
    ],
    denegados: ['document.approve'],
  };

  it('lo que viene del rol se marca como del rol', () => {
    expect(estadoDe('obligation.write', base)).toBe('del-rol');
  });

  it('lo concedido aparte se distingue de lo que da el rol', () => {
    // Sin esta distinción no se puede revertir: quitar una excepción y quitar
    // un rol son operaciones distintas contra endpoints distintos.
    expect(estadoDe('audit.read', base)).toBe('concedido');
  });

  it('DENEGADO no es lo mismo que no tenerlo', () => {
    // `document.approve` no aparece en `permisos` —una denegación nunca
    // aparece ahí— pero hay una fila explícita que dice "este no, aunque el
    // rol lo dé". Confundirlos hace que la pantalla ofrezca la acción
    // equivocada.
    expect(estadoDe('document.approve', base)).toBe('denegado');
    expect(estadoDe('inventado.cualquiera', base)).toBe('sin-permiso');
  });

  it('sin datos no afirma que la persona no tenga nada', () => {
    // Un fallo de carga no es "cero permisos". La pantalla usa esto para no
    // dibujar una matriz vacía que se leería como una restricción total.
    expect(estadoDe('obligation.write', null)).toBe('sin-permiso');
  });
});

describe('porModulo agrupa sin reordenar', () => {
  const catalogo = [
    { codigo: 'audit.read', modulo: 'audit', descripcion: 'Ver auditorías' },
    { codigo: 'audit.write', modulo: 'audit', descripcion: 'Editar auditorías' },
    { codigo: 'document.approve', modulo: 'document', descripcion: 'Aprobar documentos' },
  ];

  it('respeta el orden en que llegó de la API', () => {
    // La API ya ordena por módulo y código. Reordenar acá sería que la
    // pantalla empiece a tener criterio propio sobre el catálogo.
    expect(porModulo(catalogo).map((g) => g.modulo)).toEqual(['audit', 'document']);
  });

  it('no pierde ni duplica permisos', () => {
    const total = porModulo(catalogo).flatMap((g) => g.permisos.map((p) => p.codigo));
    expect(total).toEqual(['audit.read', 'audit.write', 'document.approve']);
  });

  it('un catálogo vacío da cero grupos, no un grupo vacío', () => {
    expect(porModulo([])).toEqual([]);
  });
});

describe('nombreDeRespaldo es un respaldo, no un catálogo', () => {
  it('hace legible un código sin descripción', () => {
    expect(nombreDeRespaldo('document.approve')).toBe('Document approve');
  });

  it('no inventa traducciones', () => {
    // Si esto tradujera al castellano, sería la segunda lista otra vez, solo
    // que escondida en una función. El texto de verdad viene de
    // `permissions.description`, y el backend falla si alguna fila no la trae.
    expect(nombreDeRespaldo('legal_matrix.article.evaluate')).toBe('Legal matrix article evaluate');
  });
});
