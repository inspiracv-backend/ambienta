export interface ChatbotQA {
  keywords: string[];
  respuesta: string;
  citaNormId?: string;
}

/**
 * **La base de ejemplo del chatbot de empresa se fue.** Esa pantalla ya
 * pregunta al asistente de verdad a traves de `/support/chatbot/consulta`
 * (RF-59 a RF-63); dejar aqui su lista de palabras clave diria que todavia
 * responde con ellas — y alguien lo creeria antes que al codigo.
 *
 * Queda la privilegiada: lo que se pregunta ahi son metricas de la plataforma
 * y la base de conocimiento del AI Service es normativa y datos de una
 * empresa. Pendiente de su lado.
 */

/** Base de conocimiento mock para el chatbot privilegiado (RF-53), solo Superadmin. */
export const mockPrivilegedQA: ChatbotQA[] = [
  {
    keywords: ['cuántos tenant', 'cuantos tenant', 'empresas activas'],
    respuesta: 'Actualmente hay 2 tenants en la plataforma: Recicladora del Sur SpA y Veolia Ambiental Chile.',
  },
  {
    keywords: ['gestor'],
    respuesta: 'Hay 1 tenant configurado como Gestor: Veolia Ambiental Chile, con 2 clientes (sub-tenants) registrados.',
  },
];
