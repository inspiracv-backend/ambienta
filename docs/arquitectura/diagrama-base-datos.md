# Modelo entidad-relación — Ambienta

**Fuente de verdad:** [`db/01_schema.sql`](../../db/01_schema.sql). Este documento describe lo que ese archivo crea; si difieren, manda el SQL.

**52 tablas · 156 claves foráneas · RLS multi-tenant · PostgreSQL 16 + pgvector**

Los diagramas están agrupados por dominio porque un ER de 52 tablas en una sola imagen no se lee. Para no saturarlos se omiten las columnas de auditoría (`created_at/by`, `updated_at/by`, `deleted_at`), que existen en toda tabla de negocio.

---

## 1. Cómo se conectan los dominios

```mermaid
flowchart TD
    A["1· Organización<br/>tenants · facilities · departments · users"]
    B["2· RBAC<br/>roles · permissions"]
    C["3· Catálogo normativo GLOBAL<br/>legal_norms · versions · articles"]
    D["4· Matriz legal<br/>matrices · matrix_norms · article_compliance"]
    E["5· Obligaciones<br/>obligations · tasks · declaraciones"]
    F["6· Evidencia<br/>documents · versions"]
    G["7· Auditoría y mejora<br/>audits · nonconformities · action_plans"]
    H["8· ISO 14001<br/>aspectos · riesgos · equipos"]
    I["9· Transversales<br/>notificaciones · soporte · chatbot · audit_log"]

    A --> B
    A --> D
    C --> D
    D --> E
    D --> G
    D --> H
    E --> F
    G --> F
    G --> D
    A --> I

    style C fill:#e8f5e9,stroke:#2e7d32
    style D fill:#e3f2fd,stroke:#1565c0
```

**La decisión estructural del modelo:** el catálogo normativo (verde) **no lleva `tenant_id`** — la ley es la misma para todos. La aplicabilidad y el cumplimiento sí son por empresa, y viven en la matriz legal (azul). Esa separación es lo que permite sincronizar BCN una vez y que sirva a todos los clientes.

---

## 2. Organización y multi-tenancy

```mermaid
erDiagram
    countries   ||--o{ tenants     : "opera en"
    tenants     ||--o{ facilities  : "tiene"
    tenants     ||--o{ departments : "tiene"
    tenants     ||--o{ users       : "emplea"
    tenants     ||--o{ processes   : "define"
    tenants     ||--o{ tenants     : "sub-tenant de"
    facilities  ||--o{ departments : "aloja"
    departments ||--o{ departments : "jerarquía"
    departments ||--o{ users       : "asigna"
    departments ||--o{ processes   : "responsable de"
    processes   ||--o{ processes   : "jerarquía"
    facilities  ||--o{ facility_processes : ""
    processes   ||--o{ facility_processes : ""
    tenants     ||--o{ contracts   : "gestor"
    tenants     ||--o{ contracts   : "cliente"
```

`tenants.parent_tenant_id` registra la relación gestor → sub-tenant. **Un sub-tenant es un tenant real** con su propio aislamiento RLS, no una partición dentro del gestor. `contracts` formaliza el vínculo comercial entre ambos.

## 3. RBAC

```mermaid
erDiagram
    tenants     ||--o{ roles            : "define"
    roles       ||--o{ role_permissions : ""
    permissions ||--o{ role_permissions : ""
    users       ||--o{ user_roles       : ""
    roles       ||--o{ user_roles       : ""
    facilities  ||--o{ user_roles       : "alcance"
    departments ||--o{ user_roles       : "alcance"
    users       ||--o{ user_permissions : "excepción individual"
    permissions ||--o{ user_permissions : ""
```

39 permisos sembrados en `03_seed_catalogos.sql`. `user_roles` permite acotar un rol a una planta o departamento concreto, no solo a la empresa.

**Permiso efectivo**, en este orden:

1. Si hay fila en `user_permissions` para ese par (usuario, permiso), manda esa.
2. Si no, se une lo que otorguen sus roles vigentes en `user_roles`.
3. En ambos niveles, `granted = false` es denegación explícita y gana sobre cualquier concesión.

El paso 3 es lo que permite quitarle **un** permiso a alguien sin sacarlo del rol ni crear un rol de excepción (RF-12).

## 4. Catálogo normativo (global, sin `tenant_id`)

