# Cambios — Alineación normativa ISO y mejoras de matriz legal

**Fecha:** 2026-08-01
**Origen:** entrevista de módulo auditoría con ADCLEAN (29-jul) · reunión con especialista ambiental (`REUNION.txt`, 30-jul) · NCh-ISO 14001:2026 · ISO 19011:2026 · Kawak · Ventanilla Única del RETC · modelo de datos preliminar del equipo de backend.

Este documento registra qué cambió, por qué, dónde se ve y cómo revertirlo.

---

## 1. Resumen

| Bloque | Estado | Detrás de flag |
|---|---|---|
| Registro de Mejora con sus 5 tipos | Implementado | `registroMejora` |
| Etapas del tratamiento (4) | Implementado, sin persistencia | `registroMejora` |
| Cadena de matrices ISO 14001 | Modelo y datos, sin pantallas | `matricesIso` |
| Identificador RETC y CIIU | Implementado | No |
| Cobertura de evaluación legal | Implementado | No |
| Corrección de citas normativas | Aplicado | No |

Verificación al cierre: typecheck limpio, lint sin warnings, build de producción correcto, **183 tests** (eran 153 al comenzar).

---

## 2. Lo que va detrás de flag

Dos flags nuevas en `packages/shared/src/feature-flags.ts`, ambas **encendidas por defecto**:

```bash
NEXT_PUBLIC_FF_REGISTRO_MEJORA=false   # vuelve al formulario de hallazgo simple
NEXT_PUBLIC_FF_MATRICES_ISO=false      # desactiva la cadena de matrices
```

Se leen en tiempo de build: cambiarlas exige reconstruir, no solo reiniciar.

### 2.1 Registro de Mejora

`packages/shared/src/schemas/registro-mejora.ts`.

El formulario asumía que todo lo registrado es una no conformidad. Ahora el **tipo es la primera decisión** y define qué campos aparecen. Son cinco cláusulas distintas, no cinco sabores de lo mismo:

| Tipo | Cláusula |
|---|---|
| Salida No Conforme | ISO 9001 §8.7 |
| No Conformidad | ISO 9001 §10.2 |
| Riesgo | ISO 14001 §6.1.4 |
| Oportunidad | ISO 14001 §6.1.4 |
| Reclamo | ISO 9001 §9.1.2 |

Más `origenDeteccion` con cinco valores: interna, externa, análisis FODA, auditoría interna, auditoría externa. **La auditoría es una fuente de detección, no el contenedor** — en el sistema del cliente la mayoría de los registros no nace de una auditoría.

Reglas que el schema hace cumplir: salida no conforme exige producto (SKU, lote, nombre, cantidad); reclamo exige cliente y canal; origen de auditoría exige apuntar a un hallazgo.

### 2.2 Etapas del tratamiento

`apps/web/components/organisms/EtapasMejoraPanel/`.

Cuatro etapas con responsable propio cada una. El cliente asigna cuatro responsables distintos desde el alta, y además registra quién ejecutó efectivamente cada etapa — cuando no coinciden, eso mismo es información.

- **Corrección** (§10.2.1 a): corrección inmediata, fecha de ejecución, evidencia.
- **Análisis de Causa** (§10.2.1 b): selector de metodología con `5 Por Qué` y `Diagrama de Pescado`. Con la primera se despliegan cinco campos de texto; con la segunda, cajas de causa ampliables. Más causa raíz.
- **Acción Correctiva** (§10.2.1 c): severidad, tipo de acción, descripción, evidencia, fechas.
- **Seguimiento** (§10.2.1 d, e y f): eficacia y cuatro preguntas de verificación.

**Los cinco campos de seguimiento son tri-estado**, no booleanos. En la aplicación del cliente son desplegables `Seleccione… / SI / NO`. Modelarlos como booleano convierte "todavía no lo verifiqué" en "No", que en tres de las cuatro preguntas es la respuesta favorable: el default silencioso cerraría la verificación a favor.

#### Un solo punto de cierre

El primer intento montó el panel de etapas junto al detalle existente y dejó
**dos defectos**:

1. Los 5 Por Qué aparecían dos veces — el bloque viejo del detalle y la Etapa
   de Análisis de Causa.
