import { z } from 'zod';

/**
 * Validación de variables de entorno al arranque (CLAUDE.md regla 3:
 * "Validación automática desde el contrato — Zod / class-validator").
 *
 * El proceso NO arranca si falta o es inválida una variable requerida —
 * es preferible fallar en el arranque con un mensaje claro que descubrir
 * la falta de configuración a mitad de una request en producción.
 */
export const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  PORT: z.coerce.number().int().positive().default(3001),

  /** URL de conexión a PostgreSQL. Requerida: sin base de datos la API no tiene sentido. */
  DATABASE_URL: z.string().url(),

  /** URL de conexión a Redis (colas y cache del worker). */
  REDIS_URL: z.string().url(),

  /** Orígenes permitidos por CORS, separados por coma (ej. "http://localhost:3000"). */
  CORS_ORIGINS: z
    .string()
    .default('http://localhost:3000')
    .transform((value) => value.split(',').map((origin) => origin.trim()).filter(Boolean)),

  /**
   * Secreto de firma de JWT. Mínimo 32 caracteres para que no sea trivialmente
   * atacable por fuerza bruta. Requerido incluso hoy que el módulo de auth aún
   * no existe, para que ningún entorno se despliegue sin él configurado.
   */
  JWT_SECRET: z.string().min(32, 'JWT_SECRET debe tener al menos 32 caracteres'),

  /**
   * Credenciales OAuth — OPCIONALES a propósito. Mientras no existan, el módulo
   * de auth no registra esas estrategias y los endpoints devuelven 501
   * (ver openspec/changes/sistema-actores-roles-rbac/design.md).
   */
  MICROSOFT_CLIENT_ID: z.string().optional(),
  MICROSOFT_CLIENT_SECRET: z.string().optional(),
  GOOGLE_CLIENT_ID: z.string().optional(),
  GOOGLE_CLIENT_SECRET: z.string().optional(),

  /** Proveedor de correo (Resend, decisión cerrada #18 del Análisis Funcional v1.7). */
  RESEND_API_KEY: z.string().optional(),
});

export type Env = z.infer<typeof envSchema>;

/** Se pasa a `ConfigModule.forRoot({ validate })`. */
export function validateEnv(raw: Record<string, unknown>): Env {
  const result = envSchema.safeParse(raw);

  if (!result.success) {
    const detalle = result.error.issues
      .map((issue) => `  - ${issue.path.join('.')}: ${issue.message}`)
      .join('\n');
    throw new Error(`Configuración de entorno inválida:\n${detalle}`);
  }

  return result.data;
}
