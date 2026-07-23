# Sección A — Autenticación y Acceso (S-01, S-02, S-03)

Fuente: "Prompts de Diseño — Ambienta v1.5" (Notion) + "Análisis Funcional v1.5" (Notion), ambos actualizados 2026-07-23.

## Elementos visuales identificados (Prompts de Diseño v1.5)

- **S-01 Login**: layout centrado con tarjeta. Botón "Continuar con Microsoft" destacado (prioridad visual), botón "Continuar con Google" secundario. Sin campo email/contraseña genérico para usuarios de empresa. Estados: vacío, error de autenticación, carga. Fondo claro, mucho aire, paleta verde/turquesa.
- **S-02 Acceso Cliente Invitado**: acceso simple con RUT + clave, o vía link público. Diseño limpio y mínimo.
- **S-03 Crear Ticket/Solicitud**: accesible sin cuenta (link público) o tras login RUT+clave. Encabezado con nombre de empresa receptora + propósito. Formulario 1 columna: tipo de solicitud (selector), asunto, descripción (textarea), adjuntos (drag&drop, máx 3), nombre/correo de contacto (solo si no autenticado). Botón primario con estado de carga. Estados: vacío, error de validación, envío exitoso → confirmación con ícono, N° de ticket, botón "Volver". Mobile-first.

## Requisitos funcionales correspondientes (Notion v1.5)

- RF-01: registro/login para Clientes Invitados vía RUT + clave.
- RF-02: link público para que Clientes Invitados generen tickets sin cuenta previa.
- RF-03: todo usuario asociado obligatoriamente a una Empresa (tenant).
- RF-04: auth con Microsoft (prioridad) y Google; JWT obligatorio en todos los flujos autenticados.
- RF-05: rol "Cliente" semi-público con permisos limitados.
- RF-06: RBAC por tipo de usuario (Superadmin, Admin Empresa, Usuario Interno, Cliente, Especialista, Gestor).

## Gaps o inconsistencias detectadas

- El prompt de diseño no específica qué pasa si un usuario Microsoft/Google pertenece a más de un tenant (selector de tenant post-login) — el Esquema de Pantallas no incluye una pantalla explícita de "selector de tenant/rol". **A confirmar con producto.** Se resuelve en esta implementación con un selector simple dentro del `AuthLayout`/mock de sesión, ya que la heurística H1 exige que el tenant/rol activo sea visible siempre.
- RF-01 dice "registro e inicio de sesión... mediante RUT y clave" pero S-02 dice "RUT + clave **o** link público" — se interpreta como dos entradas alternativas al mismo flujo de Cliente Invitado (S-03), no dos pantallas separadas de acceso. **Resuelto en implementación**, no bloqueante.
- No hay mención de recuperación de contraseña para el flujo RUT+clave en los prompts (sí aparece "0.4 Recuperar contraseña" en el Esquema de Pantallas original, pero no tiene prompt S-xx propio) — se deja **fuera de esta iteración** (no es parte de S-01/S-02/S-03).

## Componentes Atomic Design necesarios

- Átomos: `Button` (variantes primary/secondary/ghost, con ícono), `Input`, `Icon`, `Spinner`/loading state del Button.
- Moléculas: `SSOButton` (ícono proveedor + texto, usado por Microsoft/Google), `FormField` (label + input + mensaje de error inline), `FileDropzone` (adjuntos).
- Organismos: `LoginCard`, `TicketForm`.
- Templates: `AuthLayout` (centrado, tarjeta, fondo claro — reutilizado por S-01, S-02, S-03).

## Datos de ejemplo necesarios (mock data)

- `mocks/users.ts`: al menos 1 usuario por cada uno de los 6 roles, repartidos en 2 tenants, con credenciales mock (no reales) para simular el login.
- `mocks/tenants.ts`: 2 tenants para poder mostrar el selector de tenant cuando un usuario mock pertenece a ambos.
- Casos límite: intento de login con credenciales inválidas (mensaje de error humano), envío de ticket exitoso vs con adjunto que excede el máximo (3 archivos).

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — loading state en botones SSO y en submit de ticket; confirmación visual tras crear ticket.
- [x] H2 Correspondencia con el mundo real — "RUT", "Empresa", nombres de rol exactos (no traducidos/inventados).
- [x] H3 Control y libertad — botón "Volver" en confirmación de ticket; cancelar no aplica a login (no hay estado intermedio que perder).
- [x] H4 Consistencia — mismo patrón de formulario (label + validación inline + error) que se reutiliza en Catálogo/Usuarios más adelante.
- [x] H5 Prevención de errores — validación de RUT y de campos obligatorios antes del submit, no después.
- [x] H9 Recuperación de errores — mensaje de error de autenticación en lenguaje humano ("No pudimos verificar tus credenciales", no "Error 401").
- [ ] H10 Ayuda y documentación — no crítico para esta sección (no hay siglas regulatorias en Auth).