```mermaid
erDiagram
    countries          ||--o{ legal_sources      : ""
    countries          ||--o{ legal_norms        : ""
    legal_sources      ||--o{ legal_norms        : "origen"
    legal_sources      ||--o{ norm_sync_runs     : "sincroniza"
    legal_norms        ||--o{ legal_norm_versions: "versiona"
    legal_norm_versions||--o{ legal_articles     : "contiene"
    legal_articles     ||--o{ legal_articles     : "inciso/numeral"
    legal_norms        ||--o{ legal_relations    : "origen"
    legal_norms        ||--o{ legal_relations    : "destino"
    countries          ||--o{ sectors            : ""
    sectors            ||--o{ sectors            : "taxonomía"
    legal_norms        ||--o{ norm_sectors       : ""
    sectors            ||--o{ norm_sectors       : ""
```

La cadena **norma → versión → artículo** es lo que permite evaluar cumplimiento a nivel de artículo y saber con qué texto vigente se evaluó. `legal_relations` modela modificaciones, derogaciones y concordancias entre normas — la estructura que entrega BCN.

## 5. Matriz legal y cumplimiento

```mermaid
erDiagram
    tenants              ||--o{ tenant_legal_matrices : "por año"
    facilities           ||--o{ tenant_legal_matrices : "evalúa"
    tenant_legal_matrices||--o{ matrix_norms          : "incluye"
    legal_norms          ||--o{ matrix_norms          : ""
    legal_norm_versions  ||--o{ matrix_norms          : "versión evaluada"
    sectors              ||--o{ matrix_norms          : "justifica"
    matrix_norms         ||--o{ article_compliance    : "artículo a artículo"
    legal_articles       ||--o{ article_compliance    : ""
    facilities           ||--o{ article_compliance    : ""
    departments          ||--o{ article_compliance    : "responsable"
    facilities           ||--o{ facility_norm_assignments : "asignación previa"
    legal_norms          ||--o{ facility_norm_assignments : ""
```

**Este es el corazón del producto.** `facility_norm_assignments` es la asignación preliminar norma↔planta antes de entrar a una matriz anual formal; `article_compliance` es la evaluación concreta, con estado, riesgo, responsable y evidencia.

## 6. Obligaciones, tareas y declaraciones

```mermaid
erDiagram
    obligation_templates ||--o{ obligations            : "instancia"
    matrix_norms         ||--o{ obligations            : "origen legal"
    article_compliance   ||--o{ obligations            : "artículo"
    facilities           ||--o{ obligations            : ""
    obligations          ||--o{ tasks                  : "descompone"
    tasks                ||--o{ tasks                  : "subtarea"
    departments          ||--o{ tasks                  : ""
    obligations          ||--o{ declaration_submissions: "presenta"
    declaration_templates||--o{ declaration_submissions: "formato"
    documents            ||--o{ declaration_submissions: "comprobante"
```

`tasks` es el ticket único que alimenta Calendario, Gantt y Kanban — no hay tres entidades distintas para las tres vistas.

## 7. Documentos y evidencia

```mermaid
erDiagram
    tenants          ||--o{ documents        : ""
    documents        ||--o{ document_versions: "versiona"
    documents        ||--o{ entity_documents : "se adjunta a"
```

`entity_documents` es un vínculo polimórfico (`entity_type` + `entity_id`) que conecta un documento con cumplimiento, obligación, tarea, plan, auditoría, hallazgo o contrato. Los binarios **no** viven en PostgreSQL: `document_versions` guarda `storage_provider` + `storage_key`.

## 8. Auditoría y mejora

```mermaid
erDiagram
    tenants           ||--o{ audits             : ""
    facilities        ||--o{ audits             : ""
    audits            ||--o{ audit_items        : "checklist"
    audits            ||--o{ audit_participants : "equipo"
    users             ||--o{ audit_participants : ""
    article_compliance||--o{ audit_items        : "verifica"
    audit_items       ||--o{ nonconformities    : "hallazgo"
    article_compliance||--o{ nonconformities    : "incumplimiento legal"
    nonconformities   ||--o{ action_plans       : "trata"
    article_compliance||--o{ action_plans       : "trata"
```

Una no conformidad puede nacer de un punto de auditoría **o** directamente de un artículo incumplido. El tratamiento por etapas vive hoy en la columna JSONB `nonconformities.improvement_stages`.

## 9. ISO 14001

```mermaid
erDiagram
    tenants               ||--o{ environmental_aspects : ""
    facilities            ||--o{ environmental_aspects : ""
    processes             ||--o{ environmental_aspects : "genera"
    article_compliance    ||--o{ environmental_aspects : "requisito legal"
    environmental_aspects ||--o{ risks_opportunities   : "deriva"
    action_plans          ||--o{ risks_opportunities   : "trata"
    facilities            ||--o{ regulated_equipment   : ""
    regulated_equipment   ||--o{ equipment_operators   : ""
    users                 ||--o{ equipment_operators   : "habilitado"
```

