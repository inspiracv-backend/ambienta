# Tasks: La cadena de matrices de ISO 14001

Plan de [`proposal.md`](./proposal.md) / [`design.md`](./design.md).

> Todo lo implementado va detrás de la flag `matricesIso`. Con la flag apagada
> el sistema se comporta exactamente como antes de este cambio.

---

## Fase 1 — Modelo compartido y flag

- [x] `packages/shared/src/feature-flags.ts` con `matricesIso`
- [x] `packages/shared/src/schemas/aspecto-ambiental.ts`
- [x] `packages/shared/src/schemas/riesgo-oportunidad.ts`
- [x] `packages/shared/src/schemas/equipo-regulado.ts`
- [x] `packages/shared/src/schemas/configuracion-matrices.ts` (criterios y umbral por tenant)
- [x] Ampliar `legal-norm.ts` con campos opcionales — sin romper el modelo actual
- [x] Exportar todo desde `packages/shared/src/index.ts`
- [x] Tests de schema, incluidas las reglas cruzadas

## Fase 2 — Datos de ejemplo

- [ ] `mocks/aspectos-ambientales.ts` con las tres condiciones de operación **(medido: hay 3 `normal` y 1 `emergencia`, ninguno `anormal`)**
- [x] `mocks/riesgos-oportunidades.ts` con riesgos y oportunidades reales
- [x] `mocks/equipos-regulados.ts` con caldera y grupo electrógeno
- [ ] Enriquecer `mocks/catalog.ts` con los campos nuevos en al menos una norma **(medido: `mocks/catalog.ts` no tiene vigencia, aplicabilidad ni monitoreo)**
- [ ] Ampliar el catálogo con las normas que pidió la reunión: D.S. 609 (SISS), decretos 40 y 48 de seguridad minera, ley de bases del medio ambiente

## Fase 3 — Cálculo

- [x] Separar cumplimiento de cobertura en `lib/legal-matrix.ts`.
      `computeNormCoverage` deja fuera los `NA` de los dos denominadores, y a
      propósito **no** aplica `incluidoEnCalculo`: excluir algo del cumplimiento
      es una decisión legítima, esconderlo de la cobertura sería tapar que nadie
      lo miró
- [x] Indicador de completitud de la cadena en `lib/completitud-cadena.ts`
      (aspectos sin requisito, requisitos sin aspecto). Es un **tercer**
      indicador: los otros dos pueden verse perfectos sobre una lista de
      requisitos que nadie derivó de sus aspectos, que es justo el hallazgo que
      ISO busca
  - [x] Un aspecto **no significativo** sin tratar no cuenta como hueco:
        decidir que algo no es significativo es la decisión de no tratarlo
  - [x] Sin datos devuelve 1, no 0. Misma convención que la cobertura: la
        ausencia de datos no es un incumplimiento
  - [x] Los enlaces rotos —ids que apuntan a algo que ya no está— se cuentan
        **aparte** de la razón. Son inconsistencia de datos, no tarea
        pendiente, y mezclarlos haría que arreglar un id se leyera como avance
- [x] Tests de ambos indicadores, incluido el caso "100 % de cumplimiento sobre
      un 20 % evaluado" (`legal-matrix-cobertura.test.ts`) y los 10 de la
      completitud. Verificados por mutación: contar los aspectos no
      significativos hace fallar el test que lo prohíbe

## Fase 4 — Pantallas

- [x] Matriz de aspectos e impactos, con filtro por proceso y condición de operación **(21-sep: columna y filtro por proceso, incluido "Sin proceso"; el formulario asigna el proceso y `PATCH` ya lo acepta —antes lo descartaba en silencio, asi que un aspecto quedaba para siempre en el proceso con que nacio)**
- [x] Evaluación de significancia con los criterios del tenant **(con los criterios del sistema; **decidido el 21-sep**: son los de v1.0, y los de cada empresa quedan para despues del piloto — `docs/plan-de-cierre-v1.md` §6)**
- [x] Matriz de riesgos y oportunidades
- [ ] Detalle de norma: vigencia, aplicabilidad y obligación de monitoreo
- [x] Inventario de equipos regulados con alerta de certificación por vencer
- [x] Ítems de navegación condicionados a la flag

## Fase 5 — Configuración por tenant

- [ ] Pantalla de criterios de significancia y umbral **(fuera de v1.0: decision del 21-sep, criterios del sistema para todos)**
- [ ] Método de evaluación de riesgos (matriz probabilidad × consecuencia)
- [x] Default del sistema para tenants nuevos — ver decisión abierta #2 **(hay un default global en `services/iso14001.py`: umbral 25 y legal >= 8)**

## Fase 6 — Consecuencias

- [x] Dashboard: aspectos significativos sin tratar, requisitos por evaluar **(21-sep: la tarjeta de cumplimiento muestra la cobertura y cuantos requisitos faltan; un contador de aspectos sin tratar, de la misma vista que el panel de aspectos. La definicion del cumplimiento es la del tablero —decidido el 21-sep—; el spec de este cambio decia otra cosa que su propio design y se alineo)**
- [ ] Calendario: vencimientos de evaluación periódica y de monitoreo **(parcial, 21-sep: la **evaluación periódica** ya está —`GET /compliance/matrix-norms/revisiones` la deriva de la última evaluación y la frecuencia, y el calendario la muestra junto con el vencimiento de inscripción de los equipos—. Falta el **monitoreo**: `obligacionMonitoreo` del design.md no existe en la base, así que no hay fechas que mostrar)**
- [ ] Registro de mejora: enlazar `riesgo` y `oportunidad` a la matriz en vez de duplicarlos
- [x] Reportes: matriz de aspectos exportable **(21-sep: PDF y CSV desde la pantalla de aspectos, con lo filtrado y el filtro declarado en el documento; lleva los tres puntajes por separado. De paso, "No significativo" dejo de incluir lo sin evaluar)**

---

## Estado de esta entrega

Fases 1 y 2 completas salvo el contenido normativo chileno, que es trabajo de
catálogo y no de código. Las fases 3 a 6 quedan especificadas y sin implementar.

**Por qué se cortó ahí.** El modelo y los datos de ejemplo son lo que permite
evaluar si la cadena es correcta antes de construir cinco pantallas sobre ella.
Si el equipo rechaza la decisión #1 —que la matriz de aspectos entre al MVP—
lo que se descarta son dos archivos de schema, no un módulo entero.

## Cómo revertir

```bash
NEXT_PUBLIC_FF_MATRICES_ISO=false
```

Los campos nuevos de `LegalNorm` son opcionales, así que la matriz legal actual
valida igual con la flag apagada. Para revertir del todo, borrar los cuatro
schemas nuevos y sus mocks: nada del código existente depende de ellos.
