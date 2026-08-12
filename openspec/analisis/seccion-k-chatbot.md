# Sección K — Chatbot IA (S-34, S-35)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.5" (Notion), ambos actualizados 2026-07-23.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-34 Chatbot Tenant-aware**: interfaz de chat lateral o pantalla completa. Historial, input inferior, respuestas con citas a normas cuando corresponda. Diseño limpio y confiable. Solo datos del tenant + normativa pública.
- **S-35 Chatbot Privilegiado**: misma interfaz base + indicador visual de "Modo Privilegiado" y acceso a consultas de plataforma (métricas cross-tenant), exclusivo Superadmin.

## Requisitos funcionales correspondientes (Notion v1.5)

- RF-52: chatbot tenant-aware, solo datos del tenant + normativa pública.
- RF-53: chatbot privilegiado exclusivo Superadmin (métricas globales, estado de tenants).
- RF-54: capa agéntica que monitorea cambios normativos (fuera de alcance de esta sección, ver Sección H).
- RF-55: ambos chatbots se alimentan de la misma base de conocimiento (embeddings + metadata).
- RF-55b: monitoreo de estado de agentes y mecanismos anti-alucinación.

## Gaps o inconsistencias detectadas

- El chatbot real depende de `apps/ai-service` (LangGraph + embeddings, hoy solo un esqueleto TypeScript sin implementar — ver `docs/arquitectura/auditoria-stack-frontend.md`). **Sin spec de API aprobada**, esta iteración construye la interfaz completa (S-34/S-35) sobre un conjunto de preguntas/respuestas mock por palabras clave, no un LLM real. El punto de integración queda comentado en el código.
- RF-55b (monitoreo de agentes, anti-alucinación) no tiene representación en la UI de esta sección — ya existe un panel de salud del agente BCN en Catálogo Normativo (Sección H); no se duplica aquí un segundo panel sin datos reales que mostrar.
- **Heurística H9 crítica para esta sección**: cuando la pregunta del usuario no coincide con ninguna respuesta conocida, el chatbot no debe fallar en silencio — debe ofrecer una ruta de recuperación (reformular la pregunta, contactar soporte) en vez de un mensaje genérico de error.
- RF-55 ("ambos chatbots se alimentan de la misma base de conocimiento") se refleja usando el mismo organismo `ChatbotPanel` para ambos roles, cambiando solo el conjunto de respuestas disponibles (tenant-aware vs. privilegiado) y el indicador visual — no dos componentes separados.

## Componentes Atomic Design necesarios

- Átomos: ninguno nuevo.
- Moléculas: ninguna nueva (los mensajes del chat son parte del organismo, no se reutilizan en otra pantalla).
- Organismos: `ChatbotPanel` (S-34 y S-35 comparten el mismo organismo con prop `privileged`).
- Templates: ninguno nuevo.

## Datos de ejemplo necesarios (mock data)

- Nuevo `mocks/chatbot.ts`: preguntas/respuestas de ejemplo por palabras clave para el chatbot tenant-aware (citando normas de `mocks/catalog.ts` cuando corresponde) y para el chatbot privilegiado (métricas sobre `mocks/tenants.ts`).

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — indicador "escribiendo…" mientras se simula la respuesta; "Modo Privilegiado" siempre visible para el Superadmin.
- [x] H2 Correspondencia con el mundo real — respuestas citan la normativa exacta (ej. "Ley 20.920 — Ley REP"), no genéricas.
- [x] H4 Consistencia — un solo `ChatbotPanel` para ambos roles, mismo patrón de burbujas de chat.
- [x] H8 Estética minimalista — diseño limpio, sin densidad de información adicional en la burbuja del chat.
- [x] H9 Recuperación de errores (🔴 crítica para esta sección) — pregunta sin coincidencia ofrece reformular o contactar soporte, nunca un fallo silencioso.
