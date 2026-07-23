# Auditoría de stack — Frontend Ambienta

**Fecha:** 2026-07-23
**Autor:** Claude Code (sesión de arranque de desarrollo frontend)
**Estado:** Informativo — deja constancia de la discrepancia, no reemplaza una decisión formal de arquitectura

---

## 1. Objetivo

Antes de escribir el primer componente se auditó el código real del monorepo contra lo que describe `README.md`, porque ambos no coinciden. Esta auditoría fija qué stack se usa **para el trabajo inmediato de frontend**, sin resolver la discrepancia a nivel de equipo (eso le corresponde al ADR correspondiente).

## 2. Discrepancia encontrada

| Componente | Descrito en `README.md` | Código real en `apps/` / manifiestos |
|---|---|---|
| Frontend | Next.js 15 (App Router) | Next.js **14.2.15**, React 18 (`apps/web/package.json`) |
| Backend API | Fastify + tRPC | **NestJS 10** puro (`@nestjs/common`, `@nestjs/core`, `@nestjs/platform-express`) — sin Fastify ni tRPC instalados |
| Package manager | pnpm (Turborepo + pnpm workspaces) | **npm** — hay `package-lock.json` en la raíz y `"packageManager": "npm@10.8.2"` en `package.json`; no existe `pnpm-lock.yaml` |
| ORM | Drizzle (`packages/db`) | No implementado. `packages/shared` solo declara `zod` como dependencia; no hay `packages/db` |
| RBAC | CASL (`packages/permissions`) | No implementado; no existe `packages/permissions` |
| ai-service | Python + FastAPI + LangGraph | Esqueleto en TypeScript (`apps/ai-service/src/index.ts`) |
| worker | `apps/notification-worker` (BullMQ) | Carpeta `apps/worker` (nombre distinto), esqueleto TS sin BullMQ instalado |

## 3. Decisión para el trabajo inmediato de frontend

Se construye sobre el **código real, no sobre el README**:

- **Next.js 14.2.15** con App Router (ya instalado en `apps/web`). No se actualiza a Next 15 en esta etapa — eso es una decisión de equipo, no del frontend aislado.
- **npm workspaces** (ya configurado en la raíz vía `workspaces` en `package.json` y `package-lock.json`). No se introduce pnpm.
- El frontend consume **mocks locales** en esta etapa (no hay API real que consumir: NestJS solo tiene un `AppModule` vacío, sin Fastify/tRPC). La integración real queda comentada explícitamente en el código donde correspondería (ver Paso 4 de `prompt-claude-code-ambienta.md`).
- `packages/shared` se usa como está (solo `zod`) y se le agregan los primeros tipos/schemas Zod que necesita el frontend (`Tenant`, `User`/`Role`, `Obligation`, `LegalNorm`, `Audit`, `NonConformity`) — no se duplican en `apps/web`.

## 4. Constancia para el equipo

Esta discrepancia **no se resuelve aquí**. `ADR-002-backend-separado.md` (en `docs/arquitectura/adr/`) sigue en estado **"Propuesto"**, no aprobado. Se recomienda que el equipo:

1. Confirme si el objetivo real es migrar a Next 15 + Fastify/tRPC/Drizzle/CASL (como dice el README), o si el README quedó desactualizado y el objetivo es NestJS + REST/otro ORM.
2. Actualice `README.md` para que coincida con la decisión, evitando que quede como fuente de verdad contradictoria.
3. Revise si `apps/notification-worker` (nombre en README/ADD) vs `apps/worker` (nombre real) es también una decisión pendiente de renombrar.

Mientras esa decisión no se tome, el frontend desarrollado en esta iteración es agnóstico a la capa de datos real: solo depende de los tipos de `packages/shared` y de mocks, por lo que no se ve afectado si el backend termina siendo NestJS+REST o Fastify+tRPC.