Implementa la cadena de §6.1 de ISO 14001: **proceso → aspecto ambiental → riesgo/oportunidad → plan de acción**, con el requisito legal enganchado al aspecto.

## 10. Transversales

```mermaid
erDiagram
    tenants               ||--o{ notification_templates  : ""
    tenants               ||--o{ notification_rules      : ""
    notification_rules    ||--o{ notifications           : "dispara"
    users                 ||--o{ notifications           : "destinatario"
    tenants               ||--o{ support_tickets         : ""
    support_tickets       ||--o{ support_ticket_messages : ""
    tenants               ||--o{ chatbot_conversations   : ""
    chatbot_conversations ||--o{ chatbot_messages        : ""
    tenants               ||--o{ integration_accounts    : ""
    tenants               ||--o{ audit_log               : ""
    tenants               ||--o{ entity_status_history   : ""
```

`audit_log` es append-only: el rol `ambienta_app` no tiene `UPDATE` ni `DELETE` sobre esa tabla. `entity_status_history` guarda el historial funcional de estados que se muestra en pantalla, distinto del log técnico.

---

## 11. Aislamiento multi-tenant

Dos barreras independientes:

1. **La aplicación** filtra por `tenant_id` en cada repositorio.
2. **RLS en PostgreSQL** existe para cuando la primera falle.

Para que la segunda funcione, la API abre cada transacción declarando el tenant:

```sql
SET LOCAL ROLE ambienta_app;
SELECT set_config('ambienta.tenant_id', '<uuid>', true);
```

Implementado en [`apps/api/app/deps.py`](../../apps/api/app/deps.py) (`get_tenant_db`). Dos detalles que importan:

- **El rol no puede ser superusuario.** `postgres` ignora RLS por completo: con esa conexión el aislamiento no existe aunque las policies estén.
- **Sin `ambienta.tenant_id` seteado, las consultas no devuelven filas.** Falla cerrado a propósito — es preferible una pantalla vacía a una fuga entre clientes.

Verificación: [`db/02_smoke_test.sql`](../../db/02_smoke_test.sql) corre 9 comprobaciones — aislamiento de lectura y escritura entre empresas, inmutabilidad del audit log, CHECK de negocio, unicidad por empresa, fallo cerrado sin tenant, unicidad de la matriz por periodo y permisos individuales. Hace `ROLLBACK` al final, así que se puede correr contra cualquier base sin ensuciarla.

---

## 12. Convenciones

| Regla | Detalle |
|---|---|
| Identificadores | `uuid` para entidades de negocio · `bigserial` para eventos · `smallserial` para catálogos |
| Tiempo | `timestamptz` para eventos · `date` para vigencias legales |
| Auditoría | `created_at/by` y `updated_at/by` en toda tabla de negocio; `updated_at` lo mantiene un trigger |
| Borrado | Lógico con `deleted_at` + índices parciales `WHERE deleted_at IS NULL` |
| Enumerados | `varchar` + `CHECK`, no tipos `ENUM` nativos — evolucionan sin migración de tipo |
| JSONB | Solo payload externo, snapshots y configuración; nunca reemplaza una FK |
| Sin `tenant_id` (14 tablas) | `tenants` — es la tabla de empresas, no lleva referencia a sí misma. Y el catálogo compartido: `countries`, `permissions`, `role_permissions`, `legal_sources`, `legal_norms`, `legal_norm_versions`, `legal_articles`, `legal_relations`, `sectors`, `norm_sectors`, `norm_sync_runs`, `obligation_templates`, `declaration_templates` |

---

## 13. Lo que el modelo todavía no cubre

Documentado para que no se confunda "no está" con "se olvidó":

- **Borrador v1.8 del Análisis Funcional** (RF-90 a RF-114): instrumentos de auditoría, checklist por cláusula, `Hallazgo` como entidad separada del registro de mejora, información documentada y colaboración. Tiene 9 decisiones abiertas; CLAUDE.md §1 exige spec aprobada antes de implementar.
- **Salidas reglamentarias de la gestión de mejoras**: modificar la matriz de riesgos corporativa, la matriz FODA y los procedimientos/instructivos del SGC. Hoy `risks_opportunities` cubre el riesgo **ambiental** de ISO 14001, no la matriz de riesgo corporativa por horizonte (corto/medio/largo plazo) ni el FODA de ISO 9001 §4.1.
- **Embeddings para el chatbot.** Hay `pgvector` instalado y `chatbot_messages.citations`, pero ninguna tabla con columna `vector` sobre `legal_articles` — el RAG no tiene de dónde recuperar todavía.
- **Escala de severidad configurable** (RF-100): hoy es un `CHECK` con `minor · major · critical`; el borrador v1.8 la quiere por empresa.
