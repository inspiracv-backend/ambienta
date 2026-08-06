# Progreso: Integracion de Clerk Auth

**Ultima actualizacion:** 2026-08-04

## Estado actual

**Fases 1 y 2 (backend completo) — COMPLETADAS.**
- Fase 1: `feat/clerk-auth-fase1-backend` (PR #153)
- Fase 2: `feat/clerk-auth-fase2-webhook`, apilada sobre la anterior

Fases 3 a 7 pendientes. La Fase 0 sigue bloqueada en acciones del equipo.

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
- [x] **Fase 2 — sincronizacion de usuarios:**
  - [x] `db/04_clerk_auth.sql` — columna `clerk_id` + UNIQUE, idempotente
  - [x] `app/services/clerk_sync.py` — traduce eventos de Clerk a filas
  - [x] `app/routers/webhooks.py` — verificacion de firma svix
  - [x] 16 tests con firmas generadas de verdad, no simuladas

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

### Fase 2, contra Postgres real (05-ago-2026)

| Que | Resultado |
|---|---|
| `pytest` | **33 passed** (17 de auth + 16 de webhooks) |
| Migracion aplicada dos veces | Idempotente, sin error |
| `uq_users_clerk_id` | Creado |
| Los 5 usuarios del seed | Intactos, con `clerk_id` NULL |
| `user.created` | Fila creada con email, nombre, tipo y estado correctos |
| `user.updated` | Nombre actualizado |
| `user.deleted` | `status = 'disabled'`, **la fila se conserva** |
| Reenviar el mismo `user.created` | Actualiza, no duplica: sigue habiendo 1 fila |
| Mutacion: quitar la verificacion de firma | La detectaron 3 tests |

La mutacion de la Fase 2 fue reemplazar `Webhook(...).verify(...)` por un
`json.loads()` directo. Fallaron los tests de firma de otro secreto, sin
cabeceras y cuerpo alterado. Es la propiedad que sostiene todo el endpoint:
sin ella, cualquiera que conozca la URL puede crear usuarios en cualquier
tenant.

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

**Fase 3 — frontend con `@clerk/nextjs`.** No depende de la Fase 2 y se puede
construir sin cuenta: el login queda condicional y, sin
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, renderiza el DevRoleSwitcher de siempre.
Lo que no se puede es *verla* funcionando hasta que exista la cuenta.

Despues, Fase 4 (los 13 stores pasan el token) y Fase 5 (SSO).

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
