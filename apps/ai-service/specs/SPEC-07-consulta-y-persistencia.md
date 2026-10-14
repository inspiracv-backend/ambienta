# SPEC-07 · Consulta y persistencia

**Objetivo.** `POST /consulta` recibe una pregunta del frontend, responde en streaming y deja la
conversación completa guardada en el backend de Ambienta, con sus citas.

## Alcance
- El endpoint descrito en [`contrato/ai-service.openapi.yaml`](contrato/ai-service.openapi.yaml).
- Abrir conversación, leer el hilo, guardar el turno del usuario y el del asistente.
- Streaming por SSE.

## Fuera de alcance
- Almacenamiento propio de conversaciones: no existe (handoff §7).
- Feedback del usuario sobre la respuesta: el backend ya tiene el campo `feedback`; lo escribe
  el frontend.
- Resumen de conversaciones largas (V2; en V1 se mandan los últimos N turnos).

## Reglas

| Regla | De dónde sale |
|---|---|
| Sin `conversation_id`, el AI Service abre una con `POST /support/chatbot` usando el UUID de `/me` y devuelve el id | Handoff §1 |
| El contexto del modelo son los últimos 10 mensajes del hilo, leídos del backend (que ya los devuelve ordenados) | Handoff §7 |
| La pregunta se guarda como mensaje `role: user` **antes** de llamar al modelo | Si el modelo falla, la pregunta no se pierde |
| La respuesta se guarda como `role: assistant` **completa, al terminar**, con `citations`, `cited_norm_ids`, `model_name` y `token_usage` | Handoff §7 |
| Las abstenciones también se guardan, con `cited_norm_ids: []` y `citations: [{"tipo": "abstencion", "motivo": "…"}]` (el campo es JSONB de forma libre) hasta que el backend tenga un campo propio. Se le pide al equipo | Una abstención es una respuesta correcta y tiene que quedar, y distinguible de "respondió sin citar" |
| Si guardar la respuesta falla, el cliente recibe el evento `error` después de `final`, y el intento queda en la traza | El usuario vio la respuesta; hay que saber que no quedó guardada |
| Los mensajes no se editan ni se borran (handoff §7). Lo único que el AI Service puede actualizar es `citations` / `cited_norm_ids` del mensaje que acaba de crear | — |
| El AI Service responde 503 si el backend está caído, 403 sin permiso, 422 si la pregunta no cumple el contrato | Contrato |
| En modo desarrollo no hay usuario: la consulta responde pero **no se guarda**, y la respuesta lo dice con `guardado: false` | Handoff §2 |

## Secuencia

```
Frontend ──POST /consulta──▶ AI Service
                              ├─ SPEC-02 sesión (token → tenant, /me → usuario y permisos)
                              ├─ sin conversation_id → POST /support/chatbot
                              ├─ GET  /support/chatbot/{id}/messages   (hilo)
                              ├─ POST /support/chatbot/{id}/messages   (role: user)
                              ├─ SPEC-06 agente  ──▶ eventos SSE al frontend
                              └─ POST /support/chatbot/{id}/messages   (role: assistant, citas)
```

## Criterios de aceptación

```gherkin
# language: es
Característica: Una consulta queda guardada en Ambienta con sus citas

  Escenario: Primera pregunta de una conversación nueva
    Dado un usuario de la empresa A con chatbot.use
    Cuando envía "¿qué proyectos requieren EIA?" sin conversation_id
    Entonces se abrió una conversación con su UUID interno como user_id
    Y el hilo tiene dos mensajes: user y assistant, en ese orden
    Y el mensaje assistant tiene cited_norm_ids no vacío, model_name y token_usage

  Escenario: Continuar una conversación
    Dada una conversación con dos turnos
    Cuando el usuario envía "¿y si el proyecto está en un área protegida?" con ese conversation_id
    Entonces el modelo recibió los cuatro mensajes anteriores como contexto
    Y el hilo queda con seis mensajes en orden

  Escenario: Conversación de otra empresa
    Dada una conversación de la empresa B
    Cuando un usuario de la empresa A envía una pregunta con ese conversation_id
    Entonces la respuesta es 404
    Y no se llamó al modelo

  Escenario: La abstención se guarda
    Cuando el usuario pregunta algo fuera del corpus
    Entonces el evento final tiene se_abstuvo verdadero
    Y el mensaje assistant guardado registra la abstención

  Escenario: El modelo falla
    Dado un modelo que no responde
    Cuando el usuario envía una pregunta
    Entonces el mensaje user quedó guardado
    Y el cliente recibe un evento error con código "modelo_no_disponible"

  Escenario: Streaming
    Cuando el usuario envía una pregunta con Accept text/event-stream
    Entonces recibe eventos "herramienta" y "texto" antes del evento "final"
    Y el evento "final" trae la RespuestaConsulta completa

  Escenario: Modo desarrollo
    Dado el AI Service sin Clerk
    Cuando llega una pregunta con X-Tenant-Id
    Entonces se responde
    Y la respuesta tiene guardado falso
    Y no se llamó a POST /support/chatbot
```

## Pruebas
- **Unitarias** con backend simulado (`respx`) y agente falso: escenarios 3, 5, 6 y 7.
- **Integración** contra el compose de Ambienta con usuarios de Clerk de prueba: escenarios 1,
  2, 3 y 4. Requiere lo pedido al equipo (usuario de prueba por empresa).

## Implementación (20/09/2026)

Implementado en `servicio/src/ambienta_ia/consulta.py` y `servicio/src/ambienta_ia/api/app.py`.
Pruebas: `tests/integracion/test_api.py`, contra el backend simulado (`ambienta_ia.demo`), que
aplica las reglas del handoff: 404 para lo ajeno, hilo ordenado, 409 sin usuario.

El `mensaje_id` es entero (así lo devuelve el backend), no UUID; el contrato se corrigió.

## Contra el backend real (21/09/2026)

Ver [`prueba-contra-ambienta/`](../prueba-contra-ambienta/README.md).
- Conversación de tres turnos guardada en el backend real: hilo en orden, `citations`,
  `cited_norm_ids` como `uuid[]`, `model_name`, `token_usage`, autor = la persona.
- Otra empresa no puede escribir en la conversación (404).
