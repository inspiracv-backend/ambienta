# Tasks: Auditorías, Hallazgos y Registros de Mejora

Plan de implementación de [`proposal.md`](./proposal.md) / [`design.md`](./design.md).

> ⚠️ **Nada de esto se ejecuta hasta que la propuesta esté aprobada**
> (CLAUDE.md §1: solo se implementan features con spec aprobada).

---

## Supuestos que la entrevista con ADCLEAN derribó

La revisión 1 de esta propuesta (29-jul, mañana) se escribió antes de la
entrevista (29-jul, tarde). Estos supuestos ya no se sostienen y el modelo
cambió por ellos:

| # | Supuesto de la revisión 1 | Qué mostró la entrevista |
|---|---|---|
| S-1 | Un hallazgo pertenece siempre a una auditoría, y es la entidad raíz | La auditoría es una de cinco fuentes de detección. La mayoría de los registros no viene de una auditoría. **La raíz pasa a ser `RegistroMejora`** |
| S-3 | Una observación no se transforma: se crea un hallazgo nuevo enlazado | Sigue en pie, pero el cliente además agrupa hallazgos "concordantes"; se modela con `concordanteConIds` |
| S-5 | Toda no conformidad exige plan de acción | El cliente tiene la etapa de acción correctiva siempre, pero el plan de acción formal es opcional dentro de ella |
| S-7 | `criticidad: media` y `baja` mapean a `severidad: menor` | El cliente usa dos escalas distintas en dos sistemas (`Alta` / `Mayor`). El mapeo sigue sin resolverse — ver decisión abierta #2 |
| S-10 | Cobertura se mide sobre artículos | Sigue en pie, pero requiere que el Catálogo Normativo entregue artículos, cosa que hoy no hace |

## Supuestos vigentes

| # | Supuesto | Por qué se tomó | Si se rechaza |
|---|---|---|---|
| S-2 | `severidad` solo existe si la clasificación es `no_conformidad` | Una "conformidad mayor" no significa nada | Si se quiere graduar observaciones, el campo se generaliza |
| S-4 | La severidad la asigna el auditor, no se calcula | No hay reglas de negocio definidas para derivarla | Se necesita definir esas reglas y el campo pasa a calculado |
| S-6 | La verificación de eficacia es obligatoria antes del cierre | §10.2.1 d) la exige explícitamente | Sería cerrar sin verificar, que es un hallazgo contra el propio sistema |
| S-8 | Los eventos históricos del audit log no se reescriben | RNF-08 exige inmutabilidad | Reescribirlos violaría el requisito |
| S-9 | Una auditoría se puede cerrar con registros de mejora abiertos | La auditoría termina con su informe; el tratamiento sigue su ciclo | Bloquear el cierre acopla dos ciclos de duración muy distinta |
| S-11 | El orden de etapas por defecto es el de §10.2.1, no el del cliente | La norma manda cuando no hay razón para desviarse | Se invierte el default y ADCLEAN deja de ser un preset |
| S-12 | `riesgo` y `oportunidad` saltan corrección y análisis de causa | No hay corrección inmediata de una oportunidad | Recorren las cinco etapas con campos vacíos, que es peor dato |
| S-13 | Los conteos del informe son derivados, no capturados | Evita que informe y sistema digan cosas distintas | Se permite editarlos y hay que decidir cuál manda |
| S-14 | Los catálogos (severidad, metodologías, plazos, orden) son por tenant | Ambienta es multi-tenant; esto es convención de empresa | Se cablean los de ADCLEAN y el segundo cliente exige migración |

---

## Fase 0 — Prerequisitos fuera de este módulo

Sin esto, las fases siguientes se construyen sobre supuestos.

- [x] ~~Confirmar que el mapa de procesos expone procesos referenciables por id~~ — **resuelto**: `DepartamentoSchema` ya modela el departamento como proceso de §4.4 con `id`, `tipo`, `responsableId`, `entradas` y `salidas`. `procesoId` apunta ahí
- [ ] Determinar qué entrega hoy el **Catálogo Normativo** a nivel de artículo, y si el checklist se puede desplegar desde ahí o hay que cargarlo a mano
- [ ] Decidir dónde vive la **configuración por tenant** — hoy no hay un lugar para catálogos de empresa

