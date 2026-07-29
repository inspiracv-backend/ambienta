# Proposal: Separar Hallazgo de No Conformidad en el módulo de Auditorías

Fuentes: `openspec/analisis/revision-producto-v2.md` §0 y §1 (revisión de producto, 2026-07-29) · `openspec/analisis/seccion-g-auditorias-no-conformidades.md` (análisis original) · `Análisis Funcional v1.7` §3.9 (RF-46 a RF-53) · **ISO 19011:2018** (directrices para auditoría de sistemas de gestión) · **ISO 9001:2015** §9.2 (auditoría interna) y §10.2 (no conformidad y acción correctiva).

## Contexto

El modelo actual de `packages/shared/src/schemas/audit.ts` tiene dos entidades:
`Audit` y `NonConformity`. **No existe una entidad Hallazgo.** Todo lo que un
auditor registra durante una auditoría se guarda como no conformidad.

Esto es un error de modelo, no de interfaz, y contradice la definición
normativa. ISO 19011 define el hallazgo de auditoría como el resultado de
evaluar la evidencia recopilada frente a los criterios de auditoría — y ese
resultado **puede indicar conformidad o no conformidad**. El modelo actual solo
admite la segunda mitad.

### Qué se rompe hoy por esto

1. **No se puede demostrar lo que salió bien.** Ante un certificador, la
   evidencia de que un requisito *se auditó y se cumple* vale tanto como el
   registro de lo que falló. Hoy esa información no tiene dónde guardarse.
2. **Las métricas mienten.** El dashboard cuenta "No Conformidades abiertas"
   sobre un universo que en realidad son *todos* los hallazgos. Una empresa con
   30 hallazgos, 28 de ellos conformes, aparece con 30 no conformidades.
3. **No hay lugar para observaciones ni oportunidades de mejora.** En la
   práctica de certificación son categorías distintas de una no conformidad:
   no disparan acción correctiva obligatoria. Registrarlas como no conformidad
   obliga al cliente a abrir planes de acción que la norma no le exige.
4. **Se pierde contra qué se auditó.** `Audit.normativaIds` existe, pero un
   hallazgo no apunta al requisito concreto que se evaluó, así que no se puede
   reconstruir la cobertura de la auditoría.

> **Nota sobre terminología:** "no conformidad mayor/menor" es la clasificación
> que usan los organismos de certificación (ISO/IEC 17021). "Observación" y
> "oportunidad de mejora" son **práctica habitual del sector**, no términos
> definidos normativamente en ISO 9001. Se incluyen porque el equipo los usa y
> porque su ausencia obliga a distorsionar el dato, pero conviene saber que su
> definición es convencional y debe fijarla la empresa.

## Objetivo

Especificar — sin implementar todavía — el modelo que separa las tres etapas
que ISO 9001 §9.2 y §10.2 tratan como distintas y que hoy están fusionadas:

```
Planificar la auditoría  →  Ejecutarla y registrar hallazgos  →  Tratar las no conformidades
        (§9.2)                        (ISO 19011)                        (§10.2)
```

## Alcance

### Incluye

- Entidad **`Hallazgo`** con tipo (`conformidad` / `no_conformidad` /
  `observacion` / `oportunidad_mejora`) y, cuando corresponde, severidad
  (`mayor` / `menor`).
- Vínculo del hallazgo con el **requisito auditado** (artículo de norma), para
  poder medir cobertura.
- **`NoConformidad`** deja de ser la entidad raíz y pasa a ser el tratamiento
  que se abre a partir de un hallazgo de ese tipo, con su ciclo de §10.2:
  corrección inmediata → análisis de causa → acción correctiva → verificación
  de eficacia → cierre.
- **Programa de auditoría** (`Audit`) con rango de fechas en vez de una sola
  fecha, y despliegue de los requisitos a auditar según las normas elegidas.
- Migración del dato existente y del audit log (`entidadTipo: 'no_conformidad'`
  necesita convivir con `'hallazgo'`).
- Recálculo de las métricas del dashboard y de los reportes afectados.

### NO incluye

- **Código de implementación.** Esta propuesta es spec-only, igual que
  `sistema-actores-roles-rbac`. La implementación requiere aprobación previa
  (CLAUDE.md §1).
- **El resto de los puntos de la revisión de producto** (crear tenant, logo,
  mapa de procesos, unificar Catálogo con Matriz Legal, etc.) — van en
  propuestas separadas o son trabajo directo sobre el modelo actual.
- **Auditoría de proveedores / auditorías externas de segunda parte** — el
  funcional solo distingue interna/externa, sin desarrollar el caso de auditar
  a un tercero.
- **Revisión por la dirección** (ISO 9001 §9.3) — es una ausencia detectada en
  la revisión de producto, pero es un módulo aparte que consume a este.

## Impacto en cascada

Este cambio no es aislado. Al aprobarse afecta:

| Área | Impacto |
|---|---|
| `packages/shared` | Nueva entidad `Hallazgo`; `NonConformity` cambia de forma y de nombre |
| Dashboard (S-06/S-07) | El contador de "NC abiertas" cambia de denominador |
| Reportes (S-39/S-40) | El reporte de no conformidades pasa a poder filtrar por tipo de hallazgo |
| Audit log | Nuevo `entidadTipo: 'hallazgo'`; los eventos existentes de `no_conformidad` deben seguir siendo legibles |
| Planes de acción | Cuelgan de la no conformidad, no del hallazgo genérico |
| Carpeta de auditoría | Debe incluir los hallazgos conformes, hoy inexistentes |

## Decisiones que requiere el equipo

Estas **no** las resuelve esta propuesta por su cuenta:

1. **¿Una observación puede escalar a no conformidad?** En la práctica sí
   (una observación reiterada suele convertirse en NC en la siguiente
   auditoría). Si se permite, hay que decidir si se transforma el hallazgo o
   se crea uno nuevo enlazado — afecta la trazabilidad.
2. **¿Quién define mayor vs. menor?** Puede ser criterio del auditor o
   derivarse de reglas de la empresa. Afecta si el campo es libre o calculado.
3. **¿Toda no conformidad exige plan de acción?** §10.2 exige *evaluar* la
   necesidad de acción, no necesariamente ejecutarla. Si el sistema lo fuerza,
   contradice la norma; si no lo fuerza, hay que registrar la justificación de
   no actuar.
4. **¿Se pueden registrar hallazgos fuera de una auditoría?** Hoy
   `NonConformity.auditId` es opcional, así que el sistema ya lo permite de
   hecho. Hay que decidir si eso sigue siendo válido y cómo se llama entonces.

## Alternativa considerada y descartada

**Agregar un campo `tipo` a `NonConformity` sin renombrar la entidad.** Es
menos trabajo y no rompe imports. Se descarta porque deja el modelo mintiendo
sobre sí mismo: una entidad llamada "no conformidad" con `tipo: 'conformidad'`
es una contradicción que se arrastraría a la base de datos, la API y el
lenguaje del equipo. El costo de renombrar ahora, con el sistema aún en mock y
sin datos reales, es mucho menor que el de convivir con ese nombre para
siempre.
