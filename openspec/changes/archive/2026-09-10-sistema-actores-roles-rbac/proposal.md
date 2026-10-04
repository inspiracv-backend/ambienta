# Proposal: Sistema de Actores, Roles, Multi-tenancy y Audit Log

Fuentes: [`fuentes/Ambienta_Analisis_Actores_v1.md`](./fuentes/Ambienta_Analisis_Actores_v1.md) (análisis de actores, aportado por el usuario, 2026-07-27) + [`fuentes/Prompt_ClaudeCode_Implementacion_Actores.md`](./fuentes/Prompt_ClaudeCode_Implementacion_Actores.md) (prompt de implementación que acompañó el análisis) + `Análisis Funcional v1.7` (Notion, 27-jul-2026) + `docs/arquitectura/adr/ADR-002-backend-separado.md` (estado: Propuesto, sin aprobar).

## Contexto

Todo lo construido hasta ahora en este repo (rama `001-frontend-fundacion-a-f`) es un **mock de frontend** (`apps/web`): sesión simulada en memoria, sin backend real. `apps/api` es hoy un esqueleto NestJS vacío (`AppModule` sin controllers/providers, sin ORM, sin conexión a base de datos). `apps/ai-service` es un placeholder de una línea. No existe ninguna spec de OpenSpec aprobada todavía para ninguna feature del repo.

El Análisis Funcional v1.7 formaliza **5 actores** (A0 Superadmin, A1 Admin Empresa, A2 Usuario Interno, A3 Cliente Invitado, A4 Gestor), pero el análisis de actores adjunto detecta que esa tabla deja fuera actores que el propio texto del funcional sí describe con responsabilidades, permisos y flujos propios:

- **A5 — Cliente final / usuario sub-tenant**: tiene dashboard propio (generado desde el Contrato, RF-66), permisos limitados, y una identidad que no es ni Cliente Invitado (no llega por link especial) ni Usuario Interno (no pertenece a un Departamento del tenant del Gestor).
- **Agente de Soporte**: RF-84 distingue explícitamente "equipo interno" de "Superadmin", implicando un sub-rol de plataforma con menos permisos que A0.
- **4 agentes de IA** (AmbiAgent, ingesta/Catálogo, monitoreo normativo, chatbot privilegiado) que **escriben** en el sistema (crean notificaciones/tickets, RF-61) sin que un humano lo dispare — necesitan identidad propia en el audit log.
- **A6 — Usuario vía LTI/Embed**: la decisión cerrada #10 del funcional (LTI 1.3 Advantage) introduce un actor externo de tipo sistema sin mapeo definido a los roles existentes.

Además, el análisis de actores señala 8 inconsistencias/riesgos de gobernanza (ver `docs/producto/...` o el documento original adjunto, sección 6) que esta propuesta debe resolver **explícitamente**, no en silencio.

## Objetivo

Especificar — sin implementar todavía — el modelo de datos, RBAC, autenticación, gobernanza multi-tenant y audit log que soportará **todos** los módulos de negocio futuros de Ambienta (Matriz Legal, Obligaciones, Auditorías, etc.), que hoy solo existen como mock de frontend.

Esta propuesta es la que CLAUDE.md exige antes de escribir código de backend ("Solo implementar Features que tengan spec aprobada en `openspec/`"). No se toca `apps/api` en este cambio.

## Alcance

