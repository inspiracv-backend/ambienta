# Tareas — Escrituras de la interfaz

## Supuestos vigentes

Verificados contra el contrato OpenAPI y los mappers reales, no supuestos.

- **19 de 37 acciones que mutan estado llegan a la base.** Las otras 18 solo
  tocan estado local.
- El mapper de `tenants` trae `limiteUsuarios: 50` y `modulosActivos: []`
  **escritos a mano**, no de la API.
- El mapper de `audits` **no lee** `improvement_stages` ni `root_cause_answers`,
  aunque `NonconformityUpdate` acepta ambos.
- El mapper de `support` **no lee** `is_internal`.
- `users` es el único caso donde la lectura ya funciona: el mapper trae
  `department_id` y `UserUpdate` lo acepta.
- `TenantUpdate` acepta `legal_name`, `trade_name`, `business_activity`,
  `status` y `settings`. **No acepta `rut_tax_id`.**
- `ActionPlanUpdate` no tiene ningún campo para tareas.
- `ToastProvider` envuelve a los 12 stores, así que se puede avisar desde ahí.

## Supuestos por confirmar

- [x] **Forma de `settings`.** Resuelto: esquema declarado en
      `packages/shared` (`TenantSettingsSchema`), con lectura tolerante
- [ ] **Si el parpadeo de la escritura optimista molesta** en conexiones lentas
      reales, no en local
- [ ] **Si `completarPerfilEmpresa` debe existir** como acción, dado que la API
      no deja editar el RUT

## Fase 0 — Prerequisitos fuera de este módulo

- [x] Mensaje legible desde el error de la API, incluido el `detail` como lista
- [x] Superficie para avisar del fallo sin inventar interfaz nueva

## Fase 1 — El lado de lectura

**Va primero. Conectar la escritura sin esto cambia un engaño por otro.**

- [x] `tenants`: leer límite de usuarios, módulos y logo desde `settings`, con
      los valores de hoy como respaldo cuando la clave no está
- [ ] `audits`: leer `improvement_stages` y `root_cause_answers`. **Bloqueado**:
      el store pide `/audits/nonconformities/` y **descarta la respuesta**, asi
      que primero hay que mapear la entidad entera
- [ ] ~~`support`: leer `is_internal`~~ **No aplica**: `setVisibilidad` opera
      sobre el ticket, no sobre el mensaje, y `SupportTicketUpdate` no tiene
      ese campo
- [x] Verificar que un tenant sin `settings` sigue cargando

## Fase 2 — El lado de escritura

- [x] `users.updateDepartamento`
- [ ] `audits.updateEtapas` y `audits.updatePorques` — **bloqueadas por la Fase 1**
- [ ] ~~`support.setVisibilidad`~~ — **bloqueada**: la API no modela el campo
- [x] `tenants.setLimiteUsuarios`, `setModulosActivos` y `updateLogo`
- [x] **Fusionar `settings`, nunca reemplazarlo**: dos pantallas no deben
      pisarse los valores
- [x] Revertir y avisar cuando la API rechaza

## Fase 3 — Lo que no se conecta

- [x] Docstring en cada una con la causa concreta, no un "pendiente"
- [x] `completarPerfilEmpresa`: la API no acepta `rut_tax_id`
- [x] `toggleTarea`: las tareas del plan no existen en el modelo

## Fase 4 — Verificación

- [x] Tests del viaje completo: escribir, y que el valor sobreviva a releer
- [x] Test de reversión: la API rechaza y la pantalla vuelve al valor anterior
- [ ] Test de reversión parcial: de varios, solo se revierten los que fallaron
- [x] **Romper a propósito** lo que cada test dice proteger
- [x] Medir de nuevo la razón de acciones conectadas

## Fase 5 — Documentación

- [x] `docs/` con el inventario de las 37 acciones y la causa de cada hueco
- [x] Actualizar el estado del proyecto en `CLAUDE.md`
- [ ] Archivar el cambio

## Orden sugerido

**Fase 1 antes que la 2, sin excepción.** Es el error que este cambio corrige:
escribir un campo que se lee de un valor fijo del código no arregla nada, y deja
la sensación de que sí.
