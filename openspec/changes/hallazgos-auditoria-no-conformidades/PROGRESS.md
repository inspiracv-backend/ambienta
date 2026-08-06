# Progreso: Auditorias, Hallazgos y Registros de Mejora

**Ultima actualizacion:** 2026-08-04

## Estado actual

**Fase actual:** Spec completada (revision 2), pendiente de aprobacion.
**Nada implementado** — siguiendo SDD, se espera aprobacion antes de escribir codigo.

## Completado

- [x] Spec v1: proposal.md + design.md + tasks.md (commit 7caf293)
- [x] Spec v2: reescritura post-entrevista con ADCLEAN (commit ec8ed2e)
  - 5 supuestos derribados por la entrevista documentados en tasks.md
  - RegistroMejora como entidad raiz (no Hallazgo)
  - Modelo completo: 6 entidades, maquina de estados, configuracion por tenant
- [x] Fuente adjunta: entrevista ADCLEAN 2026-07-29
- [x] Seccion de analisis actualizada: `seccion-g-auditorias-no-conformidades.md`

## Siguiente paso

1. **Resolver las 9 decisiones abiertas** documentadas en proposal.md
2. Aprobar la spec
3. Ejecutar Fase 0: verificar Catalogo Normativo y decidir donde vive la configuracion por tenant
4. Fase 1: modelo compartido en `packages/shared`

## Decisiones pendientes del equipo

- 9 decisiones abiertas en proposal.md (mapeo de severidad, escala del checklist, etc.)
- El Catalogo Normativo necesita entregar articulos para que el checklist funcione (Fase 0)

## Blockers

- La Fase 4 (checklist de auditoria) depende del Catalogo Normativo con articulos desglosados
- Es el cambio mas grande del backlog: 6 entidades, 6 pantallas nuevas, primer uso del worker