2. Más grave: el bloque viejo de Cierre tenía su propio botón que **no exigía
   verificar eficacia**. La compuerta de §10.2.1 d quedaba decorativa, porque
   la puerta de al lado estaba abierta.

La corrección:

- El bloque viejo de análisis de causa **se oculta** con la flag encendida.
- El cierre **no se oculta, se endurece**: ocultarlo dejaría la pantalla sin
  forma de cerrar. La eficacia sube del panel a la página vía
  `onEficaciaChange` y baja al bloque de cierre, que la incluye en su condición
  de habilitación. La comparación es `=== true` estricta: sin responder (`null`)
  no habilita, igual que un NO explícito.
- El panel **perdió su botón "Terminar"**. El cierre con firma es uno solo,
  porque es el que registra en el audit log.

#### Orden de lectura

El cierre se extrajo a `CierreNoConformidadPanel` y se renderiza **después** de
las etapas. Cuando estaba embebido en el detalle, la pantalla pedía firmar el
cierre antes de mostrar el trabajo que se estaba cerrando. El orden ahora es:
cabecera → plan de acción → etapas → cierre → historial.

> **Limitación conocida:** el estado de las etapas es local al componente. Se ve y se edita, pero no persiste al navegar fuera. Falta conectarlo al store.

### 2.3 Cadena de matrices ISO 14001

Propuesta en `openspec/changes/matrices-ambientales-iso-14001/`. Cuatro schemas nuevos, sus mocks y tests; **sin pantallas**.

- `AspectoAmbiental` (§6.1.2) — con las tres condiciones de operación y las siete etapas del ciclo de vida.
- `RiesgoOportunidad` (§6.1.4) — entidad propia, no un valor de desplegable.
- `EquipoRegulado` — calderas y generadores con operadores certificados y su vigencia.
- `ConfiguracionMatrices` — criterios de significancia y umbral por empresa.

Más la ampliación de `LegalNorm` con campos **todos opcionales**: categoría de requisito, subtipo, organismo fiscalizador, vigencia, aplicabilidad por CIIU y evaluación periódica. A nivel de artículo: obligación de monitoreo con parámetros y límites, evidencia física y anclaje a equipos.

---

## 3. Lo que NO va detrás de flag

Son correcciones y campos que pertenecen al producto tal como está definido en el funcional v1.7. No son funcionalidad a evaluar.

### 3.1 Identificador RETC y CIIU

`PlantSchema` en `packages/shared/src/schemas/tenant.ts`.

Dos campos opcionales tomados de la Ventanilla Única del RETC (`vu.mma.gob.cl`): el **identificador del establecimiento**, que es con el que el Ministerio conoce a la instalación y por lo tanto la llave para cruzar lo que declara la empresa con lo que la autoridad ve; y el **código CIIU**, que habilita la precarga de normativa aplicable por rubro.

**Dónde se ve:** `/perfil-empresa`, sección *Plantas / Instalaciones*. Aparecen como etiquetas bajo el nombre de cada planta. Planta Concepción queda sin ellas a propósito, para representar una instalación aún no registrada.

### 3.2 Cobertura de evaluación legal

`apps/web/lib/legal-matrix.ts` — funciones `computeNormCoverage` y `countArticulosSinEvaluar`.

**El problema.** Una norma con un artículo cumplido y cuatro sin evaluar mostraba **100% de cumplimiento**. No era un error de cálculo: es cierto sobre lo evaluado. Pero se leía como "esta norma está al día".

**La solución.** Dos indicadores que responden preguntas distintas:

```
Cumplimiento = SI / (SI + NO)          ¿cumplimos lo que revisamos?
Cobertura    = evaluados / aplicables  ¿cuánto alcanzamos a revisar?
```

`NA` sale de ambos denominadores: un artículo no aplicable no es un artículo sin revisar. Y `incluidoEnCalculo` afecta **solo** al cumplimiento — excluir algo del cálculo es una decisión legítima de la empresa, esconderlo también de la cobertura sería tapar que nadie lo miró.

Kawak resuelve lo mismo contando lo no calificado como cero. Se prefirió mostrar los dos números porque cada uno sirve para una decisión distinta.

**Dónde se ve:** `/matriz-legal`, columna *Cobertura* entre Cumplimiento y En incumplimiento. Cuando quedan artículos sin evaluar, el porcentaje sale en ámbar con el conteo al lado.

