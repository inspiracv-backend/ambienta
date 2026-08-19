import { api } from '@/lib/api-client';

/**
 * El sector y el tamano de la empresa: de donde sale su normativa aplicable.
 *
 * ## Por que el sector no es el giro
 *
 * La pantalla ya tenia un campo "sector", pero era texto libre y viajaba a
 * `business_activity` — el giro. Sirve para mostrarlo en una ficha y para nada
 * mas: dos empresas de la misma industria escriben "mineria" y "Minería del
 * cobre" y ninguna consulta las agrupa.
 *
 * `sectors` es el catalogo CIIU, con codigo estable. Es contra el que estan
 * clasificadas las normas (`norm_sectors`), asi que **es el unico campo que
 * decide que le aplica a una empresa**. El giro se queda: describe a que se
 * dedica, y eso tambien hace falta.
 */

/** Tramo por tamano. Los codigos son los que acepta el CHECK de la base. */
export const TRAMOS = [
  { valor: 'micro', label: 'Micro', detalle: 'hasta 9 trabajadores' },
  { valor: 'pequena', label: 'Pequeña', detalle: '10 a 49 trabajadores' },
  { valor: 'mediana', label: 'Mediana', detalle: '50 a 199 trabajadores' },
  { valor: 'grande', label: 'Grande', detalle: '200 o más trabajadores' },
] as const;

export type Tramo = (typeof TRAMOS)[number]['valor'];

const VALORES: readonly string[] = TRAMOS.map((t) => t.valor);

/**
 * Lee un tramo sin confiar en su valor.
 *
 * La columna acepta `NULL` —una empresa creada antes de que este campo
 * existiera no tiene tramo— y eso **no es un error que haya que esconder**: es
 * lo que hace que el perfil aparezca incompleto y alguien lo complete.
 */
export function leerTramo(crudo: unknown): Tramo | null {
  return typeof crudo === 'string' && VALORES.includes(crudo) ? (crudo as Tramo) : null;
}

export function etiquetaDeTramo(tramo: Tramo | null): string {
  return TRAMOS.find((t) => t.valor === tramo)?.label ?? 'Sin definir';
}

export interface Sector {
  id: number;
  codigo: string;
  nombre: string;
}

function mapearSector(raw: Record<string, unknown>): Sector {
  return {
    id: Number(raw.id),
    codigo: String(raw.code ?? ''),
    nombre: String(raw.name ?? ''),
  };
}

/**
 * El catalogo CIIU. Es global y no cambia, asi que se pide una vez por sesion.
 *
 * **Falla en silencio a proposito.** Si el catalogo no carga, el selector queda
 * vacio y la empresa se crea sin sector — que es exactamente lo que ya pasa hoy
 * con las empresas antiguas, y el sistema sabe representarlo: la matriz dice
 * `sin_perfil` en vez de inventar normativa. Un modal que se cae porque no pudo
 * leer un catalogo de referencia seria peor.
 */
let pendiente: Promise<Sector[]> | null = null;

export function cargarSectores(): Promise<Sector[]> {
  if (!pendiente) {
    pendiente = api
      .get<Record<string, unknown>[]>('/catalog/sectors')
      .then((filas) => filas.map(mapearSector))
      .catch(() => {
        // No se cachea el fallo: al abrir el modal de nuevo hay que reintentar,
        // no quedar sin sectores por un error de red de hace diez minutos.
        pendiente = null;
        return [];
      });
  }
  return pendiente;
}

/** Solo para las pruebas: vacia el cache entre casos. */
export function olvidarSectores(): void {
  pendiente = null;
}
