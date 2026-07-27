# Sección Perfil Empresa y Departamentos (nueva en v1.7)

Fuente: "Análisis Funcional v1.7" (Notion, 27-jul-2026), sección 3.2.1 y Decisión cerrada #13. **No existe un prompt de diseño propio** para este flujo en "Prompts de Diseño — Ambienta v1.5" (Notion) — es un requisito nuevo introducido en v1.7 que no estaba en el mapa de 43 pantallas original. Se documenta aquí como gap y se construye adaptando el patrón visual de wizard ya usado en S-04 (barra de progreso + pasos + Atrás/Continuar), el precedente más cercano disponible.

## Relación con el mapa de pantallas existente

El área más cercana en "Prompts de Diseño v1.5" es **S-43 · Configuración de la Empresa** (Sección N): *"Datos de la empresa, plantas/instalaciones y configuración general del tenant."* v1.7 (Decisión cerrada #13) **eleva esa misma superficie a un flujo obligatorio de primer uso** y le agrega la entidad Departamentos. Esta sección implementa esa versión obligatoria; cuando se aborde el resto de la Sección N (S-41 Gestión de Usuarios, S-42 Perfil de Usuario), **no se debe reconstruir S-43** — ya está cubierto aquí.

## Requisitos funcionales correspondientes (v1.7)

- RF-10: el sistema debe forzar el flujo de Perfil Empresa como primer paso del Admin Empresa, antes de operar Matriz Legal u Obligaciones.
- RF-11: todo Usuario Interno debe pertenecer obligatoriamente a un Departamento definido en el Perfil Empresa.
- RF-12: el Perfil Empresa gestiona plantas, departamentos, trabajadores y matriz de permisos.

## Elementos visuales implementados

Wizard de 5 pasos (`PerfilEmpresaWizard`), con indicador de progreso clicable hacia atrás (no hacia adelante sin completar):
1. **Datos de la empresa**: razón social y RUT de solo lectura (ya existen del alta del tenant) + giro y dirección editables (obligatorios para continuar).
2. **Plantas/Instalaciones**: lista de plantas existentes + alta de nuevas (nombre, comuna, región). Requiere al menos 1 planta para continuar.
3. **Departamentos**: lista + alta de nuevos departamentos (solo nombre). Requiere al menos 1 para continuar (RF-11).
4. **Trabajadores y permisos**: tabla de solo lectura (nombre, rol, departamento asignado).
5. **Confirmación**: resumen + botón "Finalizar" que marca `Tenant.perfilEmpresaCompleto = true` y redirige a `/dashboard`.

`PerfilEmpresaGate` (organismo cross-cutting, no vive en `DashboardLayout` para no romper su convención documentada de "sin lógica de negocio"): si `user.role === 'admin_empresa'` y `tenant.perfilEmpresaCompleto === false`, redirige a `/perfil-empresa` antes de renderizar cualquier otra pantalla del `(dashboard)`.

## Gaps o inconsistencias detectadas

- **Trabajadores y permisos es de solo lectura en esta iteración.** Asignar/reasignar el departamento de un trabajador existente, invitar nuevos usuarios y editar la matriz de permisos (RF-12) requieren un store de mutación de `User` que no existe todavía — eso es exactamente el alcance de **S-41 Gestión de Usuarios y Roles** (Sección N, pendiente). Se deja como gap explícito para no duplicar trabajo.
- **Edición/eliminación de plantas y departamentos ya creados** no está implementada (solo alta) — simplificación aceptada dado que no hay prompt de diseño que especifique ese detalle.
- El gate solo aplica a `admin_empresa` (texto literal de RF-10). Los tenants tipo Gestor (rol `gestor`) no quedan bloqueados — el análisis funcional no menciona un flujo equivalente para ellos.
- Ambos tenants mock (`tenant-1`, `tenant-2`) se modelan con `perfilEmpresaCompleto: true` (tenants ya operando, coherente con todas las secciones ya verificadas en sesiones anteriores) — el gate bloqueante se verifica en vivo alternando ese flag vía la consola del navegador (`useTenants` no expone un botón de "reiniciar" porque no tiene sentido de negocio real, solo de demo).

## Componentes Atomic Design necesarios

- Átomos: reutiliza `Button`, `Input`, `Spinner`.
- Moléculas: reutiliza `FormField`.
- Organismos: `PerfilEmpresaGate` (nuevo, cross-cutting), `PerfilEmpresaWizard` (nuevo).
- Templates: ninguno nuevo — `DashboardLayout` se mantiene libre de esta lógica a propósito.

## Datos de ejemplo necesarios (mock data)

- Nuevo `packages/shared/src/schemas/departamento.ts` (`Departamento`).
- `Tenant` extendido con `giro`, `direccion`, `perfilEmpresaCompleto`.
- `User` extendido con `departamentoId` (obligatorio conceptualmente para `usuario_interno`, `null` para el resto).
- Nuevo `mocks/departamentos.ts`: 3 departamentos para tenant-1, 1 para tenant-2.

## Checklist de heurísticas de Nielsen aplicables

- [x] H1 Visibilidad del estado — barra de pasos siempre visible, paso activo resaltado.
- [x] H3 Control y libertad — botón "Atrás" y pasos ya completados son clicables para revisar/editar.
- [x] H5 Prevención de errores — "Continuar" deshabilitado hasta completar los campos obligatorios de cada paso (giro/dirección, al menos 1 planta, al menos 1 departamento).
- [x] H6 Reconocer antes que recordar — cada paso muestra los datos ya ingresados (razón social, RUT, plantas y departamentos existentes) en vez de pedirlos de nuevo.
- [x] H8 Diseño minimalista — un paso a la vez, sin campos fuera de contexto.
- [x] H10 Ayuda y documentación — nota explícita en el paso de Trabajadores aclarando que la edición vive en Usuarios y Roles (evita prometer una acción que no existe todavía, H1).