## Fase 1 — Modelo compartido

- [ ] `packages/shared/src/schemas/auditoria.ts`: `Auditoria`, `SesionAuditoria`, `NotaAuditoria`, `InformeAuditoria`
- [ ] `packages/shared/src/schemas/checklist.ts`: `ItemChecklist` con la escala de cumplimiento, agrupado por capítulo y acotado por proceso
- [ ] `packages/shared/src/schemas/hallazgo.ts`: `Hallazgo` con clasificación y severidad
- [ ] `packages/shared/src/schemas/registro-mejora.ts`: `RegistroMejora` y las cuatro etapas
- [ ] `packages/shared/src/schemas/configuracion-mejoras.ts`: catálogos por tenant
- [ ] Retirar `NonConformitySchema` de `audit.ts` y dejar el archivo solo como re-export de compatibilidad
- [ ] Agregar `'hallazgo'` y `'registro_mejora'` a `EntidadAuditableSchema` (`'auditoria'` ya existe) y sus etiquetas en `ENTIDAD_LABEL`
- [ ] Agregar `'registro_mejora'` a `OrigenPlanAccionSchema`, conservando `'no_conformidad'` por compatibilidad
- [ ] Validaciones cruzadas con tests:
  - [ ] `severidad` no nula ⇒ `clasificacion === 'no_conformidad'`
  - [ ] `tipo === 'salida_no_conforme'` ⇒ `producto` presente
  - [ ] `tipo === 'reclamo'` ⇒ `reclamo` presente
  - [ ] `origenDeteccion` de auditoría ⇒ `hallazgoId` presente
  - [ ] metodología `cinco_porques` ⇒ `cincoPorques` no vacío; `espina_pescado` ⇒ `espinaPescado` no vacío
  - [ ] cierre ⇒ `seguimiento.eficaz === true` estricto, nunca truthy (los cinco campos de seguimiento son tri-estado)
  - [ ] prefijo de `Hallazgo.codigo` coherente con la clasificación (NC / OBS / OM)

## Fase 2 — Datos y stores

- [ ] Migrar los mocks actuales según la tabla §8 del design
- [ ] Agregar mocks que hoy no existen: hallazgos **conformes**, un registro por cada uno de los cinco tipos, y uno con seguimiento no eficaz (bucle de reapertura)
- [ ] Preset de `ConfiguracionMejoras` para el tenant demo
- [ ] Separar el store actual en `auditorias-store` y `mejoras-store`
- [ ] Máquina de estados con sus precondiciones + tests, incluido el flujo corto de riesgo/oportunidad
- [ ] Instrumentar el audit log en cada transición de etapa y en el bucle de reapertura

## Fase 3 — Auditoría: planificación

- [ ] **Crear auditoría** (falta por completo): tipo, rango, normas, objetivos, sitios, procesos, metodología
- [ ] Asignación de procesos por auditor dentro del equipo
- [ ] Contraparte de la organización (responsable + cargo)
- [ ] Agenda de sesiones: alta, edición y reordenamiento
- [ ] Estados de la auditoría y registro de fechas reales vs planificadas
- [ ] Campo de limitaciones del alcance

## Fase 4 — Auditoría: ejecución

- [ ] Desplegar un checklist **por proceso** desde las normas elegidas
- [ ] Pantalla de checklist agrupada por capítulo de la norma, con encabezado de auditor / auditado / fecha
- [ ] **Nota de auditoría por proceso** (PE2-R08): identificación, criterios y alcance de la muestra
- [ ] Indicador de cobertura con `no_aplica` fuera del denominador
- [ ] Crear hallazgo desde un ítem del checklist
- [ ] Hallazgos transversales, sin ítem asociado
- [ ] Enlazar hallazgos concordantes con su motivo

## Fase 5 — Auditoría: informe

