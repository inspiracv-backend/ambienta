# Proposal: La cadena de matrices de ISO 14001

Fuentes: `REUNION.txt` (reunión con el especialista, 2026-07-30) · **ISO 14001:2026** (publicada, sustituye a 14001:2015 y su enmienda de 2024 sobre cambio climático) · **ISO 19011:2026** (cuarta edición, mayo 2026, sustituye a 19011:2018) · Kawak — módulos de auditoría y matriz legal · `Análisis Funcional v1.7` §3.4 (RF-19 a RF-24).

## Contexto

Ambienta implementa hoy **una** matriz: `LegalNormSchema`, la matriz legal con
evaluación por artículo. ISO 14001 no pide una matriz: pide una **cadena** en la
que cada eslabón justifica al siguiente.

```
Mapa de procesos → Aspectos e impactos → Obligaciones de compliance → Riesgos y oportunidades → Acciones
     §4.4                 §6.1.2                    §6.1.3                      §6.1.4             §6.1.5
```

> **Numeración de la edición 2026.** NCh-ISO 14001:2026 renumeró el apartado 6.1:
> su §6.1.1 remite ahora a «6.1.2 a 6.1.5», donde la edición 2015 llegaba hasta
> 6.1.4. Riesgos y oportunidades pasó a ser subapartado propio (§6.1.4) y
> «requisitos legales y otros requisitos» se renombró **obligaciones de
> compliance** (§6.1.3). La evaluación periódica de §9.1.2 pasó a llamarse
> **evaluación de compliance**.

El especialista lo describió con esas mismas palabras en la reunión: *"es
importante tener un mapa de procesos, para cada actividad empresa y planta, a
partir de ahí se hace el análisis; a partir del mapa de procesos ver lo que pide
la ISO"*.

| Eslabón | Cláusula | Estado hoy |
|---|---|---|
| Mapa de procesos | §4.4 | **Existe** — `DepartamentoSchema` |
| Aspectos e impactos ambientales | §6.1.2 | **No existe** |
| Riesgos y oportunidades | §6.1.4 | **No existe** como matriz |
| Obligaciones de compliance | §6.1.3 | **Parcial** — `LegalNormSchema` |
| Evaluación del cumplimiento | §9.1.2 | **No existe** como ciclo periódico |

### Por qué la cadena importa y no basta la matriz legal sola

Sin aspectos ambientales **no se puede justificar por qué una norma aplica**. El
orden correcto es: identificar la actividad, determinar qué aspecto ambiental
genera (emisión, vertido, residuo, consumo), evaluar su impacto y significancia,
y recién entonces determinar qué requisito legal la alcanza.

Hoy el sistema hace lo contrario: alguien agrega normas a mano a una lista. Eso
funciona como registro pero no es defendible ante un auditor, porque no responde
la pregunta que el auditor hace primero — *"¿cómo determinaron que esto les
aplica, y cómo saben que no falta nada?"*.

Cuando la reunión dice que *"hay que ampliar el inventario de aspectos legales,
se encuentra parcial"*, está señalando exactamente ese eslabón.

## Objetivo

Especificar e implementar la cadena completa, detrás de una **feature flag**
que permita apagarla sin revertir código.

## Alcance

### Incluye

- **`AspectoAmbiental`** (§6.1.2): actividad, aspecto, impacto, condición de
  operación, perspectiva de ciclo de vida y evaluación de significancia con
  criterios configurables por empresa.
- **`RiesgoOportunidad`** (§6.1.4): entidad propia, con origen trazable,
  evaluación de nivel, tratamiento y revisión periódica.
- **Ampliación de `LegalNorm`**: categoría de requisito, vigencia,
  aplicabilidad por actividad económica, organismo fiscalizador, periodicidad
  de evaluación y obligaciones de monitoreo.
- **`EquipoRegulado`**: calderas, generadores y grupos electrógenos, con su
  inscripción y la competencia habilitante de quien los opera.
