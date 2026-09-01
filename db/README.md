# Base de datos — Ambienta

Esquema PostgreSQL del sistema. 52 tablas, RLS multi-tenant y catálogos base.

## Estado verificado

**09-ago-2026** — recreada desde cero con `docker compose down -v && up`. Los
seis scripts de init corrieron en orden sin un solo error, y las 9
comprobaciones de `02_smoke_test.sql` pasaron.

| Qué | Cuánto |
|---|---|
| Tablas | 52 |
| Políticas RLS · tablas con `FORCE` | 38 · 38 |
| Claves foráneas | 156 |
| Índices | 142 |
| Permisos sembrados | 39 |
| Datos de demo | 2 empresas · 5 usuarios · 5 obligaciones · 6 artículos evaluados |

Comprobado además: `user_permissions` tiene su política `tenant_isolation` y su
`GRANT` (no los hereda por nacer en una migración), las dos unicidades tratan
los NULL como iguales, y `users.clerk_id` existe. La API responde el tablero en
0,3 s con 40,0 % de cumplimiento — el mismo número que da el cálculo a mano.

Para reproducirlo: `bash db/run.sh --with-tests`.

## Ejecutar

Con Docker, desde cero:

```bash
docker run -d --name ambienta-pg -e POSTGRES_PASSWORD=ambienta -e POSTGRES_DB=ambienta -p 5432:5432 pgvector/pgvector:pg16
```

Después, en orden. El orden importa: `04` y `05` alteran tablas que crea `01`, y
`02_seed` inserta filas que dependen de los catálogos.

```bash
psql "postgresql://postgres:ambienta@localhost:5432/ambienta" -v ON_ERROR_STOP=1 \
  -f db/01_schema.sql \
  -f db/04_clerk_auth.sql \
  -f db/05_user_permissions.sql   -f db/06_ticket_number.sql   -f db/07_rol_aplicacion.sql \
  -f db/08_perfil_normativo.sql \
  -f db/09_roles_por_codigo.sql \
  -f db/10_acceso_invitado.sql \
  -f db/11_solicitud_de_invitado.sql \
  -f db/12_reportabilidad_retc.sql \
  -f db/13_usuario_interno_con_departamento.sql \
  -f db/14_ds90_es_de_la_bcn.sql \
  -f db/15_declaracion_ante_su_sistema.sql \
  -f db/16_evidencia_del_articulo.sql \
  -f db/17_avisos_sin_duplicados.sql \
  -f db/18_control_documental.sql \
  -f db/21_significancia_del_aspecto.sql \
  -f db/03_seed_catalogos.sql \
  -f db/02_seed.sql
```

`docker compose up` los carga solos la primera vez que crea el volumen, en este
mismo orden. **Todo archivo de esquema nuevo tiene que agregarse a los cuatro
lados** — acá, en `db/run.sh`, en `docker-compose.yml` y en
`docker-compose.prod.yml` — o existirá solo en las bases donde alguien lo
aplicó a mano.

O todo junto con el script:

```bash
bash db/run.sh
```

## Archivos

