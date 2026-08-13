import { z } from 'zod';
import { ModuloPlataformaSchema } from './tenant';

/**
 * Lo que puede vivir dentro de `tenants.settings`.
 *
 * `settings` es un jsonb, asi que la base acepta cualquier cosa. Sin un esquema
 * declarado se convierte en un cajon: tres pantallas escriben claves distintas,
 * nadie sabe que contiene, y no hay forma de validarlo ni de documentarlo.
 *
 * Este archivo es ese contrato. Vive en `packages/shared` porque lo necesitan
 * los dos lados: el frontend para leer y escribir, y quien revise la base para
 * saber que esperar.
 *
 * **No es un modelo definitivo.** Estos tres campos estan aqui porque todavia
 * estan tomando forma y no justifican una migracion por cada ajuste. Cuando
 * alguno se estabilice, merece columna propia: un jsonb no se puede indexar ni
 * restringir como una columna, y `limiteUsuarios` es justo la clase de dato
 * sobre el que algun dia se va a querer consultar.
 */
export const TenantSettingsSchema = z.object({
  /** Tope de usuarios del contrato. */
  limiteUsuarios: z.number().int().positive().optional(),
  /** Modulos habilitados para la empresa. */
  modulosActivos: z.array(ModuloPlataformaSchema).optional(),
  /** URL del logo que se muestra en la cabecera. */
  logoUrl: z.string().url().optional(),
});

export type TenantSettings = z.infer<typeof TenantSettingsSchema>;

/** El valor que se usa cuando la empresa no tiene fijado un tope propio. */
export const LIMITE_USUARIOS_POR_DEFECTO = 50;

/**
 * Lee `settings` sin confiar en su forma.
 *
 * La base puede tener empresas creadas antes de que este esquema existiera, o
 * con claves que alguien escribio a mano. **Una clave invalida no debe tumbar
 * la carga de la empresa entera**: se descarta lo que no calza y se conserva lo
 * que si, que es lo que permite ir migrando sin un big bang.
 */
export function leerTenantSettings(crudo: unknown): TenantSettings {
  if (!crudo || typeof crudo !== 'object' || Array.isArray(crudo)) return {};

  const resultado: TenantSettings = {};
  const entrada = crudo as Record<string, unknown>;

  for (const [clave, esquema] of Object.entries(TenantSettingsSchema.shape)) {
    if (!(clave in entrada)) continue;
    const analisis = esquema.safeParse(entrada[clave]);
    if (analisis.success) {
      (resultado as Record<string, unknown>)[clave] = analisis.data;
    }
  }
  return resultado;
}
