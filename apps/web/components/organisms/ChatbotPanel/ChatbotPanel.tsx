'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { Bot, ScrollText, Send, ShieldCheck, User } from 'lucide-react';
import type { ChatMessage } from '@ambienta/shared';
import { Button, Input } from '@/components/atoms';
import { cn } from '@/lib/utils';
import { mockLegalNorms } from '@/mocks/catalog';
import type { ChatbotPanelProps } from './ChatbotPanel.types';

const FALLBACK =
  'No encontré información específica para tu pregunta. Intenta reformularla usando otros términos (por ejemplo, el nombre de una norma o de un sistema de declaración).';

function formatHora(iso: string) {
  return new Date(iso).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
}

/**
 * S-34/S-35: mismo organismo para el chatbot tenant-aware y el privilegiado
 * (RF-55, misma base de conocimiento) — solo cambia `qaBase` y `privileged`.
 * Integración real: reemplazar la búsqueda por palabra clave por
 * apps/ai-service (LangGraph + embeddings) cuando exista spec aprobada.
 */
export function ChatbotPanel({ qaBase, privileged, examplePrompts }: ChatbotPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  function respond(pregunta: string) {
    const lower = pregunta.toLowerCase();
    const match = qaBase.find((qa) => qa.keywords.some((k) => lower.includes(k)));

    setIsTyping(true);
    setTimeout(() => {
      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now()}-a`,
        role: 'assistant',
        contenido: match?.respuesta ?? FALLBACK,
        fecha: new Date().toISOString(),
        citaNormId: match?.citaNormId,
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsTyping(false);
    }, 600);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}-u`,
      role: 'user',
      contenido: input.trim(),
      fecha: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    respond(input.trim());
    setInput('');
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
        {messages.length === 0 ? (
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
          <ul className="flex flex-col gap-3">
            {messages.map((m) => {
              const norm = m.citaNormId ? mockLegalNorms.find((n) => n.id === m.citaNormId) : undefined;
              return (
                <li key={m.id} className={cn('flex gap-2', m.role === 'user' && 'flex-row-reverse')}>
                  <div className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-full', m.role === 'user' ? 'bg-slate-100' : 'bg-brand-100')}>
                    {m.role === 'user' ? <User className="h-4 w-4 text-slate-500" aria-hidden /> : <Bot className="h-4 w-4 text-brand-700" aria-hidden />}
                  </div>
                  <div className={cn('max-w-[75%] rounded-card px-4 py-2.5 text-sm', m.role === 'user' ? 'bg-slate-100 text-slate-800' : 'bg-brand-50 text-slate-800')}>
                    <p>{m.contenido}</p>
                    {norm && (
                      <Link href={`/matriz-legal/${norm.id}`} className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline">
                        <ScrollText className="h-3 w-3" aria-hidden />
                        Ver {norm.nombre}
                      </Link>
                    )}
                    <p className="mt-1 text-[10px] text-slate-400">{formatHora(m.fecha)}</p>
                  </div>
                </li>
              );
            })}
            {isTyping && <li className="text-xs text-slate-400">Escribiendo…</li>}
          </ul>
        )}
      </div>

      <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-slate-200 p-3">
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
