# Sección N — Usuarios, Roles y Perfil (S-41, S-42)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.7" (Notion, 27-jul-2026).

> **Nota de alcance**: el mapa original de esta sección incluía S-43 Configuración de la Empresa. v1.7 (Decisión cerrada #13) elevó esa pantalla a un flujo obligatorio propio — ya implementado como **Perfil Empresa** (`openspec/analisis/seccion-perfil-empresa.md`, GitHub issue #15, cerrada). Esta sección cubre únicamente lo que queda: **S-41 Gestión de Usuarios y Roles** y **S-42 Perfil de Usuario**.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-41 Gestión de Usuarios y Roles** (Actor: Admin Empresa): tabla (avatar/inicial, nombre, email, rol badge, planta asignada, estado, última actividad). Barra superior: buscador + filtro + botón "Invitar usuario". Modal de invitación: email, selector de rol (con descripción breve), selector de planta(s). Menú de acciones por fila: editar rol, reasignar planta, desactivar (con confirmación). Estado vacío para tenants nuevos.
- **S-42 Perfil de Usuario** (Actor: todos): datos personales, cambio de contraseña, sesiones activas y preferencias.

## Requisitos funcionales correspondientes (v1.7)

- RF-08: sistema de roles y permisos por tipo de usuario (Superadmin, Admin Empresa, Usuario Interno, Cliente, Gestor) con RBAC.
- RF-04: JWT obligatorio para todos los flujos autenticados (fuera de alcance del frontend mock).
- RF-06: un usuario que entra con Google/Microsoft puede posteriormente setear una clave local (RUT + clave) — parte de S-42.
- RF-11 (Perfil Empresa, v1.7): todo Usuario Interno pertenece obligatoriamente a un Departamento — S-41 es donde se reasigna en la práctica (cierra el gap dejado en `seccion-perfil-empresa.md`).

## Gaps o inconsistencias detectadas

- **No existe backend de invitación real** (envío de email, aceptación, JWT) — "Invitar usuario" crea el registro inmediatamente con `estado: 'invitado'` en el store en memoria. El envío real del correo de invitación depende de Resend, ya documentado como fuera de alcance en la Sección J.
- **Cambio de contraseña (S-42)** es un formulario mock: valida coincidencia y longitud mínima, pero no hay contraseña real detrás (no hay backend de auth) — se muestra un mensaje de éxito sin persistir nada.
- **Sesiones activas (S-42)** se modelan como una lista estática de ejemplo (no hay tabla de sesiones real ni JWT) — "Cerrar sesión" en una sesión de la lista solo la quita visualmente de esa lista; no afecta la sesión real del usuario (para eso ya existe "Cerrar sesión" en `AppHeader`).
- **Preferencias (S-42)** no se duplica: ya existe `NotificationPreferencesForm` (S-32, Sección J) — el Perfil de Usuario enlaza a `/notificaciones/configuracion` en vez de reconstruir el formulario (H4).
- **RF-03 pendiente** (registrar como usuario permanente a un Cliente Invitado que generó tickets) sigue sin resolverse: requeriría seleccionar un contacto de `SupportTicket` y convertirlo en `User`, un flujo de integración cross-sección que no tiene pantalla propia en el Esquema — se deja fuera de esta iteración, documentado explícitamente (ya se había marcado como gap en `seccion-a-autenticacion.md`).
- **Selector de rol en "Invitar usuario"** se acota a los roles que un Admin Empresa puede asignar dentro de su propio tenant (`admin_empresa`, `usuario_interno`, y `gestor` solo si `tenant.esGestor`) — `superadmin` y `cliente_invitado` no aparecen ahí (Superadmin es de plataforma, Cliente Invitado se genera vía el flujo de tickets, no por invitación directa).
- **Reasignación de planta y departamento** (dejada como gap en `seccion-perfil-empresa.md`, paso "Trabajadores") ahora se resuelve aquí, en `UserFormModal`. El paso "Trabajadores" del wizard de Perfil Empresa se actualiza para enlazar a `/usuarios` en vez de decir "próximamente".
- **`lib/get-user-name.ts` sigue leyendo del array estático `mocks/users.ts`**, no del estado en vivo de `UsersProvider` — si se renombra un usuario desde S-42, las columnas "Responsable" de Matriz Legal/Obligaciones/Auditorías (que usan `getUserName(id)`) seguirán mostrando el nombre original hasta recargar la página (y tras recargar, vuelven al nombre original de todos modos, porque nada persiste sin backend). Convertir `getUserName` en un hook conectado a `useUsers()` afectaría a más de media docena de componentes ya construidos — se documenta como inconsistencia aceptada en vez de hacer ese refactor ahora, dado el impacto puramente cosmético y acotado a esta sesión sin persistencia real.

## Componentes Atomic Design necesarios

- Átomos: reutiliza `Avatar`, `Button`, `Input`.
- Moléculas: reutiliza `FormField`, `FilterBar`.
- Organismos: `UserFormModal` (S-41, invitar/editar en un solo componente parametrizado — evita duplicar ~90% del formulario), `UsersManagementTable` (S-41, incluye confirmación de desactivar igual criterio que `TenantsManagementTable`), `UserProfileView` (S-42).
- Templates: ninguno nuevo.

## Datos de ejemplo necesarios (mock data)

- `User` extendido con `estado: 'activo' | 'invitado' | 'desactivado'` y `ultimaActividad: string | null`.
- Los 6 usuarios mock existentes se completan con esos campos (todos `activo` con fechas de actividad recientes, ya que son usuarios ya operando en las secciones previas).
- Sesiones activas de ejemplo: lista estática inline en `UserProfileView` (no amerita su propio schema — ver gap arriba).

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — badge de estado de usuario (activo/invitado/desactivado) siempre visible en la tabla.
- [x] H2 Correspondencia con el mundo real — nombres de rol exactos (`ROLE_LABEL`), sin inventar sinónimos.
- [x] H4 Consistencia — mismo patrón de confirmación de `TenantsManagementTable` (Sección L) para desactivar usuario; Preferencias reutiliza el formulario existente en vez de duplicarlo.
- [x] H5 Prevención de errores — confirmación explícita antes de desactivar un usuario (impacto en acceso real); un usuario no puede desactivarse a sí mismo (evita auto-bloqueo).
- [x] H6 Reconocer antes que recordar — buscador/filtros persistentes y visibles; formulario de edición pre-llenado con los datos actuales del usuario.
- [x] H9 Recuperación de errores — mensajes humanos si el cambio de clave no coincide o es muy corta.
- [x] H10 Ayuda y documentación — descripción breve de cada rol visible en el selector del modal de invitación (evita que el Admin Empresa asigne un rol sin entender qué implica).
