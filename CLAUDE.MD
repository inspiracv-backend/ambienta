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

### 2. Arquitectura Backend Separado
- Frontend (Next.js) y Backend (NestJS) completamente separados.
- 4 deployables: web, api, worker, ai-service.
- Nunca mezclar lógica de negocio en el frontend.

### 3. API First + OpenAPI
- Todo endpoint nuevo debe definirse primero en el contrato OpenAPI.
- Usar `packages/shared` para tipos y validadores compartidos.
- Validación automática desde el contrato (Zod / class-validator).

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