**Tests:** `apps/web/lib/legal-matrix-cobertura.test.ts`, seis casos incluido el que motiva la separación.

### 3.3 Corrección de citas normativas

NCh-ISO 14001:2026 **renumeró el apartado 6.1**. Su §6.1.1 remite ahora a «6.1.2 a 6.1.5»; la edición 2015 llegaba hasta 6.1.4.

| | 2015 | 2026 |
|---|---|---|
| 6.1.3 | Requisitos legales y otros requisitos | **Obligaciones de compliance** |
| 6.1.4 | Planificación de acciones | **Riesgos y oportunidades** |
| 6.1.5 | — | Planificación de acciones |

Y §9.1.2 pasó a llamarse **evaluación de compliance**. Las citas se corrigieron en los dos documentos de la propuesta de matrices y en cuatro schemas.

También se corrigieron las **etapas del ciclo de vida**: la NOTA 1 de §6.1.2 enumera siete (materias primas, diseño, producción, transporte/entrega, uso, tratamiento al finalizar la vida útil, disposición final). El enum tenía cinco y fusionaba las dos últimas.

---

## 4. Sobre el mapa de procesos

**No se agregaron procesos nuevos, y es deliberado.**

El mapa ya existía: `DepartamentoSchema` modela el departamento como proceso de ISO 9001 §4.4, con tipo estratégico/operativo/soporte, dueño, entradas y salidas. Los siete procesos del tenant demo son de orientación ambiental: Dirección y Planificación, Medio Ambiente, Operaciones, Declaraciones y Reportes, Administración y Finanzas, Gestión de Personas y Servicio al Cliente.

El catálogo que aparece en las capturas de ADCLEAN —Producción, Marketing, Gestión de la Calidad, Planificación, Investigación y Desarrollo, Adquisiciones, Logística, Ventas— es el de **una empresa de calidad**, no el de Ambienta. Copiarlo habría metido el mapa de procesos de un cliente concreto como si fuera el del producto.

Lo que sí se agregó es el **enlace**: el formulario de registro de mejora tiene un selector *Proceso involucrado* que se puebla desde el mapa del tenant, y los schemas de la cadena ISO 14001 referencian `Departamento.id` en `procesoId`.

**Dónde se ve:** `/no-conformidades/nueva`, campo *Proceso involucrado*.

---

## 5. Archivos tocados

**Schemas nuevos:** `feature-flags.ts`, `aspecto-ambiental.ts`, `riesgo-oportunidad.ts`, `equipo-regulado.ts`, `configuracion-matrices.ts`, `registro-mejora.ts`.

**Schemas modificados:** `legal-norm.ts` (campos opcionales), `tenant.ts` (RETC y CIIU), `index.ts` (exports).

**Componentes:** `EtapasMejoraPanel` (nuevo), `RegisterFindingForm` (reescrito), `LegalMatrixTable` (columna cobertura), `PerfilEmpresaWizard` (etiquetas RETC).

**Lib y mocks:** `legal-matrix.ts`, `mocks/tenants.ts`, `mocks/aspectos-ambientales.ts`, `mocks/riesgos-oportunidades.ts`.

**Tests:** `matrices-iso.test.ts` (24 casos), `legal-matrix-cobertura.test.ts` (6 casos).

**Documentación:** propuesta `matrices-ambientales-iso-14001/` completa; propuesta `hallazgos-auditoria-no-conformidades/` revisada a v2 con su carpeta `fuentes/`.

---

## 6. Pendientes conocidos

- **Persistencia de las etapas.** Hoy el estado es local al componente.
- **Pantallas de la cadena ISO 14001.** El modelo está, la interfaz no.
- **Contenido normativo chileno.** D.S. 609, decretos 40 y 48, ley de bases. Es trabajo de catálogo, no de código.
- **Mapeo CIIU ↔ normas.** El campo existe; la tabla que lo alimenta no.
- **Mock desactualizado:** el catálogo todavía dice "ISO 14001:2015".
- **Decisión de alcance abierta.** La cadena completa de ISO 14001 excede lo definido en el funcional v1.7, que describe un sistema de cumplimiento de declaraciones, no un sistema de gestión ambiental certificable. Por eso va detrás de flag: apagarla devuelve el producto del v1.7 sin revertir código.