- [ ] Informe con resumen ejecutivo derivado de los hallazgos
- [ ] **Matriz de resultados por proceso**, con las tres primeras columnas derivadas de nota y checklist
- [ ] Fichas de hallazgo con todos los campos del §2.5 del design
- [ ] Tasa de cierre del ciclo anterior
- [ ] Exportación a PDF (se apoya en el módulo de reportes existente)
- [ ] Cierre de auditoría

## Fase 6 — Registro de Mejora

- [ ] Formulario de alta: el **tipo** es la primera decisión y define los campos condicionales
- [ ] Alta desde un hallazgo, con los datos heredados y no reescribibles
- [ ] **Detalle como stepper**: etapas anteriores en solo lectura, actual editable
- [ ] Etapa de corrección
- [ ] Etapa de análisis de causa con selector de metodología
  - [ ] Formulario de 5 Por Qué
  - [ ] Editor de Diagrama de Pescado
- [ ] Etapa de acción correctiva, con enlace opcional a plan de acción
- [ ] Etapa de seguimiento con las cuatro preguntas de verificación como selectores de tres estados, nunca casillas
- [ ] Cierre con firma, bloqueado si el seguimiento no es eficaz
- [ ] `HistorialTimeline` montado en el detalle
- [ ] Bandejas de pendientes por etapa

## Fase 7 — Notificaciones

- [ ] Cálculo de fecha límite por etapa desde `plazosPorDefectoDias`
- [ ] Correo al asignar responsables y al avanzar de etapa
- [ ] Job periódico de plazos próximos y vencidos
- [ ] Aviso de sesión de auditoría a entrevistados
- [ ] Escalamiento según RF-42

> Esta fase es el primer consumidor real de `apps/worker` y de Resend. Hoy el
> worker es un `console.log` y no está en ningún `docker-compose`. Levantarlo es
> parte del trabajo, no un prerequisito resuelto.

## Fase 8 — Configuración por tenant

- [ ] Pantalla de catálogos: severidad, metodologías, plazos, orden de etapas, etiquetas
- [ ] Preset "ADCLEAN" documentado como ejemplo, no como default del sistema

## Fase 9 — Consecuencias

- [ ] Dashboard: contadores por etapa y % de resolución
- [ ] Reportes: filtro por tipo y clasificación
- [ ] Verificar que ningún reporte existente cambie de significado en silencio
- [ ] Revisar que el mapa de procesos no quede como dependencia rota

## Fase 10 — Documentación

- [ ] Actualizar `openspec/analisis/seccion-g-auditorias-no-conformidades.md`
- [ ] Proponer actualización del Análisis Funcional a v1.8: §3.9 pasa de 8 requisitos a cubrir el ciclo completo
- [ ] Registrar las decisiones que el equipo tome sobre los supuestos y las decisiones abiertas

---

## Orden sugerido

Fase 0 primero y de verdad: si el Catálogo Normativo no entrega artículos, la
fase 4 cambia de forma y conviene saberlo antes de escribir el schema.

Después 1 y 2 — sin el modelo y los datos, las pantallas no se pueden construir
ni evaluar.

Luego el módulo se puede partir en dos entregas independientes:

- **Entrega A (fases 3 a 5):** el ciclo de auditoría. Valor visible: hoy no se
  puede ni crear una auditoría.
- **Entrega B (fase 6):** el registro de mejora con su stepper. Es lo que el
  cliente pidió explícitamente y lo que reemplaza su Power Apps.

La B no depende de la A si se acepta que un registro se cree con origen
distinto de auditoría — que es el caso mayoritario.

Las fases 7 y 8 se pueden diferir sin bloquear a nadie, pero la 7 es la que
hace que el sistema empuje el trabajo en vez de esperarlo, y es la diferencia
entre un registro y una herramienta de gestión.

**Estimación de alcance:** es el cambio más grande pedido hasta ahora. Cinco
entidades nuevas en el paquete compartido, dos stores, seis pantallas nuevas,
cinco existentes modificadas, y el primer uso real del worker.
