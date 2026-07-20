# Ambienta

**Sistema multi-tenant de gestión de cumplimiento ambiental para empresas industriales en Chile y Latam.**

Ambienta ayuda a las empresas a gestionar vencimientos, obligaciones regulatorias (RETC, Ley REP, SINADER, SIDREP, DAE, etc.), evidencias y no conformidades de forma centralizada, reduciendo el riesgo de multas y el trabajo manual.

---

## Objetivo

Centralizar el control de obligaciones ambientales, alertar vencimientos de forma proactiva, gestionar evidencias y no conformidades, y entregar visibilidad consolidada multi-planta a especialidades ambientales y gerencias.

---

## Stack Tecnológico

| Capa              | Tecnología                          |
|-------------------|-------------------------------------|
| Frontend          | Next.js 15 (App Router) + TypeScript |
| Backend API       | Fastify + tRPC                      |
| Worker            | Node.js + BullMQ                    |
| Servicio IA       | Python + FastAPI + LangGraph        |
| Base de datos     | PostgreSQL 16 + pgvector            |
| Cache / Colas     | Redis 7                             |
| Monorepo          | Turborepo + pnpm                    |
| Autenticación     | JWT + Microsoft (prioridad)         |
| Email             | Resend / Brevo                      |
| Metodología       | Spec-Driven Development (OpenSpec)  |

---

## Estructura del Monorepo
ambienta/
├── apps/
│   ├── web/                  # Frontend (Next.js)
│   ├── api/                  # Backend API (Fastify + tRPC)
│   ├── ai-service/           # Servicio de IA (Python)
│   └── notification-worker/  # Worker de notificaciones
├── packages/
│   ├── domain/               # Entidades y lógica de dominio
│   ├── db/                   # Schema Drizzle + migraciones
│   ├── trpc/                 # Tipos compartidos tRPC
│   ├── permissions/          # RBAC (CASL)
│   └── email/                # Templates de email
├── docs/                     # Documentación de producto y arquitectura
├── openspec/                 # Especificaciones vivas (OpenSpec)
├── docker-compose.yml
└── turbo.json
text---

## Documentación

Toda la documentación se encuentra en la carpeta [`/docs`](./docs).

- **Producto**: Análisis funcional, oportunidad de mercado, segmentos objetivo
- **Arquitectura**: ADD, ADRs, diagramas
- **Desarrollo**: Setup local, flujo de Git, convenciones

Las especificaciones de features (proposal → design → tasks) se gestionan con **OpenSpec** dentro de la carpeta `openspec/`.

---

## Principios de desarrollo

1. **Spec-Driven Development** → Primero se especifica, luego se implementa.
2. **Backend separado** → Frontend y API completamente desacoplados.
3. **Multi-tenant fuerte** → Aislamiento estricto por `tenant_id` + Row Level Security.
4. **Type-safe end-to-end** → tRPC + TypeScript en todo el stack.
5. **API-first** → El backend puede ser consumido por web, móvil o integraciones.

---

## Cómo empezar (desarrollo local)

```bash
# 1. Clonar el repositorio
git clone https://github.com/inspiracv-backend/ambienta.git
cd ambienta

# 2. Instalar dependencias
pnpm install

# 3. Levantar servicios (PostgreSQL, Redis, etc.)
docker compose up -d

# 4. Ejecutar migraciones
pnpm db:migrate

# 5. Levantar el monorepo
pnpm dev
Más detalles en docs/development/setup-local.md

Estado actual

Proyecto en etapa temprana (MVP)
Documentación de producto y arquitectura en construcción
Usando OpenSpec para especificar features antes de codificar


Equipo

Luciano Recchini Studio
Fabrizzio Gomez
Gabriel Tovar


Ambienta — Cumplimiento ambiental, sin el caos.