# Fuente: entrevista módulo auditoría — ADCLEAN / Adquim SpA

**Fecha:** 29 de julio de 2026, 19:24 a 19:53 (Google Meet)
**Participantes:** Kareli Colmenares (ADCLEAN, presentando) · Gabriel Tovar · Fabrizzio Gomez
**Evidencia:** 47 capturas de pantalla, entregadas embebidas en
`Documento importante para el sistema.rtf`. El orden del documento coincide con
el cronológico. Las capturas 1 a 19 (19:24–19:34) son de la aplicación Power
Apps; el resto son documentos de Office y SharePoint.

> Este documento transcribe **lo que se observó**, sin interpretarlo. Las
> decisiones que se toman a partir de esto van en `proposal.md` y `design.md`.

---

## 1. Aplicación "Gestión de Mejoras" (Power Apps)

Sistema actual de ADCLEAN para el ciclo de mejora. Es la referencia funcional
directa del módulo.

**Menú lateral:** Inicio · Registro · Análisis de Causa · Corrección ·
Acciones Correctivas · Seguimiento · Buscador

### 1.1 Pantalla Inicio (dashboard)

Contadores en tira: Registros Pendientes · En Análisis Pendientes · En Acciones
Correctivas Pendientes · En Seguimiento Pendientes · Resolución de mejoras (%
de avance).

Listados: Mejoras En Registro · Mejoras en Progreso · Mejoras en Análisis de
Causa y Corrección · Mejoras en Acciones Correctivas.

**Observación clave sobre los identificadores.** El dashboard marca "En
Acciones Correctivas: 2 pendientes" (Ids 88 y 89) y "En Seguimiento: 4
pendientes" (Ids 84, 85, 86, 87). Son seis registros, cada uno en exactamente
una etapa, con Ids correlativos en un mismo espacio de numeración. Lo que
cambia entre pantallas es el **título** (`Seguimiento 84`, `Acción
Correctiva/Preventiva 88`), no el registro. Es decir: **un registro único que
avanza por etapas**, no un registro por etapa.

### 1.2 Formulario "Registrar Mejora" — Etapa de Registro

| Campo | Tipo | Valores observados |
|---|---|---|
| Tipo Registro | Select | Salida No Conforme · No Conformidad · Riesgo · Oportunidad · Reclamo |
| Fecha | Fecha | — |
| Reportado por | Texto | — |
| Descripción (Hallazgo) | Texto largo | — |
| Tipo de Detección | Select | Interna · Externa · Análisis FODA · Auditoría Interna · Auditoría Externa |
| Proceso Involucrado 1 | Select | Ver catálogo abajo |
| Proceso Involucrado 2 | Select | idem |
| Subir Archivos | Adjuntos | — |
| Corrección | Select | — |
| Responsable Análisis Causa y Corrección | Select persona | — |
| Responsable Acciones Correctivas | Select persona | — |
| Responsable Seguimiento | Select persona | — |

**Campos adicionales cuando `Tipo Registro = Salida No Conforme`** (vistos en la
vista de solo lectura de un registro ya creado): SKU · Lote · Nombre Producto ·
Cantidad + Unidad.

**Inconsistencia observada:** el mismo responsable aparece como `Responsable
Acciones Correctivas` en el formulario de alta y como `Responsable CAPA` en la
vista de solo lectura.

**Catálogo de `Proceso Involucrado`** (desplegable abierto, con scroll — pueden
faltar valores al final): Producción · Marketing · Gestión de la Calidad ·
Planificación · Investigación y Desarrollo · Adquisiciones · Logística · Ventas.

El informe de auditoría lista 13 procesos en el alcance, así que este catálogo
y el del informe deberían ser el mismo: Gestión Gerencial · Gestión de Calidad ·
Investigación y Desarrollo · Ventas · Producción · Control de Calidad ·
Logística y Despacho · Recursos Humanos · Marketing · Mantenimiento ·
Adquisiciones · SSOMA · Tecnología de la Información.

