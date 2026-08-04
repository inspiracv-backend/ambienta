# Progreso: Integracion de Clerk Auth

**Ultima actualizacion:** 2026-08-04

## Estado actual

**Fase actual:** Spec completada, pendiente de aprobacion.
**Nada implementado** — siguiendo SDD, se espera aprobacion antes de escribir codigo.

## Completado

- [x] Spec v1: proposal.md + design.md + tasks.md (commit 4e57898)
- [x] Spec v2: reescritura alineada con hallazgos-auditoria (commit 61672e8)
  - proposal.md: tabla de impacto, decisiones abiertas, alternativas con "por que no"
  - design.md: contratos TypeScript en vez de codigo, "por que" por decision
  - tasks.md: Fase 0 prerequisitos, supuestos vigentes vs a confirmar, tests por fase
- [x] PR #152 creado y actualizado en branch `feat/openspec-clerk-auth`

## Siguiente paso

1. **Revision y aprobacion de la spec por el equipo**
2. Resolver las 5 decisiones abiertas de proposal.md (onboarding, publicMetadata, SSO Microsoft, signup, DevRoleSwitcher)
3. Confirmar los 4 supuestos de tasks.md marcados como "a confirmar"
4. Una vez aprobada: ejecutar Fase 0 (crear cuenta Clerk, configurar JWT Template)

## Decisiones tomadas durante la escritura

| Decision | Detalle | Difiere de spec original? |
|---|---|---|
| No usar CLERK_SECRET_KEY en backend | Solo JWKS publica + webhook HMAC. Reduce superficie de ataque | No estaba en la v1 |
| Soft delete en user.deleted | Marcar is_active=false, no borrar, por integridad de audit log | No estaba en la v1 |
| 503 vs 401 cuando JWKS no disponible | 503 distingue "no puedo autenticar" de "no estas autenticado" | No estaba en la v1 |

## Blockers

- Ninguno para la fase de spec
- Para implementacion: se necesita cuenta de Clerk (Fase 0)
