# Proposal: Auditorías, Hallazgos y Registros de Mejora

Fuentes: [`fuentes/entrevista-adclean-2026-07-29.md`](./fuentes/entrevista-adclean-2026-07-29.md) (entrevista de módulo auditoría con el cliente) · `openspec/analisis/revision-producto-v2.md` §0 y §1 · `openspec/analisis/seccion-g-auditorias-no-conformidades.md` · `Análisis Funcional v1.7` §3.9 (RF-46 a RF-53) · **ISO 19011:2018** (directrices para auditoría de sistemas de gestión) · **ISO 9001:2015** §8.7, §9.2, §10.2.

> **Revisión 2 (2026-07-30).** La versión anterior de esta propuesta se escribió
> la mañana del 29-jul, nueve horas antes de la entrevista con ADCLEAN. Esta
> revisión incorpora esa entrevista y **cambia la entidad raíz del módulo**. Los
> supuestos que la entrevista derribó están marcados en `tasks.md`.

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
   sobre un universo que en realidad son *todos* los hallazgos.
3. **No hay lugar para observaciones ni oportunidades de mejora.** Registrarlas
   como no conformidad obliga al cliente a abrir planes de acción que la norma
   no le exige.
4. **Se pierde contra qué se auditó.** `Audit.normativaIds` existe, pero un
   hallazgo no apunta al requisito concreto que se evaluó.

### Lo que agregó la entrevista con el cliente

La entrevista mostró el sistema que ADCLEAN usa hoy —una app Power Apps
llamada "Gestión de Mejoras" más un conjunto de documentos en SharePoint— y
obligó a corregir el encuadre de la propuesta original:

5. **La auditoría no es el contenedor de los hallazgos, es una fuente de
   detección.** El campo `Tipo de Detección` del cliente ofrece cinco valores,
   de los cuales solo dos son auditorías. La mayoría de los registros de mejora
   **no nacen de una auditoría**.
6. **El ciclo de tratamiento tiene cinco etapas con responsable propio cada
   una**, asignados desde el momento del registro. La propuesta original tenía
   una máquina de estados con un solo `responsableId`.
7. **El análisis de causa admite más de una metodología.** RF-47 del funcional
   solo menciona los 5 Por Qué; el cliente usa también Diagrama de Pescado y lo
   elige por registro.
8. **Faltan los instrumentos de la auditoría.** El plan con agenda por sesión,
   el checklist por cláusula con escala de cumplimiento y el informe con
   resumen ejecutivo son documentos de Office hoy — y son la mitad del trabajo
   real de auditar.

## Objetivo

Especificar — sin implementar todavía — un modelo que separe cuatro cosas que
hoy están fusionadas o directamente ausentes:

```
Planificar la auditoría → Ejecutarla contra un checklist → Registrar hallazgos → Tratar la mejora
        (§9.2)                    (ISO 19011)                  (ISO 19011)         (§8.7 / §10.2 / §6.1)
```

## Decisión estructural: el Registro de Mejora es la entidad raíz

Es el cambio de fondo respecto de la revisión 1.

**Antes:** `Auditoria` → `Hallazgo` → `NoConformidad`. El hallazgo era la raíz y
colgaba siempre de una auditoría.

**Ahora:** `RegistroMejora` es la raíz. Nace de una fuente de detección, que
puede ser un hallazgo de auditoría o cualquier otra cosa, y recorre las cinco
etapas de tratamiento.

```
Auditoria ──► Hallazgo ──┐
                         ├──► RegistroMejora ──► [5 etapas de tratamiento]
Detección directa ───────┘
(interna, externa, FODA, reclamo de cliente)
```

**Por qué.** Modelar la auditoría como contenedor obliga a inventar auditorías
falsas para todo lo que se detecta fuera de una — que en el sistema del cliente
es la mayoría. Invertir la relación cuesta lo mismo y refleja lo que pasa: la
auditoría es *una* de las maneras de encontrar algo que hay que mejorar.

