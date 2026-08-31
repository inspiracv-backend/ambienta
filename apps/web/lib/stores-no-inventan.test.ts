/**
 * Que ningun store arranque con datos de ejemplo (#208).
 *
 * ## El defecto
 *
 * Los once stores inicializaban su estado con `mockX`:
 *
 *     const [obligations, setObligations] = useState<Obligation[]>(mockObligations);
 *
 * Combinado con `.catch(() => {})`, eso significa que **si la peticion falla en
 * la primera carga, la pantalla queda mostrando registros inventados** con
 * `loading = false`: indistinguibles de los reales.
 *
 * Un arreglo anterior (#208, primera parte) quito el `if (mapped.length > 0)`
 * de tres stores, para que cero filas se escribieran como cero. Pero el estado
 * **inicial** seguia siendo el de ejemplo, asi que el caso "no se pudo
 * preguntar" seguia mostrando obligaciones, auditorias y no conformidades que
 * nadie creo.
 *
 * En este dominio el dano es concreto: quien ve "Obligacion vigente" asume que
 * la empresa la tiene cubierta.
 *
 * ## Por que esta prueba lee el codigo
 *
 * Es la unica forma de afirmarlo sobre **todos** los stores a la vez. Montar
 * once providers y comprobar su estado inicial exigiria once andamiajes y no
 * cubriria el que alguien agregue manana. Un store nuevo que arranque con datos
 * de ejemplo cae aca sin que nadie tenga que acordarse.
 *
 * Y hay **una excepcion declarada**: `users-store`. Sus datos de ejemplo no son
 * registros inventados sobre la empresa, son la **fuente de identidad** del modo
 * sin Clerk — `SessionProvider` resuelve quien eres buscando ahi el id que el
 * DevRoleSwitcher guardo en `localStorage`. Vaciarlo no arregla nada: quita el
 * mecanismo de autenticacion de desarrollo. Medido: al vaciarlo, **77 pruebas**
 * de doce archivos caen, porque ninguna puede iniciar sesion.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const CARPETA = join(__dirname);

/**
 * El unico store que conserva datos de ejemplo, con su motivo.
 *
 * Va como lista y no como un comentario suelto para que agregar otro sea un
 * cambio visible en la revision, y no algo que se cuela.
 */
const EXCEPCIONES: Record<string, string> = {
  'users-store.tsx':
    'es la fuente de identidad del modo sin Clerk: SessionProvider resuelve la ' +
    'sesion buscando aca el id que el DevRoleSwitcher guarda en localStorage',
};

function stores(): string[] {
  return readdirSync(CARPETA).filter((f) => f.endsWith('-store.tsx'));
}

describe('ningun store arranca con datos de ejemplo', () => {
  it('hay stores que revisar', () => {
    // Sin esto, la comprobacion de abajo pasaria por estar vacia el dia que
    // alguien mueva los stores de carpeta.
    expect(stores().length).toBeGreaterThanOrEqual(10);
  });

  it('ninguno usa `useState(mockX)` como estado inicial', () => {
    const culpables: string[] = [];

    for (const archivo of stores()) {
      if (archivo in EXCEPCIONES) continue;
      const codigo = readFileSync(join(CARPETA, archivo), 'utf8');
      // `useState<Tipo>(mockAlgo)` en cualquiera de sus formas.
      const usos = codigo.match(/useState<[^>]*>\(\s*mock[A-Z]\w*\s*\)/g);
      if (usos) culpables.push(`${archivo}: ${usos.join(', ')}`);
    }

    expect(culpables).toEqual([]);
  });

  it('la excepcion declarada sigue existiendo', () => {
    // Si `users-store` desaparece o deja de necesitar la excepcion, esta
    // prueba avisa en vez de dejar una exclusion muerta que tape un store
    // nuevo con el mismo nombre.
    for (const archivo of Object.keys(EXCEPCIONES)) {
      expect(stores(), `${archivo} ya no existe: sobra su excepcion`).toContain(
        archivo,
      );
    }
  });

  it('cada excepcion explica por que', () => {
    // Una lista de exclusiones sin motivo se llena sola.
    for (const [archivo, motivo] of Object.entries(EXCEPCIONES)) {
      expect(motivo.length, `${archivo} sin motivo`).toBeGreaterThan(40);
    }
  });
});

/**
 * Stores que **no consultan nada**, con su motivo. Un store sin peticion no
 * puede informar de un fallo de red, asi que exigirle `errorDeCarga` seria
 * pedirle que mienta al reves.
 */
const SIN_PETICION: Record<string, string> = {
  'toast-store.tsx':
    'no es un store de datos: es el mecanismo de avisos de la interfaz y no '+
    'hace ninguna peticion. Cae en el glob por el nombre, nada mas',
  'audit-log-store.tsx':
    'no le pregunta nada a la API: `entries` solo se llena con lo que ocurre ' +
    'en esta sesion del navegador. `GET /audit-log/` existe y nadie lo llama, ' +
    'que es trabajo aparte',
  'users-store.tsx':
    'es la fuente de identidad del modo sin Clerk; su carga tiene su propio ' +
    'camino y no comparte la forma de los demas',
};

describe('un fallo de carga se puede distinguir de "no hay nada"', () => {
  it('cada store que consulta expone `errorDeCarga`', () => {
    // Sin esto la pantalla dice "no hay obligaciones" cuando la verdad es "no
    // se pudo preguntar" — la misma mentira de #208 en su otra forma, solo que
    // mas dificil de ver porque una lista vacia parece un estado legitimo.
    const mudos: string[] = [];

    for (const archivo of stores()) {
      if (archivo in SIN_PETICION) continue;
      const codigo = readFileSync(join(CARPETA, archivo), 'utf8');
      if (!codigo.includes('errorDeCarga')) mudos.push(archivo);
    }

    expect(mudos).toEqual([]);
  });

  it('y ninguno se traga el error con un `catch` vacío', () => {
    // `.catch(() => {})` en la carga es exactamente como se veía el defecto.
    const tragones: string[] = [];

    for (const archivo of stores()) {
      if (archivo in SIN_PETICION) continue;
      const codigo = readFileSync(join(CARPETA, archivo), 'utf8');
      // Solo el de la carga: el que va seguido del `.finally` que apaga
      // `loading`. Los `.catch` de las escrituras son otra cosa.
      if (/\.catch\(\(\) => \{\}\)\s*\.finally\(/.test(codigo)) {
        tragones.push(archivo);
      }
    }

    expect(tragones).toEqual([]);
  });

  it('cada excepción explica por qué', () => {
    for (const [archivo, motivo] of Object.entries(SIN_PETICION)) {
      expect(motivo.length, `${archivo} sin motivo`).toBeGreaterThan(40);
      expect(stores(), `${archivo} ya no existe`).toContain(archivo);
    }
  });
});
