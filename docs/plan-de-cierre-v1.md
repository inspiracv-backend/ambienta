# Plan de cierre de la versión 1.0

**Actualizado el 7-sep-2026.**

## Qué es esto, y qué no

Es el plan para dejar Ambienta en **versión 1.0 y listo para desplegar**.
Desplegar **no entra**: el MVP corre en local, no hay dominio, y pasar a
producción es una decisión posterior.

**Este archivo existe porque el plan vivía sólo en una conversación.** La
pregunta "¿en qué semana vamos?" no se podía contestar mirando el repositorio, y
eso es exactamente lo que este proyecto persigue en todo lo demás: estado que
sólo existe en la cabeza de alguien. El detalle día a día original no se
conserva; lo que sigue es la reconstrucción por bloques, y se dice para que nadie
lo cite como si fuera el documento firmado.

## Dónde vamos

**Semana 2, y el bloque C ya está cerrado.** La semana 1 terminó con el CRM
usable y la épica de notificaciones. La 2 se llevó C, la épica ISO 14001 (#28) y
el historial de presentaciones, que no estaba en el plan y hacía falta: la tabla
`declaration_submissions` existía desde el principio **sin un solo escritor**.

Quedan **D, E y F**, y de esos el único grande es D.

| Bloque | Qué | Estado |
|---|---|---|
| **A1–A2** | Estabilidad: el CRM roto, la eficacia, el tipo de registro | Cerrado |
| **A3** | Los routers sin pruebas de escritura | Cerrado — 0 defectos en obligaciones, ISO, documentos, soporte, notificaciones; **1 en auditorías** |
| **A4** | El cron de avisos demostrable en local | Cerrado — y apareció que el cron no avisaba nunca |
| **B1–B2** | Verificación de eficacia, datos por tipo de registro | Cerrado |
| **B3** | Las 5 etapas con responsable (#38, #43) | **Bloqueado** en la decisión #57 |
| **B4** | Catálogos por empresa (#41, RF-100) | Cerrado |
| **B5** | Informe con matriz por proceso (#42, RF-101) | Cerrado |
| **C** | Gestores, sub-tenancy y contratos (#59–65) | Cerrado — el gestor veía un sistema vacío: 0 filas y ninguna ruta que nombrara a un cliente |
| **ISO** | Épica #28: aspectos, riesgos, equipos | Cerrado el 6-sep — a la API no le faltaba nada, faltaba **llamarla** |
| **RF-31** | Historial de presentaciones | Cerrado el 7-sep — `declaration_submissions` tenía CRUD completo y cero escritores |
| **D** | Normativa propia: parseo de ISO y RCA | Pendiente |
| **E** | Información documentada y colaboración (#73–76) | Pendiente |
| **F** | Archivar los specs y recorrer el sistema entero | Pendiente |

## Lo que bloquea, y a quién le toca

**No son míos.** Cada uno espera una decisión de negocio:

| Bloqueo | Qué frena | Qué hace falta |
|---|---|---|
| **#57** | B3 entero | Confirmar tres cosas: la escala de severidad, los estados del hallazgo, y si las etapas del tratamiento son JSONB o tabla tipada |
| **#34** | Parte de la épica #27 | Las 9 decisiones abiertas de la v1.8 |
| Normativa RCA | Parte de D | 2–3 RCA reales, y qué secciones son exigibles |
| Catálogo BCN | Nada urgente | Qué normas importar de las 748.000 |

Mientras #57 no se resuelva, **B3 no se puede hacer bien**: el modelo de las
etapas es justamente lo que se está decidiendo, y elegirlo por mi cuenta
significaría una migración cuando la decisión llegue.

## Lo que queda fuera de la 1.0, a propósito

- **Desplegar.** Ver arriba.
- **La épica #24 (AmbiAgent).** La hace otra persona.
- **#64**, la extracción con IA de un PDF de contrato: depende de `ai-service`,
  que hoy es una carpeta vacía.
- **Los plazos por etapa** del registro de mejora: dependen de #57.
- **El repositorio de plantillas Excel** y la `periodicidad` de `retc_systems`:
  son contenido oficial que hay que descargar de los portales del Estado, no
  código. Inventarlos produciría vencimientos falsos.

## Cómo se mide que un bloque está cerrado

No por el checkbox del issue. Este proyecto ya cerró épicas enteras sobre código
que respondía 500 —el CRM— o que nadie llamaba —`bcn.sincronizar()`,
`control_documental.py`—. Un bloque se cierra cuando:

1. Las escrituras se ejecutan **por el camino HTTP real**, no llamando al
   handler: `TestClient` pasa por `app/errores.py`, y llamar al handler directo
   confunde un 422 con un fallo del servidor.
2. Hay una prueba que **falla al romper a propósito** lo que dice proteger.
3. Lo que se agrega tiene **un llamador**. Una tabla que nadie lee es el patrón
   que este repositorio repite.

## Verificación

```bash
cd apps/api
DATABASE_URL=postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta python -m pytest
```

Al 7-sep: **653 pruebas del frontend en verde** sobre 58 archivos, y el
`tsc --noEmit` limpio. La suite de la API se midió por última vez el 4-sep en
**1214 en verde** con 12 saltadas (las que salen a internet); hoy no se pudo
correr porque Docker no levantó, así que ese número **es de hace tres días** y
conviene volver a medirlo antes de citarlo.

El auditor (`python herramientas/auditar.py`) baja de 27 a 26 endpoints sin
llamador. El frontend y el esquema, en `CLAUDE.md` § Verificación.
