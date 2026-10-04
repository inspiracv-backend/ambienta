# Proposal: Un documento y lo que respalda, en los dos sentidos

Fuente: Análisis Funcional v1.8 §3.17, **RF-108** — *«Vinculación transversal
documento ↔ norma / proceso / obligación / auditoría»*. Issue #73, sub-tarea de
la épica #31.

## Lo que hay hoy, medido el 7-sep-2026

`entity_documents` existe desde `01_schema.sql` con su modelo, su CRUD, su
esquema Pydantic y **cinco endpoints** bajo `/documents/{id}/entities`. Y:

| Medida | Valor |
|---|---|
| Filas en la base | **0** |
| Archivos del frontend que la nombran | **0** |
| Sentidos de consulta que ofrece | **1** — desde el documento |

Es, otra vez, el patrón que este repositorio ya sufrió con `bcn.sincronizar()`,
`control_documental.py` y `declaration_submissions`: código escrito, probado y
sin un solo llamador. Aquí con un agravante — la tabla ni siquiera puede
contestar la pregunta que la gente hace.

### El sentido que falta es el que se usa

Nadie abre un documento para averiguar qué respalda. Se abre **la obligación**
—o la auditoría, o el artículo evaluado— y se pregunta *«¿con qué se sostiene
esto?»*. Ese sentido no existe: no hay ninguna ruta que reciba una entidad y
devuelva sus documentos.

Y es justo el que importa en una fiscalización, porque la pregunta del
fiscalizador tiene esa forma: señala un requisito y pide la evidencia.

### RF-108 nombra cuatro anclajes y la tabla admite dos

El CHECK de `entity_type` lista once valores. **`legal_norm` y `process` no
están**, y son dos de los cuatro que el requisito nombra por su nombre. Hoy un
procedimiento no se puede colgar del proceso que describe.

### Y el vínculo acepta identificadores que no existen

Medido con una sonda contra la base real, desde la empresa A:

| lo que se manda | respuesta |
|---|---|
| un `entity_id` inventado | **201, y la fila queda escrita** |
| una obligación **real de la empresa B** | **201, y la fila queda escrita** |

`entity_id` es polimórfico, así que **no tiene clave foránea**: nada lo mira. No
es una fuga de lectura —la fila nace en el tenant de quien la escribe— pero sí
una afirmación falsa en un sistema de cumplimiento: la ficha diría *«este
procedimiento respalda la obligación X»* señalando algo que en esta empresa no
existe. Es la misma familia que la fuga de `article_compliance_id`, y el arreglo
—`validar_visible`— ya está escrito.

## Lo que se propone

1. **Comprobar el `entity_id`** contra la tabla que corresponde a su
   `entity_type`, con la sesión del tenant. Las dos negativas —no existe, y
   existe pero es de otra empresa— responden **lo mismo**: distinguirlas sería
   un oráculo para enumerar identificadores ajenos.
2. **Agregar `legal_norm` y `process`** al CHECK, que es lo que RF-108 pide.
3. **El sentido inverso**: una ruta que reciba entidad y devuelva sus documentos.
4. **Mostrarlo**: la ficha de la obligación lista lo que la respalda, y desde el
   documento se ve a qué se engancha.

## Lo que NO entra, y por qué

- **RF-109, permisos de lectura por documento según departamento y rol.** Es una
  segunda barrera sobre un modelo que hoy no la tiene en ninguna tabla, y
  merecería su propia decisión. Vincular no cambia quién ve qué.
- **Los otros tres de la épica** (#74 comentarios, #75 línea de tiempo, #76
  buscador) necesitan tablas nuevas. Este cambio no las crea.
- **Migrar las bibliotecas de SharePoint.** La decisión 9 de la v1.8 ya está
  tomada de hecho —el control documental **reemplaza**, no hay una línea de
  código de SharePoint— y este cambio no la mueve.
