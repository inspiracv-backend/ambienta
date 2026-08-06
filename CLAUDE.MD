# CLAUDE.md - Contexto del Proyecto Ambienta

## Visión General
Ambienta es un sistema multi-tenant para la gestión de cumplimiento ambiental de empresas industriales en Chile.
Objetivo: Centralizar declaraciones ambientales (RETC, residuos peligrosos, Ley REP, etc.), alertar vencimientos y generar reportes de auditoría.

## Reglas Obligatorias de Desarrollo (NO NEGOCIABLES)

### 1. Spec-Driven Development (SDD)
- **La especificación es la fuente de verdad**, no el código.
- Ciclo obligatorio por cada Feature:
  1. Especificar (OpenSpec: proposal.md + design.md + tasks.md)
  2. Revisar y aprobar la spec
  3. Implementar (Claude Code solo implementa specs aprobadas)
  4. Actualizar spec si hay cambios

#### 1.1 Protocolo OpenSpec para implementación
**ANTES de escribir cualquier línea de código de una Feature:**
1. Leer completos los 3 archivos de la spec (`proposal.md`, `design.md`, `tasks.md`)
2. Leer la sección de análisis relevante en `openspec/analisis/` (ej: `seccion-a-autenticacion.md`)
3. Leer las fuentes referenciadas en la spec si existen (`fuentes/`)
4. Verificar que la spec está aprobada (no implementar specs pendientes de revisión)

**DURANTE la implementación:**
1. Marcar cada checkbox `[ ]` → `[x]` en `tasks.md` conforme se completa
2. Si una decisión cambia respecto a la spec, actualizar `design.md` antes de seguir
3. Si se descubre un supuesto incorrecto, moverlo a "Supuestos derribados" en `tasks.md`

**AL TERMINAR la sesión o si se corta el contexto:**
1. Crear/actualizar `PROGRESS.md` en la carpeta de la spec con:
   - Última fase/tarea completada
   - Siguiente tarea pendiente
   - Decisiones tomadas durante la implementación que difieren de la spec
   - Blockers encontrados
2. Hacer commit del `PROGRESS.md` junto con el código

**Referencia de calidad:** `openspec/changes/hallazgos-auditoria-no-conformidades/` es el estándar de rigor para specs. Toda spec nueva debe seguir su nivel de detalle.

### 2. Arquitectura Backend Separado
- Frontend (Next.js) y Backend (FastAPI, Python) completamente separados.
- 4 deployables: web, api, worker, ai-service.
- Nunca mezclar lógica de negocio en el frontend.

### 3. API First + OpenAPI
- Todo endpoint nuevo debe definirse primero en el contrato OpenAPI.
- Usar `packages/shared` para tipos y validadores compartidos.
- Validación automática desde el contrato (Pydantic en la API; Zod en el frontend).

### 4. Seguridad Multi-Tenant (Crítica)
- Toda consulta debe filtrar por `tenant_id`.
- Row Level Security (RLS) en PostgreSQL como segunda barrera.
- RBAC verificado siempre en la API (nunca solo en frontend).
- Admin Global NO puede editar contenido de tenants.

### 5. Roles
- **Admin Global**: Dueño del software (gestión de tenants, catálogo maestro).
- **Admin Empresa**: Gestiona su empresa y empleados.
- **Encargado**: Operativo - crea/envía declaraciones.

### 6. Desarrollo con IA (Claude Code)
- Solo implementar Features que tengan spec aprobada en `openspec/`.
- Revisión humana obligatoria de todo PR generado por IA.
- Seguir convenciones del monorepo y este archivo.

## Estructura del Monorepo