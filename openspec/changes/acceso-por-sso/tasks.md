# Tareas — Acceso por SSO con alta controlada

## Supuestos vigentes

Verificados leyendo el sistema real, no heredados del análisis.

- `auth.py` responde **401** tanto si el token es ilegible como si es válido sin
  `tenant_id`. Las dos ramas comparten el mismo `raise`.
- El puente de Clerk **no redirige** cuando la API da 401 con sesión viva: solo
  escribe en la consola. Es deliberado, para no armar un bucle.
- La sincronización exige `tenant_id` en el metadata del proveedor y responde
  **400** si falta. El 400 es correcto: reintentar no lo arregla.
- **`users.tenant_id` es `NOT NULL`.** Una persona autenticada sin empresa hoy
  no se puede guardar como fila.
- `users.email` es único, y la sincronización busca por identificador del
  proveedor y después por correo, así que adopta en vez de duplicar.
- El registro público **sigue abierto**: existe la pantalla y el proveedor lo
  permite.
- Sin llave del proveedor, el DevRoleSwitcher y `X-Tenant-Id` funcionan igual.

## Supuestos por confirmar

**No empezar la fase que depende de cada uno sin resolverlo.**

- [ ] **Vinculación de cuentas entre proveedores.** Si Microsoft y Google no se
      vinculan, cada persona queda atada al último proveedor usado. Bloquea
      poder prometer los dos proveedores a la vez (Fase 1)
- [ ] **Entra ID con cuentas externas.** Un directorio restringido puede
      rechazar contratistas, que son el negocio de los Gestores. Es el pendiente
      que ADR-006 dejó abierto. Bloquea prometer Microsoft SSO (Fase 1)
- [ ] **Cuántos usuarios hay hoy en el proveedor sin fila en la base**, creados
      por el registro abierto. Bloquea la Fase 2
- [ ] **Texto exacto de la pantalla sin empresa.** Debe ayudar sin revelar si esa
      empresa existe en el sistema. Bloquea la Fase 4
- [ ] **Si se registra el evento y dónde.** Sin esto, un empleado nuevo
      bloqueado es invisible hasta que reclama

## Fase 0 — Prerequisitos fuera de este módulo

**Todo esto es panel, no código, y lo hace el equipo.** No empezar la Fase 4 sin
la Fase 0 resuelta: es la lección del JWT Template, verificar el proveedor antes
de construir encima.

- [ ] App Registration en Azure / Entra ID, con la URI de retorno **del
      proveedor de identidad, no nuestra**
- [ ] OAuth Client en Google Cloud Console, con la misma URI de retorno
- [ ] Cargar ambos pares de credenciales en el panel del proveedor
- [ ] **Probar cada proveedor con una cuenta real** antes de dar por buena la
      configuración
- [ ] Probar el mismo correo por los dos proveedores y confirmar que resulta
      **una sola** identidad
- [ ] Revisar la lista de usuarios creados por el registro abierto

## Fase 1 — Cerrar el registro

- [ ] Desactivar el registro público en el panel del proveedor. **Es la que
      manda**: sin esto, la API del proveedor sigue aceptando altas
- [ ] Retirar la pantalla de registro propio de la web
- [ ] Confirmar que la ruta retirada no deja un enlace muerto en el ingreso
- [ ] Verificar que quien ya tenía cuenta creada por el registro abierto cae en
      el estado sin empresa, y no en un error crudo

## Fase 2 — La API distingue los dos fallos

- [ ] Separar "no pude verificar la identidad" de "identidad verificada sin
      empresa": la primera sigue en 401, la segunda pasa a **403**
- [ ] Marcador legible por máquina en el cuerpo, **no un texto** — el texto se
      traduce y se reescribe
- [ ] Que no colisione con el 403 que ya devuelve la comprobación de admin
      global: son dos negativas distintas
- [ ] Registrar el evento con el identificador del proveedor, para que alguien
      pueda enterarse
- [ ] Ajustar los tests que hoy afirman 401 para el token sin empresa. **Son la
      prueba de que el comportamiento cambió**, no un estorbo
- [ ] Tests de los dos caminos, rompiendo a propósito lo que dicen proteger

## Fase 3 — La sincronización

- [ ] Confirmar que un alta sin empresa en el metadata sigue sin crear fila
- [ ] Que el rechazo quede registrado con datos suficientes para actuar
- [ ] Verificar que adoptar por correo no deja huérfana la identidad anterior
      cuando alguien alterna de proveedor
- [ ] Tests con los dos proveedores sobre el mismo correo

## Fase 4 — La pantalla

**Bloqueada por el texto exacto (supuesto por confirmar).**

- [ ] El puente publica el estado en vez de solo escribir en consola
- [ ] Pantalla propia: qué pasa, a quién pedirle el acceso, y **cerrar sesión**
- [ ] Sin cerrar sesión, quien entró con la cuenta equivocada queda atrapado:
      la sesión sobrevive al refresco
- [ ] Que no revele si la empresa de ese dominio existe en el sistema
- [ ] Que no redirija al ingreso: es lo que arma el bucle
- [ ] Verificar que el modo sin proveedor **no cambia en nada**
- [ ] Tests del estado y de que el cierre de sesión funciona desde ahí

## Fase 5 — Verificación de punta a punta

- [ ] Persona dada de alta entra con Microsoft → su tablero, con sus datos
- [ ] La misma con Google → **la misma** identidad, no una segunda
- [ ] Persona sin alta entra con cualquiera de los dos → pantalla explicada, no
      tablero vacío
- [ ] Esa misma persona, conociendo la dirección exacta de un dato de negocio →
      se le niega
- [ ] Se la da de alta, vuelve a entrar → tablero normal
- [ ] Intento de registro propio → rechazado
- [ ] Sin llave del proveedor → DevRoleSwitcher intacto

## Fase 6 — Documentación

- [ ] `docs/development/setup-local.md`: que el alta es manual mientras no
      exista la invitación, y cómo se hace
- [ ] Anotar en `integracion-clerk-auth` que su Fase 5 la cubre este cambio
- [ ] **Archivar `integracion-clerk-auth` ANTES que este cambio.** Este delta
      lleva un `MODIFIED` sobre "Inicio de sesión con cuenta corporativa", que
      hoy solo existe dentro de aquel cambio: `openspec/specs/autenticacion/`
      todavía no existe. Archivar en el otro orden intentaría modificar un
      requisito ausente
- [ ] Archivar: fundir los deltas en `openspec/specs/`

## Orden sugerido

**Fase 0 antes que nada.** Sin verificar los proveedores con cuentas reales, la
Fase 4 se construye sobre un supuesto — que es exactamente cómo se perdió una
tarde con el JWT Template.

Las fases 2 y 3 son de la API y pueden ir en paralelo con la 1. La Fase 4
depende de la 2: sin el marcador, el frontend no tiene qué detectar.

Este cambio **no cierra el asunto**: mientras `credenciales-de-acceso` no
construya la invitación, dar de alta sigue siendo manual. Lo que sí hace es que
el hueco deje de ser un tablero vacío sin explicación.
