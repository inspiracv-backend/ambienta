# ADR-002: Backend Separado con Turborepo como arquitectura base del MVP

**Estado:** `Propuesto` — pendiente de decisión (ver ADR-001 para alternativa)  
**Fecha:** 2026-06-01  
**Decisores:** Gabriel Tovar · Mauricio (socio técnico, pendiente reunión 2026-06-07)  
**Categoría:** Arquitectura de software  
**Spec técnica:** `ADD-ambienta-backend-separado.md`

---

## Contexto

Ambienta necesita definir su arquitectura base para construir el MVP en 12 semanas con un equipo de 2 personas. El sistema incluye un componente de agente IA intensivo (Python/LangGraph) que no encaja naturalmente en un stack Node.js unificado, y el perfil del socio técnico (Mauricio) puede justificar mayor complejidad desde el inicio.

Esta es la alternativa al ADR-001.

---

## Decisión

Construir Ambienta como un **monorepo Turborepo** con cuatro aplicaciones separadas desplegadas de forma independiente:

| App | Tech | Rol |
|---|---|---|
| `apps/web` | Next.js 16 | Frontend + Server Actions |
| `apps/api` | Fastify + tRPC | API backend principal |
| `apps/ai-service` | FastAPI + LangGraph (Python) | Agente IA + RAG |
| `apps/worker` | Node.js + BullMQ | Jobs async + notificaciones |

Paquetes compartidos: `packages/db` (Drizzle ORM) · `packages/ui` · `packages/domain` · `packages/config`.

Stack: **Turborepo + Fastify + tRPC + Drizzle + Neon + Docker Compose + Hetzner (VPS)**.

---

## Consecuencias

### ✅ Positivas
- El servicio IA en Python corre de forma nativa con LangGraph y sus dependencias sin adapters
- Cada servicio escala independientemente (el worker de jobs no afecta al API en picos)
- Mayor separación de responsabilidades desde el día 1 — mejor para equipos que crecen rápido
- Drizzle tiene menor footprint de bundle que Prisma (relevante si el API es serverless)
- Hetzner VPS es significativamente más barato que Vercel Pro a largo plazo

### ⚠️ Trade-offs
- Docker Compose en desarrollo + 4 servicios = onboarding más lento para nuevos desarrolladores
- tRPC entre web y api añade una capa de comunicación que en monolito es una importación directa
- Sin Prisma Studio → debugging de datos más lento en etapas tempranas
- Vercel preview deployments por PR requieren configuración adicional en monorepo
- "Corremos en Hetzner" puede ser bloqueante en filtros de seguridad IT de grandes empresas vs "corremos en Vercel"

### 🔄 Neutral
- La lógica de dominio (entidades, use cases) es idéntica a ADR-001 — el dominio no cambia entre opciones
- El esquema de base de datos es compatible entre Drizzle (esta opción) y Prisma (ADR-001)

---

## Alternativas consideradas

| Alternativa | Por qué no se elige (si se descarta) |
|---|---|
| ADR-001: Monolito Modular | Menor complejidad operacional, mejor para equipo de 2 en MVP. El agente IA se puede aislar igualmente via Trigger.dev. |
| Microservicios completos | Inviable para equipo de 2 en 12 semanas |
| Backend separado sin Turborepo | Duplicación de código entre proyectos — peor que monorepo |

---

## Criterios de revisión

Esta arquitectura está **justificada desde el inicio** si:
- El socio técnico (Mauricio) tiene experiencia activa con Docker Compose y Turborepo
- El agente IA requiere GPU o dependencias Python que no son viables en Vercel Edge
- El equipo de desarrollo empieza con 3+ personas desde el MVP

Si ninguna de las anteriores aplica, **preferir ADR-001** y migrar a esta arquitectura cuando el crecimiento del equipo o del uso lo justifiquen.

---

## Referencias
- Spec técnica completa: `ADD-ambienta-backend-separado.md`
- Alternativa: `ADR-001-monolito-modular.md`
- Stack evaluado: `stack-moderno-ambienta-2026.md` · `ecosistemas-tecnologicos-ambienta.md`
