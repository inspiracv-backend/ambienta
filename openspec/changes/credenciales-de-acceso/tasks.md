# Tareas — Credenciales de acceso

## Supuestos vigentes

Verificados contra el sistema real, no heredados del análisis.

- Clerk rechaza un `username` puramente numérico (`Username must contain one
  non-number character`) y no admite puntos. Probado el 10-ago-2026 contra la
  instancia `rapid-octopus-10` con los 5 formatos de la tabla de design.
- `users` ya tiene `rut_tax_id`, `password_hash` y `clerk_id`, las tres vacías
  en las 5 filas de demo.
- `user_type` admite `guest` por CHECK.
- La API no hace ninguna llamada saliente a Clerk. Confirmado por búsqueda de
  `api.clerk.com`, `CLERK_SECRET`, `invitation` en `apps/api/app/`.
- `CLERK_SECRET_KEY` llega al servicio `web`, no al de la API.
- `lib/rut.ts` calcula el dígito verificador pero no valida uno escrito.
- `/acceso-invitado` es ruta pública en el middleware y no pasa por Clerk.

## Supuestos por confirmar

**No empezar la fase que depende de cada uno sin resolverlo.**

- [ ] **El invitado no es cuenta de Clerk** (D2). Decisión abierta #1 del
      proposal. Bloquea la Fase 4 entera
- [ ] **Vigencia del acceso de invitado**: propuesta 30 días. Bloquea la Fase 4
- [ ] **RUT global vs por empresa** (decisión abierta #3). Si el equipo dice
      que un contratista debe servir a dos empresas, **este diseño se revisa
      antes de codear**: `users.tenant_id` es una sola columna
- [ ] **Registro público**: sigue sin decidirse desde el cambio de Clerk. Con
      `username` habilitado y registro abierto, cualquiera reclama un RUT ajeno
- [ ] **Verificación del RUT**: nada comprueba que el RUT sea de esa persona.
      ¿Alcanza el dígito verificador o se exige algo más?

## Fase 0 — Prerequisitos fuera de este módulo

- [ ] **Habilitar Username como identificador** en el dashboard de Clerk
      (Configure → Email, phone, username). Sin esto el RUT no sirve para
      ingresar, aunque se guarde bien
- [ ] Confirmar con una prueba que un usuario con `username` puede iniciar
      sesión con él **antes** de escribir el formulario. Es la lección del
      template: verificar el proveedor antes de construir encima
- [ ] Decidir el cierre del registro público
- [ ] Definir cómo se prueba el webhook en local: túnel o esperar al VPS

## Fase 1 — Cliente saliente hacia Clerk

- [ ] `CLERK_SECRET_KEY` al servicio `api` en compose y `.env.example`
- [ ] Módulo con las llamadas salientes: crear invitación, fijar username,
      fijar clave. Aislado como `auth.py`, para que cambiar de proveedor siga
      siendo reescribir un archivo (ADR-006)
- [ ] Manejo de fallos del proveedor: distinguir "rechazó" de "no respondió".
      El segundo no debe dejar la fila creada (D4)
- [ ] Tests con el cliente HTTP simulado
- [ ] **Prueba contra la instancia real**, no solo simulada: crear una
      invitación de verdad y borrarla

## Fase 2 — Invitación de usuarios

- [ ] Endpoint de invitación: crea en Clerk y después la fila (orden de D4)
- [ ] Verificar Admin Empresa. Mínimo viable, se reemplaza cuando entre
      `sistema-actores-roles-rbac`
- [ ] Rechazar invitar a una empresa distinta a la propia
- [ ] Que `clerk_sync` adopte la invitación consumida sin duplicar fila
- [ ] Pantalla de invitación conectada al endpoint. Hoy `inviteUser` del store
      escribe local y hace POST a `/users/`, que no crea identidad
- [ ] Tests de los 5 escenarios del requisito de invitación

## Fase 3 — RF-06, clave local con RUT

- [ ] `validarRut()` y `normalizarRut()` en `lib/rut.ts` con sus tests,
      incluidos verificador K y los tres formatos de escritura
- [ ] Gemelo en Python: el modelo se escribe dos veces y ya se desincronizó
- [ ] Endpoint para fijar RUT y clave local del usuario autenticado
- [ ] Rechazar RUT ya usado sin revelar de quién es
- [ ] Guardar en `users.rut_tax_id` además del username (D5)
- [ ] Pantalla en el perfil (S-42) para fijar la clave
- [ ] Pestaña de RUT en el ingreso, con formulario propio (D1)
- [ ] Confirmar que el ingreso por SSO sigue funcionando después de fijar clave
- [ ] Tests de los 6 escenarios del requisito de clave local

## Fase 4 — RF-02/RF-07, acceso real del invitado

**Bloqueada por las decisiones abiertas #1 y #2.**

- [ ] Migración `db/NN_*.sql` idempotente para las credenciales de invitado,
      **con su propia política RLS y sus GRANT** — el bucle de `01_schema`
      corre una sola vez. Agregarla a los 4 puntos de sincronización: los dos
      compose, `db/run.sh` y `db/README.md`
- [ ] Emisión de credenciales: RUT y clave persistidos con vigencia
- [ ] Validación de credenciales de invitado, separada de la de Clerk (D3)
- [ ] Dependencia propia para los endpoints que el invitado sí puede tocar
- [ ] Reemplazar `generateMockRut()` y `generateDynamicPassword()` del
      navegador por la emisión del servidor
- [ ] Que un invitado solo vea sus propias solicitudes
- [ ] Tests de los 7 escenarios del requisito de invitado, incluidos los tres
      de negación: credencial inventada, vencida, y de otra empresa

## Fase 5 — Comprobación contra la instancia real

- [ ] Script que emite un token con la clave secreta, pega a la API y verifica
      200 más la presencia del claim
- [ ] Extenderlo a los tres caminos: correo, RUT e invitado
- [ ] Job programado con secretos, **separado del CI de cada PR** porque
      depende de un servicio externo
- [ ] Documentar en `CLAUDE.md` la regla que faltaba: verificar contra el
      proveedor real antes de escribir el código que depende de él

## Fase 6 — Documentación

- [ ] `db/README.md` con la tabla nueva y el conteo de RLS actualizado
- [ ] `.env.example` y ambos compose
- [ ] Cómo dar de alta un usuario en local mientras el webhook no llegue
- [ ] Archivar el cambio: fundir los deltas en `openspec/specs/`

## Orden sugerido

Fase 0 antes que nada: sin `username` habilitado, la Fase 3 no se puede probar.

Fase 1 es prerrequisito de 2 y 3. La Fase 4 es independiente de las tres
primeras y puede ir en paralelo **una vez desbloqueadas sus decisiones** — no
toca Clerk.

La Fase 5 conviene empezarla junto con la 1: es la que habría atrapado el
problema del JWT Template.