Esto **no elimina** la entidad `Hallazgo`. Un hallazgo de auditoría sigue
existiendo con su clasificación ISO 19011, porque el informe de auditoría
necesita contar también los conformes, que nunca generan un registro de mejora.

### Las dos taxonomías no se fusionan

La entrevista dejó a la vista dos clasificaciones que no son el mismo eje:

| Eje | Valores | De dónde sale | Dónde vive |
|---|---|---|---|
| Clasificación del hallazgo | conformidad · no conformidad · observación · oportunidad de mejora | ISO 19011 / práctica de certificación | `Hallazgo.clasificacion` |
| Tipo de registro | salida no conforme · no conformidad · riesgo · oportunidad · reclamo | Cláusulas §8.7, §10.2, §6.1, §9.1.2 | `RegistroMejora.tipo` |

Fusionarlas en un solo campo produce valores sin sentido. Un hallazgo conforme
no tiene tipo de registro porque no abre ninguno; un reclamo de cliente no
tiene clasificación de auditoría porque no vino de una auditoría.

> **Nota sobre terminología:** "no conformidad mayor/menor" es la clasificación
> de los organismos de certificación (ISO/IEC 17021). "Observación" y
> "oportunidad de mejora" son **práctica habitual del sector**, no términos
> definidos en ISO 9001. "CAPA" y "acción preventiva" vienen del mundo farma y
> de dispositivos médicos: ISO 9001:2015 dice "acción correctiva" y eliminó
> "acción preventiva" respecto de la versión 2008, reemplazándola por el
> pensamiento basado en riesgos de §6.1. Se documentan porque el cliente los
> usa, no porque la norma los exija.

## Alcance

### Incluye

- Entidad **`RegistroMejora`** como raíz, con `tipo` (5 valores) y
  `origenDeteccion` (5 valores), campos condicionales según el tipo, y las
  cinco etapas de tratamiento con responsable por etapa.
- Entidad **`Hallazgo`** con clasificación ISO 19011 y vínculo al requisito
  auditado, para poder medir cobertura y contar conformes.
- **`Auditoria`** con rango de fechas, objetivos, sitios, equipo auditor con
  procesos asignados, estados y **agenda por sesión** (proceso, horario,
  entrevistado, auditor, método).
- **`NotaAuditoria`**: el registro de campo por proceso auditado (formato
  PE2-R08 del cliente), con la muestra revisada y su objetivo.
- **`ItemChecklist`**: ítems por cláusula **y por proceso**, con requisito
  textual, pregunta, evidencia y escala de cumplimiento.
- **`InformeAuditoria`**: resumen ejecutivo con conteos derivados, matriz de
  resultados por proceso y fichas de hallazgo.
- **Análisis de causa con metodología seleccionable** (5 Por Qué y Diagrama de
  Pescado como mínimo), extensible por tenant.
- **Verificación de eficacia** con las tres preguntas de §10.2.1 d), e) y f)
  más la de recurrencia.
- Catálogos **configurables por tenant**: escala de severidad, metodologías de
  análisis de causa, formato de codificación de hallazgos, plazos por defecto y
  orden de las etapas.
- Notificación por correo al responsable de cada etapa con fecha límite.
- Migración del dato existente y del audit log.
- Recálculo de las métricas del dashboard y de los reportes afectados.

### NO incluye

- **Código de implementación.** Esta propuesta es spec-only (CLAUDE.md §1).
- **El resto de los puntos de la revisión de producto** — van en propuestas
  separadas.
- **Auditoría de proveedores / de segunda parte.**
- **Revisión por la dirección** (§9.3) — módulo aparte que consume a este.
- **Firma electrónica con validez legal.** El cierre registra un acto, no una
  firma criptográfica.

## Lo que esto exige del resto del sistema

