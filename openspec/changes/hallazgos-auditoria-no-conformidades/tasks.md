# Tasks: Hallazgos de auditoría y gestión de no conformidades

Plan de implementación de [`proposal.md`](./proposal.md) / [`design.md`](./design.md).

> ⚠️ **Nada de esto se ejecuta hasta que la propuesta esté aprobada**
> (CLAUDE.md §1: solo se implementan features con spec aprobada).

---

## Supuestos tomados en el diseño

Se listan para que se puedan rechazar uno por uno en la revisión. Cada uno
cambia el modelo si se decide distinto.

| # | Supuesto | Por qué se tomó | Si se rechaza |
|---|---|---|---|
| S-1 | Un hallazgo pertenece siempre a una auditoría | ISO 19011 define el hallazgo como resultado de *una auditoría* | Habría que permitir hallazgos sueltos y darles otro nombre (¿"desviación"?) |
| S-2 | `severidad` solo existe si el tipo es `no_conformidad` | Una "conformidad mayor" no significa nada | Si se quiere graduar observaciones, el campo se generaliza |
| S-3 | Una observación **no** se transforma en no conformidad: se crea un hallazgo nuevo que la referencia | Transformar el registro original destruye la trazabilidad de qué se dijo en su momento | Se agrega transición de tipo, con el tipo anterior en el audit log |
| S-4 | La severidad la asigna el auditor, no se calcula | No hay reglas de negocio definidas para derivarla | Se necesita definir esas reglas y el campo pasa a calculado |
| S-5 | Toda no conformidad exige plan de acción antes de cerrarse | Es el caso habitual en certificación | §10.2 solo exige *evaluar* la necesidad; habría que permitir cerrar con justificación documentada |
| S-6 | La verificación de eficacia es obligatoria antes del cierre | §10.2.1 e) la exige explícitamente | Sería cerrar sin verificar, que es un hallazgo contra el propio sistema |
| S-7 | `criticidad: media` y `baja` mapean ambas a `severidad: menor` | La escala actual tiene 3 valores y la de certificación 2 | Se necesita definir el mapeo con el equipo |
| S-8 | Los eventos históricos del audit log no se reescriben | RNF-08 exige inmutabilidad | Reescribirlos violaría el requisito |
| S-9 | Una auditoría se puede cerrar con no conformidades abiertas | La auditoría termina con su informe; las NC siguen su ciclo | Bloquear el cierre acopla dos ciclos de duración muy distinta |
| S-10 | Cobertura se mide sobre artículos, no sobre normas completas | Una norma parcialmente auditada no es "auditada" | Si el detalle por artículo es demasiado, se mide por norma |

---

## Fase 1 — Modelo compartido

- [ ] Crear `packages/shared/src/schemas/hallazgo.ts` con `HallazgoSchema`, `TipoHallazgoSchema`, `SeveridadSchema`
- [ ] Reescribir `audit.ts`: `Auditoria` con rango de fechas, estados y equipo auditor
- [ ] Mover `NonConformity` a `no-conformidad.ts` con la nueva forma (tratamiento + verificación de eficacia)
- [ ] Agregar `'hallazgo'` a `EntidadAuditableSchema` del audit log
- [ ] Validación cruzada: `severidad` no nula ⇒ `tipo === 'no_conformidad'`
- [ ] Tests del schema, incluida la regla anterior

## Fase 2 — Datos y stores

- [ ] Actualizar mocks: dividir las NC actuales en hallazgo + tratamiento, y **agregar hallazgos conformes** (hoy no existe ninguno, y sin ellos no se puede evaluar la pantalla)
- [ ] `audits-store`: separar `hallazgos` de `noConformidades`
- [ ] Instrumentar el audit log en las transiciones nuevas, especialmente la verificación de eficacia y el bucle de reapertura
- [ ] Máquina de estados con sus precondiciones + tests

## Fase 3 — Auditorías

- [ ] **Crear auditoría** (falta por completo): tipo, rango de fechas, normas, procesos, equipo
- [ ] Detalle de auditoría: desplegar requisitos a auditar desde las normas elegidas
- [ ] Indicador de cobertura
- [ ] Quitar el acceso directo a No Conformidades desde la auditoría
- [ ] Cierre de auditoría con conclusiones (informe)

## Fase 4 — Registro de hallazgos

- [ ] Rediseñar S-24: el **tipo** es la primera decisión del formulario
- [ ] Campos de tratamiento visibles solo si es no conformidad
- [ ] Evidencia obligatoria y separada de la descripción
- [ ] Selector de requisito auditado

## Fase 5 — Gestión de No Conformidades

- [ ] Módulo propio con la máquina de estados
- [ ] Corrección inmediata (§10.2.1 a)
- [ ] 5 ¿Por qué? + causa raíz (ya existe, se mueve)
- [ ] Enlace al plan de acción
- [ ] **Verificación de eficacia** — la etapa que hoy falta
- [ ] Cierre con firma, bloqueado si la verificación no es eficaz
- [ ] `HistorialTimeline` montado en el detalle

## Fase 6 — Consecuencias

- [ ] Dashboard: recalcular el contador sobre no conformidades reales
- [ ] Reportes: filtro por tipo de hallazgo
- [ ] Carpeta de auditoría: incluir hallazgos conformes
- [ ] Revisar que los reportes existentes no cambien de significado en silencio

## Fase 7 — Documentación

- [ ] Actualizar `openspec/analisis/seccion-g-auditorias-no-conformidades.md`
- [ ] Actualizar README con el modelo nuevo
- [ ] Registrar en el análisis las decisiones que el equipo tome sobre los supuestos

---

## Orden sugerido

Fases 1 y 2 primero: sin el modelo y los datos, las pantallas no se pueden
construir ni evaluar. La fase 5 (gestión de NC) es la que aporta el valor
diferencial —hoy no existe— y la 3 la que cierra el hueco más visible (no se
puede crear una auditoría).

**Estimación de alcance:** es el cambio más grande pedido hasta ahora en el
frontend. Toca 3 entidades del paquete compartido, 2 stores, 5 pantallas
existentes y agrega 1 módulo nuevo.
