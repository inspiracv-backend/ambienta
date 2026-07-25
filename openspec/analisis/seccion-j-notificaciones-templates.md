# Sección J — Notificaciones y Templates (S-31 a S-33)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.5" (Notion), ambos actualizados 2026-07-23.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-31 Centro de Notificaciones**: panel desde el ícono de campana. Lista con indicadores de urgencia (ícono+color+texto). Botón "Marcar todas como leídas". Estado vacío.
- **S-32 Configuración de Notificaciones**: toggles de canal (email/in-app) y anticipación de recordatorios.
- **S-33 Super-repositorio de Templates Excel**: listado de templates por sistema de declaración (SIDREP, SINADER, DAE...). Cada template indica versión y pestañas. Acción de descarga. Nota visual de que se adjuntan automáticamente en los recordatorios de email.

## Requisitos funcionales correspondientes (Notion v1.5)

- RF-22 a RF-26: super-repositorio de templates Excel (2 pestañas mínimo), adjunto automático en recordatorios, actualización cuando cambia la estructura oficial, campos dinámicos por cliente/gestor.
- RF-30 a RF-33: notificaciones proactivas (email + in-app), escalamiento de urgencia según proximidad del plazo, adjunto de template en notificaciones de declaración, entrega al responsable correcto.

## Gaps o inconsistencias detectadas

- El envío real de notificaciones (email con template Excel adjunto, RF-24/RF-32) depende de un servicio de correo transaccional (Resend/Brevo, ver Sección 6.2 del Análisis Funcional) — **fuera de alcance del frontend**, sin spec de API aprobada. El Centro de Notificaciones (S-31) se construye sobre notificaciones in-app ya generadas (mock); no se dispara ningún email real.
- **Decisión de UI**: el prompt describe S-31 como "panel desde el ícono de campana" (popover). En esta iteración se implementa como una **página dedicada** (`/notificaciones`) en vez de un popover flotante, por consistencia con el resto de la plataforma (las 8 secciones ya implementadas son todas páginas de ruta propia, ninguna es un dropdown) — evita introducir un patrón de interacción nuevo (click-outside-to-close, posicionamiento flotante) para una sola pantalla. El ícono de campana en el header muestra el contador de no leídas y enlaza a la página.
- La actualización automática de templates cuando el organismo oficial cambia su estructura (RF-25) no tiene disparador en el frontend — se deja como acción manual de un Admin Empresa/Superadmin (fuera de alcance de S-33 tal como está descrita, que es de solo lectura/descarga).

## Componentes Atomic Design necesarios

- Átomos: reutiliza `StatusBadge` (urgencia baja/media/alta → mapeo a semáforo existente).
- Moléculas: reutiliza `FormField`.
- Organismos: `NotificationCenter` (S-31), `NotificationPreferencesForm` (S-32), `ExcelTemplatesList` (S-33).
- Templates: ninguno nuevo.

## Decisión: mapeo de urgencia

`Notification.urgencia` (baja/media/alta) se mapea a `SemaforoStatus` existente (baja→cumple, media→parcial, alta→no_cumple) — mismo criterio que Auditorías/NC (Sección G) y Catálogo (Sección H): nunca un nuevo valor en `StatusBadge`, siempre ícono+color+texto (H1+H4).

## Datos de ejemplo necesarios (mock data)

- Nuevo `mocks/notifications.ts`: notificaciones mixtas (leídas/no leídas, urgencia alta/media/baja) para el usuario actual, cruzando obligaciones ya existentes en `mocks/obligations.ts` cuando corresponda.
- Nuevo `mocks/templates.ts`: 5 templates Excel (uno por sistema: RETC, Ley REP, SINADER, SIDREP, DAE), cada uno con exactamente 2 pestañas (RF-23).

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — contador de no leídas visible en el header sin necesidad de entrar al Centro de Notificaciones.
- [x] H2 Correspondencia con el mundo real — nombres de sistema de declaración exactos (SIDREP, SINADER, etc.) en los templates.
- [x] H3 Control y libertad — "Marcar todas como leídas" es reversible en el sentido de que no borra nada, solo cambia el estado de lectura.
- [x] H4 Consistencia — mismo semáforo que el resto de la plataforma para la urgencia.
- [x] H8 Estética minimalista — Centro de Notificaciones no mezcla configuración ni templates en la misma vista; cada uno es su propia pantalla.
- [x] H10 Ayuda y documentación — estado vacío del Centro de Notificaciones con mensaje claro cuando no hay notificaciones.
