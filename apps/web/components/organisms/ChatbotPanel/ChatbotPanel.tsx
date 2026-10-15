'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { AlertTriangle, Bot, ScrollText, Send, ShieldCheck, User } from 'lucide-react';
import type { ChatMessage } from '@ambienta/shared';
import { Button, Input } from '@/components/atoms';
import { esConversacionPerdida, mensajeDeFalla } from '@/lib/chatbot';
import type { CitaDelAsistente } from '@/lib/chatbot';
import { cn } from '@/lib/utils';
import type { ChatbotPanelProps } from './ChatbotPanel.types';

/** Un turno ya mostrado. Agrega a `ChatMessage` lo que el asistente de verdad devuelve. */
interface Turno extends ChatMessage {
  seAbstuvo?: boolean;
  citas?: CitaDelAsistente[];
  /** La consulta no llegó o fue rechazada; no es una respuesta del asistente. */
  esFalla?: boolean;
}

function formatHora(iso: string) {
  return new Date(iso).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
}

function etiqueta(cita: CitaDelAsistente) {
  return cita.articulo ? `${cita.norma}, artículo ${cita.articulo}` : cita.norma;
}

/**
 * S-34/S-35: mismo organismo para el chatbot de empresa y el privilegiado
 * (RF-55, misma base de conocimiento) — sólo cambia quién contesta.
 *
 * ## Tres cosas que no se deducen del texto de la respuesta
 *
 * **La abstención la declara el servicio** (`se_abstuvo`). Un «no tengo
 * información suficiente» y una respuesta fundamentada se muestran distinto, y
 * adivinarlo leyendo el texto es como se termina presentando una abstención
 * como si fuera un hecho comprobado.
 *
 * **Una falla no es una respuesta.** Cuando la consulta no llega, lo que se
 * muestra lleva su propio aspecto y no la cara del asistente: un error con
 * forma de respuesta se lee como que el asistente afirmó algo.
 *
 * **La conversación la abre el servicio.** El primer turno va sin id; el que
 * vuelve se guarda y viaja en los siguientes, o cada pregunta empieza un hilo
 * nuevo y el asistente responde sin recordar la anterior.
 */
export function ChatbotPanel({ responder, privileged, examplePrompts }: ChatbotPanelProps) {
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [input, setInput] = useState('');
  const [esperando, setEsperando] = useState(false);
  const [conversacionId, setConversacionId] = useState<string | null>(null);

  async function preguntar(pregunta: string) {
    setEsperando(true);
    try {
      const r = await responder({ pregunta, conversacionId });
      // Sólo se pisa si vino uno: una respuesta sin `conversation_id` no
      // significa "volvé a empezar".
      if (r.conversacionId) setConversacionId(r.conversacionId);
      setTurnos((prev) => [
        ...prev,
        {
          id: `msg-${Date.now()}-a`,
          role: 'assistant',
          contenido: r.texto,
          fecha: new Date().toISOString(),
          seAbstuvo: r.seAbstuvo,
          citas: r.citas,
        },
      ]);
    } catch (error) {
      // Si el hilo se perdio, se suelta: arrastrarlo deja cada pregunta
      // siguiente fallando igual, y el chat roto hasta recargar.
      if (esConversacionPerdida(error)) setConversacionId(null);
      setTurnos((prev) => [
        ...prev,
        {
          id: `msg-${Date.now()}-e`,
          role: 'assistant',
          contenido: mensajeDeFalla(error),
          fecha: new Date().toISOString(),
          esFalla: true,
        },
      ]);
    } finally {
      setEsperando(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const pregunta = input.trim();
    // **Una consulta a la vez, y la regla vive sólo acá.** Dos en vuelo vuelven
    // en cualquier orden y el hilo queda con las respuestas cruzadas. No se
    // duplica en `disabled` del campo ni del botón: una guarda que no se puede
    // alcanzar es una guarda que ninguna prueba mide — y lo parecía.
    if (!pregunta || esperando) return;

    setTurnos((prev) => [
      ...prev,
      { id: `msg-${Date.now()}-u`, role: 'user', contenido: pregunta, fecha: new Date().toISOString() },
    ]);
    setInput('');
    void preguntar(pregunta);
  }

  return (
    <div className="flex h-[70vh] flex-col rounded-card border border-slate-200 bg-white">
      {privileged && (
        <div className="flex items-center gap-2 border-b border-slate-200 bg-brand-50 px-4 py-2 text-sm font-medium text-brand-700">
          <ShieldCheck className="h-4 w-4" aria-hidden />
          Modo Privilegiado — métricas de toda la plataforma
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4">
        {turnos.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-sm text-slate-500">
            <Bot className="h-8 w-8 text-brand-400" aria-hidden />
            <p>Pregúntame sobre el cumplimiento de tu {privileged ? 'plataforma' : 'empresa'}.</p>
            <div className="flex flex-wrap justify-center gap-2">
              {examplePrompts.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => {
                    setInput(p);
                  }}
                  className="rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <ul className="flex flex-col gap-3" aria-live="polite">
            {turnos.map((m) => (
              <li key={m.id} className={cn('flex gap-2', m.role === 'user' && 'flex-row-reverse')}>
                <div
                  className={cn(
                    'flex h-7 w-7 shrink-0 items-center justify-center rounded-full',
                    m.role === 'user' ? 'bg-slate-100' : m.esFalla ? 'bg-amber-100' : 'bg-brand-100',
                  )}
                >
                  {m.role === 'user' ? (
                    <User className="h-4 w-4 text-slate-500" aria-hidden />
                  ) : m.esFalla ? (
                    <AlertTriangle className="h-4 w-4 text-amber-700" aria-hidden />
                  ) : (
                    <Bot className="h-4 w-4 text-brand-700" aria-hidden />
                  )}
                </div>
                <div
                  // Una falla se **anuncia**: quien usa lector de pantalla se
                  // entera de que la consulta no llego, en vez de quedarse
                  // esperando una respuesta que no viene.
                  role={m.esFalla ? 'alert' : undefined}
                  className={cn(
                    'max-w-[75%] rounded-card px-4 py-2.5 text-sm',
                    m.role === 'user'
                      ? 'bg-slate-100 text-slate-800'
                      : m.esFalla
                        ? 'bg-amber-50 text-amber-900'
                        : 'bg-brand-50 text-slate-800',
                  )}
                >
                  {m.seAbstuvo && (
                    <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      Sin evidencia suficiente
                    </p>
                  )}
                  <p>{m.contenido}</p>
                  {m.citas && m.citas.length > 0 && (
                    <ul className="mt-1.5 flex flex-col gap-1">
                      {m.citas.map((c) => (
                        <li key={`${c.norm_id}-${c.article_id ?? 'norma'}`}>
                          <Link
                            href={`/matriz-legal/${c.norm_id}`}
                            className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline"
                          >
                            <ScrollText className="h-3 w-3" aria-hidden />
                            {etiqueta(c)}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="mt-1 text-[10px] text-slate-400">{formatHora(m.fecha)}</p>
                </div>
              </li>
            ))}
            {esperando && <li className="text-xs text-slate-400">Escribiendo…</li>}
          </ul>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        aria-busy={esperando}
        className="flex items-center gap-2 border-t border-slate-200 p-3"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Escribe tu pregunta..."
          aria-label="Mensaje para el chatbot"
        />
        <Button type="submit" size="md" aria-label="Enviar" disabled={!input.trim()}>
          <Send className="h-4 w-4" aria-hidden />
        </Button>
      </form>
    </div>
  );
}