| Archivo | Qué hace |
|---|---|
| `01_schema.sql` | Extensiones, 52 tablas, 156 FK, índices, triggers, RLS y rol de aplicación. Transaccional: o entra todo o no entra nada |
| `02_smoke_test.sql` | 9 verificaciones de las garantías: aislamiento entre empresas, inmutabilidad del audit log, CHECK de negocio, unicidad de la matriz por periodo y permisos individuales. Hace `ROLLBACK` al final |
| `03_seed_catalogos.sql` | Países, fuentes normativas, 39 permisos, sectores CIIU y plantillas de declaración. Idempotente |
| `04_clerk_auth.sql` | Columna `clerk_id` en `users` con UNIQUE, para vincular con Clerk (ADR-006). Idempotente |
| `05_user_permissions.sql` | Tabla `user_permissions` (RF-12) y dos unicidades que tratan los NULL como iguales. Crea su propia política RLS y sus permisos: una tabla nacida en una migración no hereda el `GRANT ON ALL TABLES` ni el bucle de políticas de `01_schema`. Idempotente |
| `06_ticket_number.sql` | Secuencia que genera `support_tickets.ticket_number`. Lo hace la base y no Python porque la unicidad es global: calcular `max()+1` en la aplicación abre una carrera entre peticiones de tenants distintos. Incluye el `GRANT` sobre la secuencia, que no se hereda. Idempotente |
| `07_rol_aplicacion.sql` | Da `LOGIN` a `ambienta_app` para que la API se conecte con un rol que **no** puede saltarse RLS. Antes se conectaba con el dueño (superusuario con `BYPASSRLS`) y el aislamiento dependía de un `SET LOCAL ROLE` por transacción, que se perdía en cada `commit`. Idempotente |
| `08_perfil_normativo.sql` | Perfil normativo de la empresa: `tenants.sector_id` (FK a `sectors`, CIIU) y `size_bracket` por tramo, mas `matrix_norms.inclusion_source` para distinguir la norma que incluyo el calculo de la que agrego una persona. **No crea tablas**, asi que no declara RLS ni GRANT: las columnas heredan los de su tabla. Idempotente |
| `09_roles_por_codigo.sql` | Corrige los permisos de los tres roles del sistema, que `02_seed` asignaba **por id numerico** contra un catalogo distinto del que finalmente quedo — el Admin Empresa terminaba sin poder administrar usuarios. Crea los roles en **todas** las empresas y agrega `servicio_lectura` para integraciones. Idempotente |
| `10_acceso_invitado.sql` | Credenciales del Cliente Invitado (RF-01, RF-02, RF-07): RUT, clave con hash y vigencia acotada. **No es un usuario**: no abre ningun endpoint de negocio, solo el seguimiento de sus propias solicitudes. Trae su propia politica RLS y sus GRANT, porque el bucle de `01_schema` ya corrio. Idempotente |
| `11_solicitud_de_invitado.sql` | Vincula la solicitud con la credencial que la abrió (`support_tickets.guest_credential_id`). Sin esto, «el invitado ve solo lo suyo» no se puede cumplir: filtrar por `guest_email` sería **peor que no filtrar**, porque el correo lo escribe la misma persona en el formulario y cualquiera puede poner el de otro. **No crea tablas**, así que hereda RLS y GRANT de `support_tickets`. Idempotente |
| `12_reportabilidad_retc.sql` | Sistemas sectoriales del RETC y su reportabilidad por instalación (ADR-004, #102 y #103). **Dos tablas y la separación importa:** `retc_systems` es catálogo global sin `tenant_id` —los portales son los mismos para todas— y `facility_retc_reporting` es dato de empresa, con RLS propia. **Un sistema sectorial NO es un sector CIIU**: uno dice *ante quién se declara*, el otro *a qué se dedica la empresa*. Siembra los **12 sectoriales** del portal oficial con su procedencia en cada fila, en `active = false` hasta que negocio los confirme; los 9 de la SMA que menciona ADR-004 **no se siembran** porque no hay fuente verificable. Idempotente |
| `13_usuario_interno_con_departamento.sql` | RF-11: todo Usuario Interno pertenece a un Departamento. **No es un `NOT NULL` a secas y esa es la decisión:** `user_type` admite cinco valores y solo `internal` y `tenant_admin` son «Usuario Interno». Un `NOT NULL` plano obligaría al Admin Global a pertenecer a un departamento de una empresa cliente, y el día que entrara el primero habría que romper la restricción. Va un CHECK condicionado al tipo. Rellena antes con el primer departamento de la empresa, y **se detiene con un mensaje** si alguna empresa tiene internos y ningún departamento — adivinar por ellas sería inventar estructura organizacional. Idempotente |
| `14_ds90_es_de_la_bcn.sql` | Mueve el DS 90/2000 de `ISO` a `BCN_LEYCHILE`. **No es cosmetico:** con la fuente equivocada la sincronizacion no lo reconoce como suyo, no lo adopta, y crea la norma real **al lado** de la sembrada. La clasificacion por sector queda pegada a la copia falsa y la matriz de la empresa se vacia sin ningun error a la vista. Solo mueve la fila si sigue en ISO y sin `external_norm_id` — si alguien ya la corrigio a mano, no la toca. Idempotente |
| `15_declaracion_ante_su_sistema.sql` | La obligacion declara **ante que portal se presenta** (#114). Antes el sistema se deducia partiendo el codigo por guiones (`OBL-SIDREP-2026S1`), y el codigo lo escribe una persona en texto libre: uno con otra forma dejaba la obligacion sin sistema **y sin ningun error** — el boton de ir al sistema oficial simplemente no aparecia. La referencia va a `retc_systems`, que es donde vive `url_oficial`; copiarla en cada fila obligaria a corregirlas una por una el dia que el Estado mueva un portal. Es **opcional**: un compromiso de RCA no se presenta ante ninguno. Idempotente |
| `16_evidencia_del_articulo.sql` | La evidencia de un articulo evaluado (#126). **Se estaba perdiendo en silencio, con respuesta 200:** el dialogo la pide, el store la manda como `evidence_url`, `evaluate_article()` la asignaba... y la columna no existia. SQLAlchemy acepta que se le ponga un atributo cualquiera a una instancia y no lo persiste, asi que nada fallaba — pegabas el enlace, veias «guardado», recargabas y no estaba. Va como URL y no por `entity_documents` porque RF-07 pide adjuntar desde Drive u OneDrive: un enlace a un archivo que vive fuera, no un documento nuestro con versiones. Trae un indice parcial para separar lo que incumple **sin nada que mostrar**, que es lo que hay que atender primero. Idempotente |
| `17_avisos_sin_duplicados.sql` | Un aviso de vencimiento por obligacion y ventana, **no tres** (#119). Medido: tres corridas de `create_deadline_notifications()` dejaban tres avisos identicos. El generador esta pensado para un cron diario, asi que un reinicio o un reintento repetia el correo. El dano no es el ruido sino lo que provoca: un sistema que avisa de mas se deja de leer, y despues pasa de largo el aviso que importaba. Va como `dedupe_key` **generica** —no una columna `obligation_id`— porque `notifications` sirve a cualquier evento. La migracion **limpia los duplicados que ya existen** antes de crear el indice, o fallaria en cualquier base con datos. Idempotente |
| `18_control_documental.sql` | Control de informacion documentada, ISO 9001 §7.5 (RF-102 a RF-106). La capa de evidencias ya existia; **lo que faltaba era el control**: sin codigo no se puede citar un documento en una auditoria, y sin aprobacion registrada **nada impedia usar un borrador como evidencia**. La decision de diseno: el ciclo de vida vive en la **revision**, no en el documento — poner el estado en `documents` haria que aprobar la revision 4 borrara el rastro de que la 3 estuvo vigente entre tales fechas, que es lo que pregunta una auditoria. Dos restricciones con dientes: aprobado exige quien y cuando, y **una sola revision vigente por documento**. Sale `deleted` de `documents.status`: un documento controlado se retira marcandolo obsoleto, no se borra. Idempotente |
| `21_significancia_del_aspecto.sql` | `environmental_aspects.significance` admitia `compliant / partial / non_compliant / pending`: los estados de `article_compliance.compliance_status`, de donde se copio. **Son dos preguntas distintas.** La significancia (ISO 14001 §6.1.2) contesta si el aspecto importa lo suficiente como para gestionarlo; el cumplimiento, si se cumple un requisito legal. Un aspecto puede ser significativo y estar controlado, y con el vocabulario viejo eso no se podia ni escribir. El dano era visible: la pantalla tiene una columna 'Significativo' y un filtro 'significativo sin tratar' —el hallazgo mas comun en una auditoria de 14001— y ninguno podia funcionar. Las filas existentes pasan a `pending` y **no se traducen**: traducirlas seria inventar una evaluacion que nadie hizo. **Salta del 18 al 21** para no chocar con las 19 y 20 del PR de notificaciones, que va en paralelo; el hueco es inocuo porque la lista es explicita. Idempotente |
| `02_seed.sql` | Datos de demo: 2 tenants, 5 usuarios, obligaciones y una matriz legal evaluada. Sin esto el Dashboard muestra ceros correctos que no permiten ver si algo funciona |

`02_smoke_test.sql` no es parte del despliegue — es la verificación. Corrélo después de cualquier cambio al esquema.

## Multi-tenancy: cómo lo usa la API

El aislamiento tiene dos barreras. La primera es el `WHERE tenant_id = ...` de cada repositorio. La segunda es RLS, que existe justamente para cuando la primera falle.

Para que RLS funcione, **la API debe abrir cada transacción declarando el tenant de la sesión**:

```sql
SET LOCAL ambienta.tenant_id = '<uuid del tenant>';
```

Y conectarse con un rol que no sea superusuario — `ambienta_app` está creado para eso. Un superusuario **ignora RLS por completo**, así que si la API se conecta como `postgres` el aislamiento no existe aunque las policies estén ahí.

Sin `ambienta.tenant_id` seteado, las consultas no devuelven filas. Falla cerrado a propósito: es preferible una pantalla vacía a una fuga de datos entre clientes.

## Qué NO incluye

**El borrador v1.8 del Análisis Funcional** (RF-90 a RF-114): instrumentos de auditoría, checklist por cláusula, entidad Hallazgo separada del registro de mejora, información documentada y colaboración. Ese borrador tiene 9 decisiones abiertas y CLAUDE.md §1 exige spec aprobada antes de implementar. Va en una migración posterior.

## Decisiones tomadas por defecto

Tres puntos del modelo estaban sin cerrar. Se eligió un valor por defecto para no bloquear el arranque, pero **conviene confirmarlos**:

| Punto | Qué se hizo | Qué falta decidir |
|---|---|---|
| Escala de severidad | `minor · major · critical` (la del modelo del backend), como `CHECK` | RF-100 del borrador v1.8 pide que sea configurable por empresa. Cuando se apruebe, el `CHECK` pasa a ser tabla de catálogo |
| Estados de un hallazgo | Los 6 del backend | El frontend usa 3 y el borrador v1.8 modela las etapas como entidad propia |
| Etapas del tratamiento | Columna `improvement_stages` JSONB en `nonconformities` | Si se normalizan, se convierte en tabla hija. El JSONB evita perder lo que el frontend ya guarda mientras tanto |

El stack del backend quedó resuelto en **FastAPI** (ADR-005), y no afectaba a este esquema: era el mismo en cualquier caso.

## Convenciones

- `uuid` para entidades de negocio, `bigserial` para eventos, `smallserial` para catálogos
- `timestamptz` para eventos, `date` para vigencias legales
- `created_at/by` y `updated_at/by` en toda tabla de negocio; `updated_at` lo mantiene un trigger
- Borrado lógico con `deleted_at` e índices parciales `WHERE deleted_at IS NULL`
- El catálogo normativo (`legal_norms`, `legal_articles`, `sectors`, `countries`) **no lleva `tenant_id`**: la ley es la misma para todos
