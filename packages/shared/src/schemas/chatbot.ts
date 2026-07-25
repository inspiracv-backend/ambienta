import { z } from 'zod';

export const ChatMessageSchema = z.object({
  id: z.string(),
  role: z.enum(['user', 'assistant']),
  contenido: z.string(),
  fecha: z.string(),
  citaNormId: z.string().optional(),
});
export type ChatMessage = z.infer<typeof ChatMessageSchema>;
