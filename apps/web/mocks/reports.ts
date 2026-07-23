/**
 * Datos de ejemplo para Reportes y ejemplos de conversación del Chatbot
 * (Secciones M y K, pendientes en esta iteración). Se deja el mínimo
 * necesario para que esas secciones no dupliquen la estructura al
 * implementarse.
 */
export interface ReportTemplate {
  id: string;
  tipo: 'Cumplimiento' | 'No Conformidades' | 'Matriz Legal';
  nombre: string;
}

export const mockReportTemplates: ReportTemplate[] = [
  { id: 'report-1', tipo: 'Cumplimiento', nombre: 'Reporte de cumplimiento trimestral' },
  { id: 'report-2', tipo: 'No Conformidades', nombre: 'Reporte de no conformidades abiertas' },
];

export interface ChatbotExchange {
  id: string;
  pregunta: string;
  respuesta: string;
}

export const mockChatbotExamples: ChatbotExchange[] = [
  {
    id: 'chat-1',
    pregunta: '¿Cuándo vence la próxima declaración SIDREP?',
    respuesta: 'La declaración SIDREP Q3 2026 de Planta Rancagua vence en 6 días.',
  },
];