**Fecha nula:** el valor `31/12/2001` aparece en campos de fecha vacíos
(`Fecha` en el alta, `Fecha Finalización` en un registro a medio completar).
Es el placeholder de "sin fecha" de su aplicación, no un dato.

### 1.3 Etapa de Análisis de Causa

- `Metodología de Análisis de Causa` — select con **exactamente dos opciones**,
  con estos rótulos literales: `5 Por Qué` y `Diagrama de Pescado`.
  El catálogo completo lo confirmó Fabrizzio, que estuvo en la reunión; las
  capturas muestran cada valor usado en un registro distinto.
- Con 5 Por Qué: cinco campos de texto libre, `Por Qué 1` a `Por Qué 5`,
  dispuestos 1-2-3 en la columna izquierda y 4-5 en la derecha.
  En el caso real observado el contenido mezcla niveles: los dos primeros
  campos traen la *pregunta* ("¿Por qué el tamaño de la etiqueta no se ajusta
  al envase?") y los tres siguientes la *respuesta* ("Porque no se incluyó la
  verificación de dimensiones del…"). No hay campos separados de pregunta y
  respuesta por nivel; es un solo texto por escalón.
- Con Diagrama de Pescado: lienzo con la espina y cajas de texto alrededor.
  Las cajas se ven **sueltas, sin rótulo de categoría** — una está vacía con el
  texto placeholder `Causa`. No se observa la clasificación por 6M (método,
  máquina, material, mano de obra, medio, medición) que trae un Ishikawa
  canónico. Puede que las categorías existan y no se vean en la captura;
  queda como incertidumbre a confirmar.
- Causas observadas en un caso real: "Equipos de envasado sin control de
  hermeticidad" · "No existe protocolo para validar estabilidad del HOCl en
  almacenamiento" · "Contacto con aire (oxígeno) que favorece la descomposición
  del…" · "Producto granel de Ácido Hipocloroso 3000 ppm (diluido desde…)".
- `Responsable Etapa` (persona que efectivamente ejecutó la etapa).

### 1.4 Etapa de Corrección

Corrección Inmediata · Fecha de Ejecución de Corrección · Evidencia · Subir
Archivo.

### 1.5 Etapa de Capa

Escrito así en la aplicación, no "CAPA".

Tipo de Severidad (valor observado: `Alta`) · Tipo Acción (valor observado:
`Correctiva`) · Acción Correctiva · Evidencia de la Acción · Causa Raíz ·
Fecha Inicial · Fecha Finalización · Responsable Etapa · Subir Evidencia.

### 1.6 Etapa de Seguimiento

Campo `Eficacia` y cuatro preguntas de verificación. **Todos son desplegables
de tres estados**: `Seleccione…` / `SI` / `NO`. No son casillas booleanas — sin
responder es un estado distinto de "No".

1. ¿La causa se ha vuelto a repetir durante el periodo de seguimiento?
2. ¿La acción correctiva cumplió su propósito?
3. ¿Se requiere actualizar los riesgos y oportunidades?
4. ¿Se requiere hacer cambios al sistema de gestión de calidad?

Más `Fecha Seguimiento`, `Responsable Etapa` y `Evidencia Seguimiento`.

Las preguntas 2, 3 y 4 son las sub-cláusulas d), e) y f) de ISO 9001 §10.2.1
convertidas en preguntas.

### 1.7 Orden de las etapas dentro del registro

Deducido de adyacencias visibles **dentro de una misma captura**, no del orden
de las capturas:

- `Etapa de Registro` está al tope del formulario.
- `Etapa de Corrección` y `Etapa de Capa` aparecen juntas en una captura.
- `Etapa de Capa` y `Etapa de Seguimiento` aparecen juntas en otra.
- Por eliminación, `Etapa de Análisis de Causa` queda entre Registro y
  Corrección.