### Incluye
- Modelo de datos para: tenants, plantas, departamentos, usuarios, sub-tenants (como tenants reales, ver `design.md`), contratos, permisos (tabla + asignación, no columnas booleanas), audit log inmutable con `actor_type` humano/sistema.
- RBAC granular para A2 (Usuario Interno), incluyendo los permisos que el análisis dejó explícitamente como faltantes (`puede_aprobar_cierre` separado de `puede_editar_evidencia`).
- Estrategia de autenticación: JWT + OAuth2/OIDC (Microsoft Entra ID prioritario + Google) **con el login social dejado como stub documentado** — sin credenciales reales todavía (decisión del usuario, 2026-07-27) — más el flujo **real** de Cliente Invitado (RUT + clave dinámica autogenerada, con expiración) y el fallback de clave local (RF-06).
- Guarda de ruta/middleware real (no solo validación de UI) para el flujo obligatorio de Perfil Empresa (RF-10).
- Aislamiento multi-tenant vía Row Level Security de PostgreSQL.
- Resolución explícita y documentada de las 4 preguntas de gobernanza que el prompt de implementación pidió resolver antes de modelar (cardinalidad de A1, A4 como flag de tenant, alcance de A5, acceso Gestor↔sub-tenant), más 5 supuestos adicionales detectados durante este diseño (ver tabla en `tasks.md`).
- Seed data: los usuarios de prueba de la sección 9 del análisis de actores, como fixtures.

### NO incluye (importante)
- **Código de implementación** — esta propuesta es spec-only. La implementación real en `apps/api` requiere que este documento sea revisado y aprobado primero (ciclo obligatorio de CLAUDE.md).
- **Credenciales OAuth reales** de Microsoft Entra ID / Google — el usuario no las tiene todavía; se deja el punto de enganche (`AuthStrategy` por proveedor) documentado pero sin secrets ni app registrations.
- **Resolución de ADR-002** (Fastify+tRPC+Drizzle vs. NestJS) — el usuario confirmó explícitamente construir sobre NestJS (lo ya instalado); ADR-002 queda como deuda arquitectónica sin resolver, no la resuelve esta propuesta.
- **Módulo LTI 1.3 completo** (A6) — solo se documenta el punto de extensión (`auth_provider` reservado, sin implementar el flujo de lanzamiento LTI).
- **Módulos de negocio** (Matriz Legal, Obligaciones, Auditorías, Reportes, etc.) — estos consumirán este sistema de actores más adelante, en propuestas separadas.
- **`apps/ai-service` real** (FastAPI/Python) — los 4 agentes de IA se modelan aquí solo como *identidades de auditoría* (`actor_type = 'system'`), no se implementa el servicio de IA en sí.

## Decisiones ya tomadas por el usuario (2026-07-27)

1. Redactar esta propuesta OpenSpec antes de escribir cualquier código de backend.
2. Modelar contra **NestJS** (el esqueleto ya instalado en `apps/api`), no contra Fastify+tRPC+Drizzle de ADR-002.
3. Auth OAuth real (Microsoft/Google) queda **pendiente de credenciales** — se avanza con todo lo demás (modelo de datos, RBAC, audit log, Cliente Invitado real) y se deja el stub de OAuth documentado.

## Criterios de aceptación

- [ ] El modelo de datos cubre los 5 actores formales + A5 + A6 (como extensión reservada) + agentes de sistema, sin que ninguno quede como "actor sin fila y sin permiso definido" (el problema raíz que detectó el análisis adjunto).
- [ ] Cada pregunta de gobernanza de las secciones 6 y 8 del análisis de actores queda resuelta con un default explícito y documentado (no implementada en silencio), en la tabla de `tasks.md`.
- [ ] El diseño de RBAC permite agregar un permiso nuevo sin migración estructural (tabla de permisos + tabla de asignación).
- [ ] El diseño de RLS mantiene el aislamiento por tenant (RNF-07) incluso para el caso Gestor↔sub-tenant, sin bypass implícito.
- [ ] El audit log queda diseñado como inmutable a nivel de base de datos (no solo por convención de aplicación), cubriendo RNF-08 y RNF-25.
- [ ] El flujo de Cliente Invitado y el guard de Perfil Empresa quedan diseñados como validación de servidor, no solo de UI (según pidió explícitamente el prompt de implementación).
- [ ] Queda claro qué partes son implementables ya (todo excepto OAuth social) y cuáles esperan un insumo externo (credenciales OAuth).