- **Feature flag** `matricesIso` que gobierna todo lo anterior.

### NO incluye

- **Pantallas.** Esta entrega es modelo de datos, mocks y flag. La interfaz va
  en una entrega siguiente, sobre el modelo ya estabilizado.
- **Precarga automática por actividad económica.** Se modela el campo de
  aplicabilidad; poblar catálogos por CIIU es trabajo de contenido, no de código.
- **Integración con laboratorios.** Se modela la obligación de monitoreo; la
  carga de resultados de laboratorio es otra propuesta.
- **SEA y APL como flujos.** Se admiten como tipos de requisito; sus flujos
  propios quedan fuera.

## Decisiones tomadas

**1. Riesgos y oportunidades deja de ser un tipo de registro de mejora.** Hoy
`riesgo` y `oportunidad` son dos valores de un desplegable en el registro de
mejoras. Eso trata un requisito de planificación como si fuera un incidente.
§6.1.4 pide determinarlos al planificar, no cuando alguien los reporta. Pasan a
entidad propia; el registro de mejora puede seguir originando uno.

**2. La significancia es configurable, no cableada.** Los criterios de
evaluación de aspectos (severidad, frecuencia, alcance, existencia de requisito
legal) y el umbral de significancia varían por empresa y por sector. Se modelan
como catálogo del tenant, igual que se hizo con la escala de severidad de
mejoras.

**3. Se separan dos indicadores que hoy están fusionados.** Kawak cuenta lo no
calificado como cero; nuestro modelo lo excluye del cálculo con
`incluidoEnCalculo`. Ambos son correctos para cosas distintas:

| Indicador | Qué mide | Qué hace con lo no evaluado |
|---|---|---|
| Cumplimiento legal | Si la empresa puede afirmar que cumple | Lo cuenta como **no cumplido** |
| Cobertura de evaluación | Cuánto del universo se alcanzó a revisar | Lo cuenta como **no cubierto** |

Un 100% de cumplimiento sobre el 30% evaluado no es cumplimiento: es una
muestra. Mostrar los dos juntos evita esa lectura.

**4. La evidencia admite papel.** La reunión fue explícita: las empresas no
digitalizan y *"igual debe existir papel a resguardo o administrado según
empresa"*. La evidencia deja de asumir una URL.

## Lo que cambia por ISO 14001:2026

La edición 2026 refuerza tres cosas que tocan directo a este modelo:

- **§4 contexto** se amplía a cambio climático, biodiversidad y recursos
  naturales. Se agregan como tipos de aspecto y como origen de riesgo.
- **§6 planificación** incorpora riesgos derivados del cambio climático y exige
  datos verificables.
- **§7.5** pasa a exigir trazabilidad digital, control de versiones electrónicas
  y seguridad de los datos ambientales. Eso convierte la matriz documental —hoy
  propuesta en el borrador v1.8 del funcional— en requisito, no en mejora.

## Riesgo de esta propuesta

Es el cambio de modelo más grande hasta ahora y toca el módulo corazón. Por eso
va detrás de flag: con `matricesIso` apagada, el sistema se comporta
exactamente como hoy y los tipos nuevos quedan sin uso, sin romper nada.

## Decisiones que requiere el equipo

1. **¿La matriz de aspectos entra al MVP o queda identificada?** Arrastra el
   mapa de procesos como prerequisito duro.
2. **¿Los criterios de significancia se definen por empresa o hay un default
   del sistema?** Sin default, cada tenant nuevo arranca con una matriz que no
   puede evaluar.
3. **¿Riles se adelanta desde post-MVP?** El funcional v1.7 lo pone en RF-71 a
   RF-74 como posterior, y la reunión lo trata como necesidad presente con el
   decreto 609 encima.
4. **¿Quién mantiene el catálogo de aplicabilidad por actividad económica?**
   Es trabajo de contenido permanente, no de desarrollo.