Confirmado de forma independiente por el orden del menú lateral y por los
nombres compuestos `Responsable Análisis Causa y Corrección` y la lista
`Análisis de Causa y Corrección Pendientes`.

**Orden resultante:** Registro → Análisis de Causa → Corrección → Capa →
Seguimiento.

Nota: ISO 9001 §10.2.1 plantea el orden inverso entre las dos del medio —
primero reaccionar y corregir, después evaluar la causa.

### 1.8 Acciones por pantalla

Botones `Guardar`, `Cancelar` y `Terminar`. `Terminar` cierra la etapa y
avanza el registro.

---

## 2. Artefactos fuera de la aplicación

Todo lo siguiente vive hoy en Office y SharePoint, desconectado de la app.

### 2.1 `PE2-R02 Plan Auditoría Interna` (Word)

Tabla de agenda con: ítem · proceso · fecha · hora inicio · hora fin ·
entrevistado(s) · auditor · método / foco.

Procesos que aparecen en el plan: Gestión de Calidad, Control de Calidad,
Ventas, Marketing, TI, Gestión Gerencial, Recorrido por instalaciones,
Producción, Recursos Humanos, SSOMA, Seguimiento de hallazgos del ciclo
anterior, Revisión documental complementaria, Reunión de cierre.

Sección de Observaciones con notas del alcance (ejecución por muestreo, no
exhaustiva; toda modificación al plan debe quedar registrada).

### 2.2 `PE2-R08 Notas de Auditoría` (Word) — tercer instrumento

Versión 2, 12/06/2026, 2 páginas. **Es un registro distinto del plan y del
checklist**, y se llena por proceso auditado.

1. Identificación del proceso auditado: proceso · responsable del proceso ·
   cargo · fecha · auditor · sede/lugar · entrevistados adicionales.
2. Criterios auditados y alcance de la muestra: cláusulas/criterios auditados ·
   objetivo del muestreo · período/muestra revisada · seguimiento de hallazgos
   previos (sí/no).

Su ausencia es motivo de limitación declarada: el informe dice que no se
dispuso de la nota PE2-R08 del proceso de Producción y por eso la evidencia se
consolidó de otra forma.

### 2.3 `Checklist_ISO9001_*.xlsx`

Encabezado: título "CHECKLIST DE AUDITORÍA INTERNA – ISO 9001:2015 | ADQUIM",
**`Proceso`** (ej. "Control de Calidad | AUS 32 / AUS 40 / Icarb 25") y los
campos Auditor · Auditado · Fecha · Código.

Columnas: N° · Cláusula ISO 9001 · Requisito Textual (ISO 9001:2015) ·
Pregunta de Auditoría · Comentarios / Evidencia · Cumplimiento.

Las filas se **agrupan por capítulo de la norma** con filas de encabezado
("4. CONTEXTO DE LA ORGANIZACIÓN").

Escala de cumplimiento: **2 = Cumple · 1 = Parcial · 0 = No Cumple**.
Hojas: Checklist y Leyenda.

Cláusulas vistas en los checklists: 4.4, 6.3, 7.1.3, 7.1.4, 7.1.5.

**El checklist es por proceso, no por auditoría.** El nombre del archivo trae
el número de proceso (`_08_Control_Calidad_`) y el encabezado lo repite.

### 2.4 `Informe_Auditoria_Interna_ISO9001`

**Encabezado:** fecha del informe · N° auditoría interna (`001/2026`) ·
fecha(s) de auditoría · norma/referencia (`ISO 9001:2015`) · **objetivo**
(cuatro objetivos numerados, separado del alcance) · **alcance** (los 13
procesos + período auditado) · sitio(s) auditado(s) · responsable de la
auditoría por parte de la organización (tres personas con cargo: representante
legal, CFO, encargado del SGC) · auditor líder · equipo auditor · metodología ·
limitaciones relevantes.

