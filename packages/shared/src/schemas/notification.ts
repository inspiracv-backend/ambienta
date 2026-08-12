import { z } from 'zod';
import { SistemaDeclaracionSchema } from './obligation';

export const UrgenciaSchema = z.enum(['baja', 'media', 'alta']);
export type Urgencia = z.infer<typeof UrgenciaSchema>;

export const NotificationSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  userId: z.string(),
  urgencia: UrgenciaSchema,
  titulo: z.string(),
  mensaje: z.string(),
  leida: z.boolean(),
  fecha: z.string(),
  obligationId: z.string().optional(),
});
export type Notification = z.infer<typeof NotificationSchema>;

/** RF-30 a RF-33: preferencias de canal y anticipación de recordatorios, por usuario. */
export const NotificationPreferencesSchema = z.object({
  userId: z.string(),
  canalEmail: z.boolean(),
  canalInApp: z.boolean(),
  anticipacionDias: z.array(z.number()),
});
export type NotificationPreferences = z.infer<typeof NotificationPreferencesSchema>;

/** RF-22/RF-23: al menos 2 pestañas (matriz de códigos + hoja de declaraciones). */
export const ExcelTemplateSchema = z.object({
  id: z.string(),
  sistema: SistemaDeclaracionSchema,
  nombre: z.string(),
  version: z.string(),
  pestanas: z.array(z.string()).min(2),
  archivoUrl: z.string(),
});
export type ExcelTemplate = z.infer<typeof ExcelTemplateSchema>;
