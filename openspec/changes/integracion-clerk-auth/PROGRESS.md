# Progreso: Integracion de Clerk Auth

**Ultima actualizacion:** 2026-08-04

## Estado actual

**Fase 1 (backend: validacion JWT) — COMPLETADA.**
Rama `feat/clerk-auth-fase1-backend`, apilada sobre la rama de la spec.

Fases 2 a 7 pendientes. La Fase 0 esta bloqueada en acciones del equipo.

## Completado

- [x] Spec v1: proposal.md + design.md + tasks.md (commit 4e57898)
- [x] Spec v2: reescritura alineada con hallazgos-auditoria (commit 61672e8)
- [x] PROGRESS.md y protocolo OpenSpec en CLAUDE.md §1.1 (commit 89ae3b1)
- [x] **Fase 1 — backend:**
  - [x] `apps/api/app/auth.py` — validacion RS256 contra JWKS, cache 1h
  - [x] `apps/api/app/deps.py` — `get_tenant_id()` del JWT, fallback a header
  - [x] `apps/api/app/config.py` — 3 variables de Clerk + `clerk_configured`
  - [x] `apps/api/tests/` — 17 tests, sin necesidad de cuenta de Clerk
  - [x] `apps/api/README.md` — reescrito (estaba en puerto 3001, obsoleto)
  - [x] `.env.example` — Clerk reemplaza a `JWT_SECRET` y OAuth directo

## Verificacion hecha

| Que | Resultado |
|---|---|
| `python -m pytest` | 17 passed |
| `ruff check` sobre los archivos tocados | All checks passed |
| `from app.main import app` | 93 rutas, importa OK |
| Mutacion sobre la propiedad de seguridad | El test fallo como debia — no es vacuo |

La mutacion fue: hacer que `get_current_user()` confiara en el header
`X-Tenant-Id` aun con Clerk activo. `test_tenant_id_sale_del_token_no_del_header`
lo detecto. Esa es la propiedad que justifica todo el cambio.

## Decisiones tomadas durante la implementacion

| Decision | Detalle | Estaba en la spec? |
|---|---|---|
| `status='disabled'`, no `is_active` | La columna `is_active` no existe. `users` tiene `status` con CHECK | **No** — design.md corregido (commit e0acff5) |
| Validar el claim `iss` (`CLERK_ISSUER`) | Sin esto, un JWT de otra instancia de Clerk podia pasar | No — agregado |
| Fallback a JWKS vencida si Clerk cae | Una llave de hace 2h verifica firmas igual | No — agregado |
| `user_id=""` en modo desarrollo | No inventar una identidad que no existe | No — agregado |
| No usar `CLERK_SECRET_KEY` en backend | Solo JWKS publica + HMAC del webhook | Si |
| 503 y no 401 si la JWKS no carga | Distingue "no puedo verificar" de "no estas autenticado" | Si |

## Siguiente paso

**Fase 2 — migracion `clerk_id` + webhook de sincronizacion.**
No esta bloqueada: la migracion SQL y el endpoint de webhook se pueden escribir
y testear sin cuenta de Clerk (la firma svix se puede simular igual que la JWKS).

En paralelo, **Fase 3 (frontend)** tampoco depende de Fase 2.

## Bloqueado en el equipo (Fase 0)

Nada de esto lo puede hacer Claude Code — requiere acceso a dashboards externos:

1. **Crear la cuenta de Clerk** y obtener `CLERK_JWKS_URL`, `CLERK_ISSUER` y
   `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
2. **Configurar el JWT Template** que mapea `publicMetadata.tenant_id` al claim
   `tenant_id`. Sin esto, todo JWT llega sin tenant y la API responde 401
   (el caso ya esta cubierto por `test_token_sin_tenant_id_da_401`)
3. **Verificar el SSO de Microsoft/Entra ID** con una cuenta real — ADR-006 lo
   dejo pendiente y algunos tenants de Azure bloquean el flujo
4. **Decidir si se deshabilita el signup publico** (decision abierta #4)

Hasta que 1 y 2 esten hechos, la app corre en modo desarrollo (DevRoleSwitcher
+ header `X-Tenant-Id`), que es exactamente como corria antes de este cambio.

## Decisiones abiertas que siguen sin resolver

Las 5 de proposal.md. Ninguna bloquea la Fase 2 ni la Fase 3.