| Área | Impacto |
|---|---|
| `packages/shared` | Tres entidades nuevas; `NonConformity` desaparece como raíz |
| Perfil Empresa | El mapa de procesos pasa a ser prerequisito duro: sin procesos no hay `Proceso Involucrado` ni alcance de auditoría |
| Catálogo Normativo | El checklist se despliega desde los artículos de la norma; hoy el catálogo no los expone así |
| Dashboard (S-06/S-07) | El contador cambia de denominador; se agregan los pendientes por etapa |
| Reportes (S-39/S-40) | Informe de auditoría como reporte de primera clase |
| Audit log | Nuevos `entidadTipo`; los eventos de `no_conformidad` deben seguir siendo legibles |
| Planes de acción | Cuelgan de la etapa de acción correctiva, no del registro |
| Notificaciones / worker | Primer caso de uso real de correo con fecha límite (RF-41 a RF-45, Resend) |
| Configuración de tenant | Aparece la necesidad de catálogos por empresa; hoy no existe ese lugar |

## Decisiones que requiere el equipo

Estas **no** las resuelve esta propuesta por su cuenta:

1. **¿En qué orden van Corrección y Análisis de Causa?** ISO 9001 §10.2.1 pone
   primero reaccionar y corregir; la app del cliente pone primero el análisis.
   La propuesta lo resuelve haciendo el orden configurable con el de la norma
   por defecto, pero conviene confirmarlo con el cliente porque cambia su hábito.
2. **¿Qué escala de severidad manda?** El cliente usa `Alta` en su app y `Mayor`
   en SharePoint. Hay que fijar la escala del sistema y el mapeo.
3. **¿Una observación puede escalar a no conformidad?** Si se permite, hay que
   decidir si se transforma el hallazgo o se crea uno nuevo enlazado.
4. **¿Toda no conformidad exige acción correctiva?** §10.2 exige *evaluar* la
   necesidad de acción, no necesariamente ejecutarla. Si el sistema la fuerza,
   contradice la norma; si no la fuerza, hay que registrar la justificación.
5. **¿El checklist es obligatorio para ejecutar una auditoría?** El cliente hoy
   lo usa como documento aparte y no siempre. Si se hace obligatorio, la
   cobertura se mide sola; si es opcional, hay auditorías sin cobertura medible.
6. **¿Se muestra "CAPA" en la interfaz?** Es el término del cliente pero no es
   vocabulario ISO 9001. Afecta a las etiquetas, no al modelo.
7. **¿El Diagrama de Pescado se organiza por categorías?** En las capturas las
   cajas de causa se ven sueltas, sin rótulo de categoría. Un Ishikawa canónico
   agrupa por 6M. Hay que confirmar con el cliente si su diagrama tiene
   categorías que no se alcanzan a ver o si efectivamente son causas planas:
   cambia si el editor obliga a clasificar o no.
8. **¿"Fortaleza" y "conformidad" son dos clasificaciones o una?** El resumen
   ejecutivo cuenta fortalezas y no cuenta conformidades. El diseño mantiene
   ambas por razones que se explican en `design.md` §2.5, pero es una decisión
   que el equipo puede revertir.

## Alternativas consideradas y descartadas

**Mantener `Hallazgo` como raíz bajo `Auditoria` (revisión 1 de esta
propuesta).** Se descarta porque obliga a que todo lo detectado fuera de una
auditoría cuelgue de un `auditoriaId` opcional, y eso deja el modelo diciendo
que un reclamo de cliente es un hallazgo de auditoría sin auditoría.

**Un solo campo `tipo` que mezcle ambas taxonomías.** Se descarta por los
valores sin sentido que produce, descritos arriba.

**Agregar un campo `tipo` a `NonConformity` sin renombrar la entidad.** Es
menos trabajo y no rompe imports. Se descarta porque deja el modelo mintiendo
sobre sí mismo: una entidad llamada "no conformidad" con `tipo: 'conformidad'`
es una contradicción que se arrastraría a la base de datos, la API y el
lenguaje del equipo. El costo de renombrar ahora, con el sistema aún en mock y
sin datos reales, es mucho menor que el de convivir con ese nombre para
siempre.

**Copiar el modelo del cliente tal cual.** Se descarta porque Ambienta es
multi-tenant: cablear la escala de severidad, las metodologías y el orden de
etapas de ADCLEAN deja al segundo cliente fuera. Lo que es trazable a una
cláusula va fijo; lo que es convención de empresa va configurable.
