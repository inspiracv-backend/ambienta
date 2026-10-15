import type { CitaDelAsistente } from '@/lib/chatbot';

/** Lo que el panel necesita mostrar de una respuesta, venga de donde venga. */
export interface RespuestaMostrable {
  texto: string;
  /** El hilo al que pertenece el turno; el panel lo guarda y lo devuelve en el siguiente. */
  conversacionId?: string | null;
  /** Si el asistente dijo que no tiene información suficiente. */
  seAbstuvo?: boolean;
  citas?: CitaDelAsistente[];
}

/**
 * Quién contesta.
 *
 * Es una función y no un `qaBase` porque **las dos pantallas no preguntan a lo
 * mismo**: la de empresa va al asistente de verdad a través de la API, y la
 * privilegiada sigue en datos de ejemplo mientras el AI Service no responda
 * métricas de plataforma. Con un `qaBase` como única entrada, conectar una
 * obligaba a conectar la otra — o a meter el `if` dentro del organismo.
 */
export type Responder = (consulta: {
  pregunta: string;
  conversacionId: string | null;
}) => Promise<RespuestaMostrable>;

export interface ChatbotPanelProps {
  responder: Responder;
  privileged?: boolean;
  examplePrompts: string[];
}
