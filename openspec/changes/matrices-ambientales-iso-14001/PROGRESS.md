# Progreso: La cadena de matrices de ISO 14001

**Ultima actualizacion:** 2026-08-04

## Estado actual

**Fase actual:** Fases 1 y 2 parcialmente implementadas (schemas + mocks). Fases 3-6 pendientes.
**Spec no aprobada formalmente** — se implementaron las fases 1-2 antes de formalizar el flujo SDD.

## Completado

- [x] Spec: proposal.md + design.md + tasks.md
- [x] Fase 1 — Modelo compartido (commit ec8ed2e):
  - [x] Feature flag `matricesIso`
  - [x] Schemas: aspecto-ambiental, riesgo-oportunidad, equipo-regulado, configuracion-matrices
  - [x] Campos opcionales en legal-norm.ts
  - [x] Tests de schema
- [x] Fase 2 — Datos de ejemplo (parcial):
  - [x] Mocks de aspectos ambientales, riesgos, equipos regulados
  - [ ] **Pendiente:** contenido normativo chileno (D.S. 609, decretos 40/48, ley de bases)

## Siguiente paso

1. **Formalizar la aprobacion de la spec** — las fases 1-2 ya se implementaron sin aprobacion formal
2. Completar el contenido normativo chileno (Fase 2, tarea pendiente)
3. Fase 3: separar cumplimiento de cobertura + indicador de completitud de la cadena

## Decisiones pendientes del equipo

- Decision abierta #1 de proposal.md: ¿la matriz de aspectos entra al MVP?
- Decision abierta #2: default de configuracion para tenants nuevos

## Blockers

- Si el equipo rechaza la decision #1 (matriz fuera del MVP), las fases 3-6 no se implementan
- El contenido normativo chileno es trabajo de catalogo, no de codigo