**El equipo auditor trae la asignación de procesos por auditor**, no una lista
plana: "Darwin Pérez Lucena (Producción, Control de Calidad, Logística y
Despacho, Adquisiciones); Kareli Colmenares (Recursos Humanos, Marketing, TI);
Juan Carlos Carmona (Gestión Gerencial, Ventas, SSOMA); Kerwin Bermúdez
(Gestión de Calidad, Investigación y Desarrollo, Mantenimiento)".

**Resumen ejecutivo** como tabla de conteos: procesos auditados (13) ·
fortalezas (8) · no conformidades (5) · observaciones (10) · oportunidades de
mejora (11). Más una conclusión ejecutiva en prosa que cita la tasa de cierre
del ciclo anterior (56%, 9 de 16 hallazgos cerrados conformes).

**Nota sobre "fortalezas":** se cuentan aparte y no aparece un conteo de
"conformidades". La clasificación efectiva del cliente es fortaleza / no
conformidad / observación / oportunidad de mejora.

**Matriz de resultados por proceso** — tabla que no estaba identificada antes:
proceso · criterio / cláusulas auditadas · evidencia clave revisada · código(s)
de hallazgo · clasificación · conclusión del proceso. La clasificación es a
nivel de proceso ("Conforme con observaciones", "Observación", "No
conformidad") y la conclusión es un párrafo por proceso.

**Ficha por hallazgo:** código · proceso · requisito / criterio · lote ·
persona · fecha · evidencia objetiva · descripción del hallazgo · responsable
del proceso · clasificación · hallazgo concordante con · riesgo / impacto ·
registro / documentos · plazo / tratamiento.

**Prefijos de código observados:** `NC-2026-01` (no conformidad),
`OBS-2026-01` (observación), `OM-2026-01` (oportunidad de mejora).

**`Hallazgo concordante con` lleva justificación, no solo el código:**
"NC-2026-01 (mismo tipo de brecha de control de cambios (cl. 8.5.6), en un
producto distinto)".

Los criterios citados en los hallazgos son cláusulas de ISO 9001:2015: 7.5,
8.5.1, 8.5.6 (control de cambios), 8.4.1 (proveedores externos), 8.3.4, 8.3.5,
8.6, 8.7, 7.4, 8.2.1, 8.2.2, 8.2.3, 9.1.2.

### 2.5 SharePoint — Sistema de Gestión de Calidad de Adquim

Listas y bibliotecas: Políticas · Objetivos · Procedimientos · Instrucciones de
Trabajo · Flujos automatizados · Formatos · Documentos externos · Registros ·
Productos/Servicios y Salidas · Listado de productos · **Quejas o Reclamos** ·
**No Conformidades** · **Acciones Correctivas** · **Tratamiento de No
Conformidades 2026** · Obsoletos · Papelera de reciclaje.

Columnas de la lista No Conformidades: Empresa · Fuente NC · Descripción ·
Corrección · Severidad NC · Evidencia Objetiva · Impacto NC · Proceso · Efecto
potencial · Otro proceso.

**Segunda inconsistencia observada:** la severidad es `Alta` en Power Apps y
`Mayor` en la lista de SharePoint. Dos vocabularios para lo mismo.

En la lista aparece también una referencia a "Certificación ISO 22.241", lo que
indica que ADCLEAN opera bajo más de un esquema normativo.

Los instructivos de trabajo (`PP3-I01`, `PP3-P05`, `PE5-P03`) son documentos
Word versionados en SharePoint, con encabezado de código, versión, fecha y
paginación.

---

## 3. Requisito verbal recogido en la reunión

Al guardar un registro, **llega correo a los responsables** indicándoles que
deben cumplir con su etapa, **con fecha límite**.

---

## 4. Ubicación de las capturas

Las 47 capturas se extrajeron del RTF y se convirtieron a PNG. No están
versionadas en el repositorio por peso (23 MB). Si se decide incorporarlas,
el subconjunto relevante es el de las capturas 1 a 19 (la aplicación Power
Apps); el resto son documentos que ya están descritos arriba.
