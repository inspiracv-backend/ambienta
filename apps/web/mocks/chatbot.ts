export interface ChatbotQA {
  keywords: string[];
  respuesta: string;
  citaNormId?: string;
}

/**
 * Base de conocimiento mock (RF-55) para el chatbot tenant-aware: solo datos
 * del tenant + normativa pública. Integración real: reemplazar por LangGraph
 * + embeddings via apps/ai-service cuando exista spec de API aprobada.
 */
export const mockChatbotQA: ChatbotQA[] = [
  {
    keywords: ['sidrep', 'próximo vencimiento', 'proximo vencimiento'],
    respuesta: 'La declaración SIDREP Q3 2026 de Planta Rancagua está por vencer. Revisa el detalle en Obligaciones.',
  },
  {
    keywords: ['ley rep', 'rep'],
    respuesta: 'La Ley 20.920 (Ley REP) establece metas de recolección y valorización para productores. Tu tenant tiene un 67% de cumplimiento en esta norma.',
    citaNormId: 'norm-1',
  },
  {
    keywords: ['rca', 'rancagua'],
    respuesta: 'La RCA de Planta Rancagua N° 145/2019 exige mantener un plan de manejo de residuos peligrosos vigente.',
    citaNormId: 'norm-2',
  },
  {
    keywords: ['iso 14001', 'iso'],
    respuesta: 'La ISO 14001:2015 (Sistema de Gestión Ambiental) tiene un 67% de cumplimiento en tu tenant. El artículo pendiente es la cláusula 9.1 (seguimiento y medición).',
    citaNormId: 'norm-3',
  },
];

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
